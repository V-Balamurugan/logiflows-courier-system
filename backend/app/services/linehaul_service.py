import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assignment import DeliveryAssignment
from app.models.branch import Branch
from app.models.enums import (
    AssignmentStatus,
    BagStatus,
    DiscrepancySeverity,
    DiscrepancyStatus,
    DiscrepancyType,
    ManifestItemStatus,
    ManifestStatus,
    ParcelStatus,
    UserRole,
    VehicleStatus,
)
from app.models.linehaul import (
    BagItem,
    ConsolidationBag,
    LinehaulManifest,
    LinehaulManifestItem,
    TransferDiscrepancy,
)
from app.models.route import DeliveryRoute, RouteStop
from app.models.parcel import Parcel
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.linehaul import (
    BagCreate,
    BagDebagRequest,
    BagParcelAttachRequest,
    BagParcelInfo,
    BagResponse,
    BagSealRequest,
    DiscrepancyCreate,
    DiscrepancyResolveRequest,
    DiscrepancyResponse,
    ManifestArriveRequest,
    ManifestAttachItemsRequest,
    ManifestCancelRequest,
    ManifestCreate,
    ManifestDispatchRequest,
    ManifestItemResponse,
    ManifestReconcileRequest,
    ManifestReconciliationResponse,
    ManifestResponse,
    ManifestSealRequest,
)
from app.services.state_machine import ShipmentStateMachine


class LinehaulService:
    """Service layer for consolidation bags, branch-to-branch manifests, receiving, and discrepancies."""

    # --- Helpers ---

    @staticmethod
    def _generate_unique_code(db: Session, model: Any, column: Any, prefix: str) -> str:
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        for _ in range(10):
            candidate = f"{prefix}-{date_part}-{secrets.token_hex(3).upper()}"
            exists = db.query(model.id).filter(column == candidate).first()
            if not exists:
                return candidate
        return f"{prefix}-{date_part}-{secrets.token_hex(5).upper()}"

    @staticmethod
    def _get_branch_for_tenant(db: Session, current_user: User, branch_id: int) -> Branch:
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id or branch.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
        return branch

    @staticmethod
    def _validate_route_branches(
        db: Session, current_user: User, origin_branch_id: int, dest_branch_id: int
    ) -> Tuple[Branch, Branch]:
        if origin_branch_id == dest_branch_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Origin branch and destination branch must be different",
            )
        origin = LinehaulService._get_branch_for_tenant(db, current_user, origin_branch_id)
        dest = LinehaulService._get_branch_for_tenant(db, current_user, dest_branch_id)

        if origin.organization_id != dest.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Destination branch not found in organization",
            )
        if not origin.is_active or not dest.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Both origin and destination branches must be active",
            )
        if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
            if current_user.branch_id != origin.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Branch managers can only initiate transfers from their own assigned branch",
                )
        return origin, dest

    @staticmethod
    def _assert_origin_operator(current_user: User, origin_branch_id: int) -> None:
        if current_user.role in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
            return
        if current_user.role == UserRole.BRANCH_MANAGER:
            if not current_user.branch_id or current_user.branch_id == origin_branch_id:
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the origin branch manager or org admin may modify or dispatch this outbound transfer",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for outbound linehaul operation",
        )

    @staticmethod
    def _assert_dest_operator(current_user: User, dest_branch_id: int) -> None:
        if current_user.role in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
            return
        if current_user.role == UserRole.BRANCH_MANAGER:
            if not current_user.branch_id or current_user.branch_id == dest_branch_id:
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the destination branch manager or org admin may receive or reconcile this arrival",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for inward linehaul operation",
        )

    @staticmethod
    def _get_bag_scoped(db: Session, current_user: User, bag_id: int) -> ConsolidationBag:
        bag = db.query(ConsolidationBag).filter(ConsolidationBag.id == bag_id).first()
        if not bag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consolidation bag not found")
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id or bag.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consolidation bag not found")
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                if current_user.branch_id not in (bag.origin_branch_id, bag.dest_branch_id):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="Consolidation bag not found"
                    )
        return bag

    @staticmethod
    def _get_manifest_scoped(db: Session, current_user: User, manifest_id: int) -> LinehaulManifest:
        manifest = db.query(LinehaulManifest).filter(LinehaulManifest.id == manifest_id).first()
        if not manifest:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linehaul manifest not found")
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id or manifest.organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Linehaul manifest not found"
                )
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                if current_user.branch_id not in (manifest.origin_branch_id, manifest.dest_branch_id):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="Linehaul manifest not found"
                    )
            elif current_user.role == UserRole.DELIVERY_AGENT:
                if manifest.driver_id != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="Linehaul manifest not found"
                    )
        return manifest

    @staticmethod
    def _resolve_parcels(
        db: Session,
        organization_id: int,
        parcel_ids: List[int],
        tracking_numbers: List[str],
    ) -> List[Parcel]:
        parcels_by_id: Dict[int, Parcel] = {}
        if parcel_ids:
            found = db.query(Parcel).filter(Parcel.id.in_(parcel_ids)).all()
            found_map = {p.id: p for p in found}
            for pid in parcel_ids:
                p = found_map.get(pid)
                if not p:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel {pid} not found")
                p_org = p.origin_branch.organization_id if p.origin_branch else None
                if p_org != organization_id:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel {pid} not found")
                parcels_by_id[p.id] = p

        cleaned_tns = [tn.strip() for tn in tracking_numbers if tn and tn.strip()]
        if cleaned_tns:
            found_tn = db.query(Parcel).filter(Parcel.tracking_number.in_(cleaned_tns)).all()
            tn_map = {p.tracking_number: p for p in found_tn}
            for tn in cleaned_tns:
                p = tn_map.get(tn)
                if not p:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel '{tn}' not found")
                p_org = p.origin_branch.organization_id if p.origin_branch else None
                if p_org != organization_id:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel '{tn}' not found")
                parcels_by_id[p.id] = p

        return list(parcels_by_id.values())

    @staticmethod
    def _validate_parcel_for_loading(
        db: Session,
        parcel: Parcel,
        origin_branch_id: int,
        dest_branch_id: int,
        allow_in_bag_id: Optional[int] = None,
    ) -> None:
        if parcel.origin_branch_id != origin_branch_id or parcel.dest_branch_id != dest_branch_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parcel {parcel.tracking_number} route mismatch for this transfer corridor",
            )
        if parcel.delivery_status != ParcelStatus.AT_ORIGIN_BRANCH:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Parcel {parcel.tracking_number} must be AT_ORIGIN_BRANCH before loading "
                    f"(current: {parcel.delivery_status.value})"
                ),
            )
        active_assign = (
            db.query(DeliveryAssignment)
            .filter(
                DeliveryAssignment.parcel_id == parcel.id,
                DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]),
            )
            .first()
        )
        if active_assign:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} holds active DeliveryAssignment #{active_assign.id}",
            )
        active_route_stop = (
            db.query(RouteStop)
            .filter(RouteStop.parcel_id == parcel.id, RouteStop.is_active == True)
            .first()
        )
        if active_route_stop:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} is actively scheduled on Route #{active_route_stop.route_id}",
            )
        active_bag_item = (
            db.query(BagItem)
            .filter(BagItem.parcel_id == parcel.id, BagItem.is_active == True)
            .first()
        )
        if active_bag_item and active_bag_item.bag_id != allow_in_bag_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} is already consolidated inside Bag #{active_bag_item.bag_id}",
            )
        active_manifest_item = (
            db.query(LinehaulManifestItem)
            .filter(LinehaulManifestItem.parcel_id == parcel.id, LinehaulManifestItem.is_active == True)
            .first()
        )
        if active_manifest_item:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} is already assigned to active Manifest #{active_manifest_item.manifest_id}",
            )

    @staticmethod
    def _recompute_bag_totals(db: Session, bag: ConsolidationBag) -> None:
        active_items = (
            db.query(BagItem).filter(BagItem.bag_id == bag.id, BagItem.is_active == True).all()
        )
        bag.parcel_count = len(active_items)
        total_w = Decimal("0.0")
        for bi in active_items:
            if bi.parcel:
                total_w += Decimal(str(bi.parcel.weight_kg or 0.0))
        bag.total_weight_kg = float(total_w)

    @staticmethod
    def _recompute_manifest_totals(db: Session, manifest: LinehaulManifest) -> None:
        items = db.query(LinehaulManifestItem).filter(LinehaulManifestItem.manifest_id == manifest.id).all()
        manifest.expected_parcel_count = len(items)
        manifest.received_parcel_count = sum(
            1 for item in items if item.status in (ManifestItemStatus.RECEIVED, ManifestItemStatus.DAMAGED)
        )
        total_w = Decimal("0.0")
        for item in items:
            if item.parcel:
                total_w += Decimal(str(item.parcel.weight_kg or 0.0))
        manifest.total_weight_kg = float(total_w)

    @staticmethod
    def _validate_vehicle_and_capacity(
        db: Session,
        organization_id: int,
        vehicle_id: int,
        total_weight_kg: float,
        exclude_manifest_id: Optional[int] = None,
    ) -> Vehicle:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.is_active == True).first()
        if not vehicle or vehicle.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

        if vehicle.status != VehicleStatus.AVAILABLE:
            # Allow reusing the same vehicle if it was already provisionally linked only if available
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle {vehicle.vehicle_number} is unavailable (status: {vehicle.status.value})",
            )

        active_assign = (
            db.query(DeliveryAssignment)
            .filter(
                DeliveryAssignment.vehicle_id == vehicle.id,
                DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]),
            )
            .first()
        )
        if active_assign:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle {vehicle.vehicle_number} is actively assigned on Assignment #{active_assign.id}",
            )
        active_route = (
            db.query(DeliveryRoute)
            .filter(DeliveryRoute.vehicle_id == vehicle.id, DeliveryRoute.is_active_dispatch == True)
            .first()
        )
        if active_route:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle {vehicle.vehicle_number} is actively dispatched on Route {active_route.route_code}",
            )

        conflict_query = db.query(LinehaulManifest).filter(
            LinehaulManifest.vehicle_id == vehicle.id,
            LinehaulManifest.status.in_([ManifestStatus.SEALED, ManifestStatus.IN_TRANSIT]),
        )
        if exclude_manifest_id is not None:
            conflict_query = conflict_query.filter(LinehaulManifest.id != exclude_manifest_id)
        conflict_manifest = conflict_query.first()
        if conflict_manifest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle {vehicle.vehicle_number} is locked on Manifest {conflict_manifest.manifest_number}",
            )

        if Decimal(str(total_weight_kg)) > Decimal(str(vehicle.max_weight_kg)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Manifest payload weight {total_weight_kg:.2f} kg exceeds vehicle "
                    f"{vehicle.vehicle_number} capacity {vehicle.max_weight_kg:.2f} kg"
                ),
            )
        return vehicle

    @staticmethod
    def _validate_driver(db: Session, organization_id: int, driver_id: int) -> User:
        driver = db.query(User).filter(User.id == driver_id, User.is_active == True).first()
        if not driver or driver.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
        if driver.role not in (UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected driver must hold DELIVERY_AGENT or BRANCH_MANAGER role",
            )
        return driver

    # --- Response Serializers ---

    @staticmethod
    def to_bag_response(bag: ConsolidationBag) -> BagResponse:
        parcel_infos = [
            BagParcelInfo(
                parcel_id=bi.parcel_id,
                tracking_number=bi.parcel.tracking_number if bi.parcel else "",
                weight_kg=bi.parcel.weight_kg if bi.parcel else 0.0,
                delivery_status=bi.parcel.delivery_status.value if bi.parcel else "",
                is_active=bi.is_active,
                added_at=bi.added_at,
                debagged_at=bi.debagged_at,
            )
            for bi in bag.bag_items
        ]
        return BagResponse(
            id=bag.id,
            organization_id=bag.organization_id,
            bag_code=bag.bag_code,
            origin_branch_id=bag.origin_branch_id,
            dest_branch_id=bag.dest_branch_id,
            origin_branch_name=bag.origin_branch.branch_name if bag.origin_branch else None,
            dest_branch_name=bag.dest_branch.branch_name if bag.dest_branch else None,
            manifest_id=bag.manifest_id,
            seal_number=bag.seal_number,
            status=bag.status,
            total_weight_kg=bag.total_weight_kg,
            parcel_count=bag.parcel_count,
            notes=bag.notes,
            sealed_at=bag.sealed_at,
            received_at=bag.received_at,
            created_at=bag.created_at,
            parcels=parcel_infos,
        )

    @staticmethod
    def to_discrepancy_response(disc: TransferDiscrepancy) -> DiscrepancyResponse:
        return DiscrepancyResponse(
            id=disc.id,
            organization_id=disc.organization_id,
            manifest_id=disc.manifest_id,
            manifest_number=disc.manifest.manifest_number if disc.manifest else None,
            parcel_id=disc.parcel_id,
            tracking_number=disc.parcel.tracking_number if disc.parcel else None,
            bag_id=disc.bag_id,
            discrepancy_type=disc.discrepancy_type,
            severity=disc.severity,
            status=disc.status,
            description=disc.description,
            resolution_notes=disc.resolution_notes,
            reported_by_id=disc.reported_by_id,
            reported_by_name=disc.reported_by.full_name if disc.reported_by else None,
            resolved_by_id=disc.resolved_by_id,
            reported_at=disc.reported_at,
            resolved_at=disc.resolved_at,
        )

    @staticmethod
    def to_manifest_response(manifest: LinehaulManifest) -> ManifestResponse:
        return ManifestResponse(
            id=manifest.id,
            organization_id=manifest.organization_id,
            manifest_number=manifest.manifest_number,
            origin_branch_id=manifest.origin_branch_id,
            dest_branch_id=manifest.dest_branch_id,
            origin_branch_name=manifest.origin_branch.branch_name if manifest.origin_branch else None,
            dest_branch_name=manifest.dest_branch.branch_name if manifest.dest_branch else None,
            vehicle_id=manifest.vehicle_id,
            vehicle_number=manifest.vehicle.vehicle_number if manifest.vehicle else None,
            driver_id=manifest.driver_id,
            driver_name=manifest.driver.full_name if manifest.driver else None,
            seal_number=manifest.seal_number,
            status=manifest.status,
            expected_parcel_count=manifest.expected_parcel_count,
            received_parcel_count=manifest.received_parcel_count,
            total_weight_kg=manifest.total_weight_kg,
            notes=manifest.notes,
            dispatched_at=manifest.dispatched_at,
            arrived_at=manifest.arrived_at,
            reconciled_at=manifest.reconciled_at,
            created_at=manifest.created_at,
            items=[
                ManifestItemResponse(
                    id=item.id,
                    parcel_id=item.parcel_id,
                    tracking_number=item.parcel.tracking_number if item.parcel else "",
                    weight_kg=item.parcel.weight_kg if item.parcel else 0.0,
                    bag_id=item.bag_id,
                    bag_code=item.bag.bag_code if item.bag else None,
                    status=item.status,
                    is_active=item.is_active,
                    scanned_out_at=item.scanned_out_at,
                    scanned_in_at=item.scanned_in_at,
                    remarks=item.remarks,
                )
                for item in manifest.items
            ],
            bags=[LinehaulService.to_bag_response(b) for b in manifest.bags],
            discrepancies=[LinehaulService.to_discrepancy_response(d) for d in manifest.discrepancies],
        )

    # --- Consolidation Bag Operations ---

    @staticmethod
    def create_bag(db: Session, current_user: User, data: BagCreate) -> BagResponse:
        origin, dest = LinehaulService._validate_route_branches(
            db, current_user, data.origin_branch_id, data.dest_branch_id
        )
        bag_code = LinehaulService._generate_unique_code(db, ConsolidationBag, ConsolidationBag.bag_code, "BAG")
        bag = ConsolidationBag(
            organization_id=origin.organization_id,
            bag_code=bag_code,
            origin_branch_id=origin.id,
            dest_branch_id=dest.id,
            status=BagStatus.OPEN,
            notes=data.notes,
            created_by_id=current_user.id,
        )
        db.add(bag)
        db.commit()
        db.refresh(bag)
        return LinehaulService.to_bag_response(bag)

    @staticmethod
    def list_bags(
        db: Session,
        current_user: User,
        status_filter: Optional[BagStatus] = None,
        origin_branch_id: Optional[int] = None,
        dest_branch_id: Optional[int] = None,
        unassigned_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[BagResponse]:
        query = db.query(ConsolidationBag)
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                return []
            query = query.filter(ConsolidationBag.organization_id == current_user.organization_id)
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                query = query.filter(
                    (ConsolidationBag.origin_branch_id == current_user.branch_id)
                    | (ConsolidationBag.dest_branch_id == current_user.branch_id)
                )
        if status_filter:
            query = query.filter(ConsolidationBag.status == status_filter)
        if origin_branch_id:
            query = query.filter(ConsolidationBag.origin_branch_id == origin_branch_id)
        if dest_branch_id:
            query = query.filter(ConsolidationBag.dest_branch_id == dest_branch_id)
        if unassigned_only:
            query = query.filter(ConsolidationBag.manifest_id.is_(None))
        bags = query.order_by(ConsolidationBag.created_at.desc()).offset(skip).limit(limit).all()
        return [LinehaulService.to_bag_response(b) for b in bags]

    @staticmethod
    def get_bag(db: Session, current_user: User, bag_id: int) -> BagResponse:
        bag = LinehaulService._get_bag_scoped(db, current_user, bag_id)
        return LinehaulService.to_bag_response(bag)

    @staticmethod
    def attach_parcels_to_bag(
        db: Session, current_user: User, bag_id: int, req: BagParcelAttachRequest
    ) -> BagResponse:
        bag = LinehaulService._get_bag_scoped(db, current_user, bag_id)
        LinehaulService._assert_origin_operator(current_user, bag.origin_branch_id)
        if bag.status != BagStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot modify bag in '{bag.status.value}' status",
            )
        parcels = LinehaulService._resolve_parcels(
            db, bag.organization_id, req.parcel_ids, req.tracking_numbers
        )
        if not parcels:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide at least one parcel_id or tracking_number",
            )
        existing_ids = {bi.parcel_id for bi in bag.bag_items if bi.is_active}
        for parcel in parcels:
            if parcel.id in existing_ids:
                continue
            LinehaulService._validate_parcel_for_loading(
                db, parcel, bag.origin_branch_id, bag.dest_branch_id
            )
            db.add(BagItem(bag_id=bag.id, parcel_id=parcel.id, is_active=True))

        try:
            db.flush()
            LinehaulService._recompute_bag_totals(db, bag)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more parcels are already actively consolidated in another bag",
            )
        db.refresh(bag)
        return LinehaulService.to_bag_response(bag)

    @staticmethod
    def remove_parcel_from_bag(
        db: Session, current_user: User, bag_id: int, parcel_id: int
    ) -> BagResponse:
        bag = LinehaulService._get_bag_scoped(db, current_user, bag_id)
        LinehaulService._assert_origin_operator(current_user, bag.origin_branch_id)
        if bag.status != BagStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot remove parcels from bag in '{bag.status.value}' status",
            )
        item = db.query(BagItem).filter(BagItem.bag_id == bag.id, BagItem.parcel_id == parcel_id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not in bag")
        db.delete(item)
        db.flush()
        LinehaulService._recompute_bag_totals(db, bag)
        db.commit()
        db.refresh(bag)
        return LinehaulService.to_bag_response(bag)

    @staticmethod
    def seal_bag(db: Session, current_user: User, bag_id: int, req: BagSealRequest) -> BagResponse:
        bag = LinehaulService._get_bag_scoped(db, current_user, bag_id)
        LinehaulService._assert_origin_operator(current_user, bag.origin_branch_id)
        if bag.status != BagStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bag cannot be sealed from '{bag.status.value}' status",
            )
        LinehaulService._recompute_bag_totals(db, bag)
        if bag.parcel_count == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cannot seal an empty consolidation bag",
            )
        bag.seal_number = req.seal_number or LinehaulService._generate_unique_code(
            db, ConsolidationBag, ConsolidationBag.seal_number, "BSEAL"
        )
        bag.status = BagStatus.SEALED
        bag.sealed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(bag)
        return LinehaulService.to_bag_response(bag)

    @staticmethod
    def debag_at_destination(
        db: Session, current_user: User, bag_id: int, req: BagDebagRequest
    ) -> BagResponse:
        bag = LinehaulService._get_bag_scoped(db, current_user, bag_id)
        LinehaulService._assert_dest_operator(current_user, bag.dest_branch_id)
        if bag.status != BagStatus.RECEIVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bag must be in RECEIVED state at destination before de-bagging (current: {bag.status.value})",
            )
        now = datetime.now(timezone.utc)
        for bi in bag.bag_items:
            if bi.is_active:
                bi.is_active = False
                bi.debagged_at = now
        bag.status = BagStatus.OPENED_AT_DEST
        if req.notes:
            bag.notes = f"{bag.notes} | Debagged: {req.notes}" if bag.notes else f"Debagged: {req.notes}"
        db.commit()
        db.refresh(bag)
        return LinehaulService.to_bag_response(bag)

    # --- Manifest Lifecycle Operations ---

    @staticmethod
    def _attach_bags_and_parcels_internal(
        db: Session,
        manifest: LinehaulManifest,
        bags: List[ConsolidationBag],
        loose_parcels: List[Parcel],
    ) -> None:
        existing_item_parcel_ids = {item.parcel_id for item in manifest.items}
        for bag in bags:
            if bag.organization_id != manifest.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bag {bag.id} not found")
            if bag.origin_branch_id != manifest.origin_branch_id or bag.dest_branch_id != manifest.dest_branch_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Bag {bag.bag_code} corridor does not match manifest origin/destination",
                )
            if bag.status != BagStatus.SEALED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Bag {bag.bag_code} must be SEALED before attaching to a manifest",
                )
            if bag.manifest_id is not None and bag.manifest_id != manifest.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Bag {bag.bag_code} is already attached to Manifest #{bag.manifest_id}",
                )
            bag.manifest_id = manifest.id
            active_bag_items = [bi for bi in bag.bag_items if bi.is_active]
            for bi in active_bag_items:
                if not bi.parcel or bi.parcel.id in existing_item_parcel_ids:
                    continue
                LinehaulService._validate_parcel_for_loading(
                    db,
                    bi.parcel,
                    manifest.origin_branch_id,
                    manifest.dest_branch_id,
                    allow_in_bag_id=bag.id,
                )
                db.add(
                    LinehaulManifestItem(
                        manifest_id=manifest.id,
                        parcel_id=bi.parcel.id,
                        bag_id=bag.id,
                        status=ManifestItemStatus.EXPECTED,
                        is_active=True,
                    )
                )
                existing_item_parcel_ids.add(bi.parcel.id)

        for parcel in loose_parcels:
            if parcel.id in existing_item_parcel_ids:
                continue
            LinehaulService._validate_parcel_for_loading(
                db, parcel, manifest.origin_branch_id, manifest.dest_branch_id
            )
            db.add(
                LinehaulManifestItem(
                    manifest_id=manifest.id,
                    parcel_id=parcel.id,
                    bag_id=None,
                    status=ManifestItemStatus.EXPECTED,
                    is_active=True,
                )
            )
            existing_item_parcel_ids.add(parcel.id)

    @staticmethod
    def create_manifest(db: Session, current_user: User, data: ManifestCreate) -> ManifestResponse:
        origin, dest = LinehaulService._validate_route_branches(
            db, current_user, data.origin_branch_id, data.dest_branch_id
        )
        org_id = origin.organization_id

        if data.driver_id:
            LinehaulService._validate_driver(db, org_id, data.driver_id)

        manifest_number = LinehaulService._generate_unique_code(
            db, LinehaulManifest, LinehaulManifest.manifest_number, "LH"
        )
        manifest = LinehaulManifest(
            organization_id=org_id,
            manifest_number=manifest_number,
            origin_branch_id=origin.id,
            dest_branch_id=dest.id,
            vehicle_id=data.vehicle_id,
            driver_id=data.driver_id,
            seal_number=data.seal_number,
            status=ManifestStatus.DRAFT,
            notes=data.notes,
            created_by_id=current_user.id,
        )
        db.add(manifest)
        db.flush()

        bags: List[ConsolidationBag] = []
        if data.bag_ids:
            found_bags = db.query(ConsolidationBag).filter(ConsolidationBag.id.in_(data.bag_ids)).all()
            bag_map = {b.id: b for b in found_bags}
            for bid in data.bag_ids:
                b = bag_map.get(bid)
                if not b or b.organization_id != org_id:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bag {bid} not found")
                bags.append(b)

        loose_parcels = (
            LinehaulService._resolve_parcels(db, org_id, data.parcel_ids, []) if data.parcel_ids else []
        )
        LinehaulService._attach_bags_and_parcels_internal(db, manifest, bags, loose_parcels)

        try:
            db.flush()
            LinehaulService._recompute_manifest_totals(db, manifest)
            if data.vehicle_id:
                LinehaulService._validate_vehicle_and_capacity(
                    db, org_id, data.vehicle_id, manifest.total_weight_kg, exclude_manifest_id=manifest.id
                )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more parcels are already assigned to an active manifest",
            )
        db.refresh(manifest)
        return LinehaulService.to_manifest_response(manifest)

    @staticmethod
    def list_manifests(
        db: Session,
        current_user: User,
        status_filter: Optional[ManifestStatus] = None,
        origin_branch_id: Optional[int] = None,
        dest_branch_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ManifestResponse]:
        query = db.query(LinehaulManifest)
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                return []
            query = query.filter(LinehaulManifest.organization_id == current_user.organization_id)
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                query = query.filter(
                    (LinehaulManifest.origin_branch_id == current_user.branch_id)
                    | (LinehaulManifest.dest_branch_id == current_user.branch_id)
                )
            elif current_user.role == UserRole.DELIVERY_AGENT:
                query = query.filter(LinehaulManifest.driver_id == current_user.id)
        if status_filter:
            query = query.filter(LinehaulManifest.status == status_filter)
        if origin_branch_id:
            query = query.filter(LinehaulManifest.origin_branch_id == origin_branch_id)
        if dest_branch_id:
            query = query.filter(LinehaulManifest.dest_branch_id == dest_branch_id)
        manifests = query.order_by(LinehaulManifest.created_at.desc()).offset(skip).limit(limit).all()
        return [LinehaulService.to_manifest_response(m) for m in manifests]

    @staticmethod
    def get_manifest(db: Session, current_user: User, manifest_id: int) -> ManifestResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        return LinehaulService.to_manifest_response(manifest)

    @staticmethod
    def attach_items_to_manifest(
        db: Session, current_user: User, manifest_id: int, req: ManifestAttachItemsRequest
    ) -> ManifestResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        LinehaulService._assert_origin_operator(current_user, manifest.origin_branch_id)
        if manifest.status != ManifestStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot modify manifest items in '{manifest.status.value}' status",
            )
        bags: List[ConsolidationBag] = []
        if req.bag_ids:
            found_bags = db.query(ConsolidationBag).filter(ConsolidationBag.id.in_(req.bag_ids)).all()
            bag_map = {b.id: b for b in found_bags}
            for bid in req.bag_ids:
                b = bag_map.get(bid)
                if not b or b.organization_id != manifest.organization_id:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bag {bid} not found")
                bags.append(b)
        loose_parcels = LinehaulService._resolve_parcels(
            db, manifest.organization_id, req.parcel_ids, req.tracking_numbers
        )
        if not bags and not loose_parcels:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide at least one bag_id, parcel_id, or tracking_number",
            )
        LinehaulService._attach_bags_and_parcels_internal(db, manifest, bags, loose_parcels)
        try:
            db.flush()
            LinehaulService._recompute_manifest_totals(db, manifest)
            if manifest.vehicle_id:
                LinehaulService._validate_vehicle_and_capacity(
                    db,
                    manifest.organization_id,
                    manifest.vehicle_id,
                    manifest.total_weight_kg,
                    exclude_manifest_id=manifest.id,
                )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more parcels are already assigned to an active manifest",
            )
        db.refresh(manifest)
        return LinehaulService.to_manifest_response(manifest)

    @staticmethod
    def remove_parcel_from_manifest(
        db: Session, current_user: User, manifest_id: int, parcel_id: int
    ) -> ManifestResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        LinehaulService._assert_origin_operator(current_user, manifest.origin_branch_id)
        if manifest.status != ManifestStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot remove items in '{manifest.status.value}' status",
            )
        item = (
            db.query(LinehaulManifestItem)
            .filter(LinehaulManifestItem.manifest_id == manifest.id, LinehaulManifestItem.parcel_id == parcel_id)
            .first()
        )
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found on manifest")
        if item.bag_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove individual parcel belonging to a sealed bag; detach the bag instead",
            )
        db.delete(item)
        db.flush()
        LinehaulService._recompute_manifest_totals(db, manifest)
        db.commit()
        db.refresh(manifest)
        return LinehaulService.to_manifest_response(manifest)

    @staticmethod
    def detach_bag_from_manifest(
        db: Session, current_user: User, manifest_id: int, bag_id: int
    ) -> ManifestResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        LinehaulService._assert_origin_operator(current_user, manifest.origin_branch_id)
        if manifest.status != ManifestStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot detach bag in '{manifest.status.value}' status",
            )
        bag = (
            db.query(ConsolidationBag)
            .filter(ConsolidationBag.id == bag_id, ConsolidationBag.manifest_id == manifest.id)
            .first()
        )
        if not bag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bag not attached to manifest")
        db.query(LinehaulManifestItem).filter(
            LinehaulManifestItem.manifest_id == manifest.id, LinehaulManifestItem.bag_id == bag.id
        ).delete()
        bag.manifest_id = None
        db.flush()
        LinehaulService._recompute_manifest_totals(db, manifest)
        db.commit()
        db.refresh(manifest)
        return LinehaulService.to_manifest_response(manifest)

    @staticmethod
    def seal_manifest(
        db: Session, current_user: User, manifest_id: int, req: ManifestSealRequest
    ) -> ManifestResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        LinehaulService._assert_origin_operator(current_user, manifest.origin_branch_id)
        if manifest.status != ManifestStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot seal manifest in '{manifest.status.value}' status",
            )
        LinehaulService._recompute_manifest_totals(db, manifest)
        if manifest.expected_parcel_count == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cannot seal an empty manifest",
            )
        manifest.seal_number = req.seal_number or manifest.seal_number or LinehaulService._generate_unique_code(
            db, LinehaulManifest, LinehaulManifest.seal_number, "MSEAL"
        )
        manifest.status = ManifestStatus.SEALED
        db.commit()
        db.refresh(manifest)
        return LinehaulService.to_manifest_response(manifest)

    @staticmethod
    def dispatch_manifest(
        db: Session, current_user: User, manifest_id: int, req: ManifestDispatchRequest
    ) -> ManifestResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        LinehaulService._assert_origin_operator(current_user, manifest.origin_branch_id)
        if manifest.status not in (ManifestStatus.DRAFT, ManifestStatus.SEALED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Manifest cannot be dispatched from '{manifest.status.value}' status",
            )
        LinehaulService._recompute_manifest_totals(db, manifest)
        if manifest.expected_parcel_count == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cannot dispatch an empty manifest",
            )

        vehicle_id = req.vehicle_id or manifest.vehicle_id
        if not vehicle_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A linehaul vehicle must be assigned before dispatch",
            )

        driver_id = req.driver_id or manifest.driver_id
        if driver_id:
            LinehaulService._validate_driver(db, manifest.organization_id, driver_id)
            manifest.driver_id = driver_id

        vehicle = LinehaulService._validate_vehicle_and_capacity(
            db, manifest.organization_id, vehicle_id, manifest.total_weight_kg, exclude_manifest_id=manifest.id
        )
        seal_number = req.seal_number or manifest.seal_number or LinehaulService._generate_unique_code(
            db, LinehaulManifest, LinehaulManifest.seal_number, "MSEAL"
        )

        # Atomic conditional vehicle lock to eliminate double-dispatch races
        veh_lock = db.execute(
            update(Vehicle)
            .where(Vehicle.id == vehicle.id, Vehicle.status == VehicleStatus.AVAILABLE)
            .values(status=VehicleStatus.IN_TRANSIT)
        )
        if veh_lock.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle {vehicle.vehicle_number} was dispatched concurrently; please retry with an available vehicle",
            )

        now = datetime.now(timezone.utc)
        origin_name = manifest.origin_branch.branch_name if manifest.origin_branch else "Origin Hub"
        dest_name = manifest.dest_branch.branch_name if manifest.dest_branch else "Destination Hub"
        remarks = (
            f"Dispatched on linehaul manifest {manifest.manifest_number} "
            f"(Seal: {seal_number}) to {dest_name}"
        )
        broadcasts: List[Dict[str, Any]] = []

        try:
            for item in manifest.items:
                parcel = item.parcel
                if not parcel:
                    continue
                if parcel.delivery_status != ParcelStatus.AT_ORIGIN_BRANCH:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Parcel {parcel.tracking_number} cannot be dispatched while in "
                            f"'{parcel.delivery_status.value}' status"
                        ),
                    )
                ShipmentStateMachine.transition(
                    db=db,
                    current_user=current_user,
                    parcel=parcel,
                    to_status=ParcelStatus.IN_TRANSIT,
                    remarks=remarks,
                    location_name=origin_name,
                    branch_id=manifest.origin_branch_id,
                    source="LINEHAUL_DISPATCH",
                    commit=False,
                )
                item.scanned_out_at = now
                broadcasts.append(
                    {
                        "tracking_number": parcel.tracking_number,
                        "to_status": ParcelStatus.IN_TRANSIT,
                        "location": origin_name,
                        "remarks": remarks,
                        "timestamp": now,
                    }
                )

            for bag in manifest.bags:
                bag.status = BagStatus.IN_TRANSIT

            manifest.vehicle_id = vehicle.id
            manifest.seal_number = seal_number
            manifest.status = ManifestStatus.IN_TRANSIT
            manifest.dispatched_by_id = current_user.id
            manifest.dispatched_at = now
            if req.notes:
                manifest.notes = f"{manifest.notes} | Dispatch: {req.notes}" if manifest.notes else req.notes

            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        for b in broadcasts:
            ShipmentStateMachine.broadcast_milestone(**b)

        db.refresh(manifest)
        return LinehaulService.to_manifest_response(manifest)

    @staticmethod
    def mark_arrived(
        db: Session, current_user: User, manifest_id: int, req: ManifestArriveRequest
    ) -> ManifestResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        if current_user.role == UserRole.DELIVERY_AGENT:
            if manifest.driver_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the assigned linehaul driver or destination hub manager may mark arrival",
                )
        else:
            LinehaulService._assert_dest_operator(current_user, manifest.dest_branch_id)

        if manifest.status != ManifestStatus.IN_TRANSIT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only IN_TRANSIT manifests can be marked arrived (current: {manifest.status.value})",
            )

        now = datetime.now(timezone.utc)
        manifest.status = ManifestStatus.ARRIVED
        manifest.arrived_at = now
        manifest.received_by_id = current_user.id
        if req.notes:
            manifest.notes = f"{manifest.notes} | Arrival: {req.notes}" if manifest.notes else req.notes

        if manifest.vehicle_id and manifest.vehicle and manifest.vehicle.status == VehicleStatus.IN_TRANSIT:
            manifest.vehicle.status = VehicleStatus.AVAILABLE

        for bag in manifest.bags:
            if bag.status == BagStatus.IN_TRANSIT:
                bag.status = BagStatus.RECEIVED
                bag.received_at = now

        if not req.seal_intact:
            db.add(
                TransferDiscrepancy(
                    organization_id=manifest.organization_id,
                    manifest_id=manifest.id,
                    discrepancy_type=DiscrepancyType.SEAL_BROKEN,
                    severity=DiscrepancySeverity.CRITICAL,
                    status=DiscrepancyStatus.OPEN,
                    description=(
                        f"Tampered or broken manifest seal detected upon arrival of {manifest.manifest_number} "
                        f"(Expected seal: {manifest.seal_number})"
                    ),
                    reported_by_id=current_user.id,
                    reported_at=now,
                )
            )

        db.commit()
        db.refresh(manifest)
        return LinehaulService.to_manifest_response(manifest)

    @staticmethod
    def reconcile_manifest(
        db: Session, current_user: User, manifest_id: int, req: ManifestReconcileRequest
    ) -> ManifestReconciliationResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        LinehaulService._assert_dest_operator(current_user, manifest.dest_branch_id)

        if manifest.status not in (ManifestStatus.IN_TRANSIT, ManifestStatus.ARRIVED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Manifest cannot be reconciled in '{manifest.status.value}' status",
            )

        now = datetime.now(timezone.utc)
        # Auto-mark arrived if still IN_TRANSIT so inward scan works seamlessly
        if manifest.status == ManifestStatus.IN_TRANSIT:
            manifest.status = ManifestStatus.ARRIVED
            manifest.arrived_at = now
            if manifest.vehicle and manifest.vehicle.status == VehicleStatus.IN_TRANSIT:
                manifest.vehicle.status = VehicleStatus.AVAILABLE
            for bag in manifest.bags:
                if bag.status == BagStatus.IN_TRANSIT:
                    bag.status = BagStatus.RECEIVED
                    bag.received_at = now

        received_set = {tn.strip() for tn in req.received_tracking_numbers if tn and tn.strip()}
        damaged_set = {tn.strip() for tn in req.damaged_tracking_numbers if tn and tn.strip()}
        missing_set = {tn.strip() for tn in req.missing_tracking_numbers if tn and tn.strip()}
        excess_set = {tn.strip() for tn in req.excess_tracking_numbers if tn and tn.strip()}

        overlap = (received_set & damaged_set) | (received_set & missing_set) | (damaged_set & missing_set)
        if overlap:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Conflicting scan classifications for tracking number(s): {', '.join(sorted(overlap))}",
            )

        items_by_tn = {item.parcel.tracking_number: item for item in manifest.items if item.parcel}
        unknown_tns = (received_set | damaged_set | missing_set) - set(items_by_tn.keys())
        if unknown_tns:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parcel(s) not listed on manifest {manifest.manifest_number}: {', '.join(sorted(unknown_tns))}",
            )

        dest_name = manifest.dest_branch.branch_name if manifest.dest_branch else "Destination Hub"
        discrepancies_created = 0
        received_count = 0
        damaged_count = 0
        missing_count = 0
        broadcasts: List[Dict[str, Any]] = []

        if not req.seal_intact:
            db.add(
                TransferDiscrepancy(
                    organization_id=manifest.organization_id,
                    manifest_id=manifest.id,
                    discrepancy_type=DiscrepancyType.SEAL_BROKEN,
                    severity=DiscrepancySeverity.CRITICAL,
                    status=DiscrepancyStatus.OPEN,
                    description=(
                        f"Seal discrepancy reported during reconciliation of {manifest.manifest_number} "
                        f"(Expected seal: {manifest.seal_number})"
                    ),
                    reported_by_id=current_user.id,
                    reported_at=now,
                )
            )
            discrepancies_created += 1

        try:
            for tn in sorted(received_set):
                item = items_by_tn[tn]
                parcel = item.parcel
                if parcel.delivery_status in (ParcelStatus.IN_TRANSIT, ParcelStatus.ON_HOLD):
                    remarks = f"Inward received at {dest_name} on manifest {manifest.manifest_number}"
                    ShipmentStateMachine.transition(
                        db=db,
                        current_user=current_user,
                        parcel=parcel,
                        to_status=ParcelStatus.AT_DESTINATION_BRANCH,
                        remarks=remarks,
                        location_name=dest_name,
                        branch_id=manifest.dest_branch_id,
                        source="LINEHAUL_ARRIVAL",
                        commit=False,
                    )
                    broadcasts.append(
                        {
                            "tracking_number": parcel.tracking_number,
                            "to_status": ParcelStatus.AT_DESTINATION_BRANCH,
                            "location": dest_name,
                            "remarks": remarks,
                            "timestamp": now,
                        }
                    )
                item.status = ManifestItemStatus.RECEIVED
                item.is_active = False
                item.scanned_in_at = now
                item.scanned_in_by_id = current_user.id
                received_count += 1

            for tn in sorted(damaged_set):
                item = items_by_tn[tn]
                parcel = item.parcel
                remarks = f"Damaged on arrival via manifest {manifest.manifest_number} at {dest_name}"
                if parcel.delivery_status in (ParcelStatus.IN_TRANSIT, ParcelStatus.AT_DESTINATION_BRANCH):
                    ShipmentStateMachine.transition(
                        db=db,
                        current_user=current_user,
                        parcel=parcel,
                        to_status=ParcelStatus.ON_HOLD,
                        remarks=remarks,
                        location_name=dest_name,
                        branch_id=manifest.dest_branch_id,
                        source="LINEHAUL_DISCREPANCY",
                        commit=False,
                    )
                    broadcasts.append(
                        {
                            "tracking_number": parcel.tracking_number,
                            "to_status": ParcelStatus.ON_HOLD,
                            "location": dest_name,
                            "remarks": remarks,
                            "timestamp": now,
                        }
                    )
                item.status = ManifestItemStatus.DAMAGED
                item.is_active = False
                item.scanned_in_at = now
                item.scanned_in_by_id = current_user.id
                damaged_count += 1
                db.add(
                    TransferDiscrepancy(
                        organization_id=manifest.organization_id,
                        manifest_id=manifest.id,
                        parcel_id=parcel.id,
                        bag_id=item.bag_id,
                        discrepancy_type=DiscrepancyType.DAMAGED,
                        severity=DiscrepancySeverity.HIGH,
                        status=DiscrepancyStatus.OPEN,
                        description=remarks,
                        reported_by_id=current_user.id,
                        reported_at=now,
                    )
                )
                discrepancies_created += 1

            if req.finalize:
                for item in manifest.items:
                    if item.status == ManifestItemStatus.EXPECTED and item.parcel:
                        missing_set.add(item.parcel.tracking_number)

            for tn in sorted(missing_set):
                item = items_by_tn[tn]
                parcel = item.parcel
                remarks = f"Missing on arrival reconciliation for manifest {manifest.manifest_number} at {dest_name}"
                if parcel.delivery_status == ParcelStatus.IN_TRANSIT:
                    ShipmentStateMachine.transition(
                        db=db,
                        current_user=current_user,
                        parcel=parcel,
                        to_status=ParcelStatus.ON_HOLD,
                        remarks=remarks,
                        location_name=dest_name,
                        branch_id=manifest.dest_branch_id,
                        source="LINEHAUL_DISCREPANCY",
                        commit=False,
                    )
                    broadcasts.append(
                        {
                            "tracking_number": parcel.tracking_number,
                            "to_status": ParcelStatus.ON_HOLD,
                            "location": dest_name,
                            "remarks": remarks,
                            "timestamp": now,
                        }
                    )
                item.status = ManifestItemStatus.MISSING
                item.is_active = False
                item.scanned_in_by_id = current_user.id
                missing_count += 1
                db.add(
                    TransferDiscrepancy(
                        organization_id=manifest.organization_id,
                        manifest_id=manifest.id,
                        parcel_id=parcel.id,
                        bag_id=item.bag_id,
                        discrepancy_type=DiscrepancyType.MISSING,
                        severity=DiscrepancySeverity.HIGH,
                        status=DiscrepancyStatus.OPEN,
                        description=remarks,
                        reported_by_id=current_user.id,
                        reported_at=now,
                    )
                )
                discrepancies_created += 1

            for excess_tn in sorted(excess_set):
                excess_parcel = db.query(Parcel).filter(Parcel.tracking_number == excess_tn).first()
                excess_pid = None
                if excess_parcel:
                    p_org = excess_parcel.origin_branch.organization_id if excess_parcel.origin_branch else None
                    if p_org == manifest.organization_id:
                        excess_pid = excess_parcel.id
                db.add(
                    TransferDiscrepancy(
                        organization_id=manifest.organization_id,
                        manifest_id=manifest.id,
                        parcel_id=excess_pid,
                        discrepancy_type=DiscrepancyType.EXCESS,
                        severity=DiscrepancySeverity.MEDIUM,
                        status=DiscrepancyStatus.OPEN,
                        description=(
                            f"Unmanifested excess parcel '{excess_tn}' unloaded at {dest_name} "
                            f"from manifest {manifest.manifest_number}"
                        ),
                        reported_by_id=current_user.id,
                        reported_at=now,
                    )
                )
                discrepancies_created += 1

            LinehaulService._recompute_manifest_totals(db, manifest)
            manifest.received_by_id = current_user.id
            if req.notes:
                manifest.notes = f"{manifest.notes} | Reconcile: {req.notes}" if manifest.notes else req.notes

            if req.finalize:
                manifest.status = ManifestStatus.RECONCILED
                manifest.reconciled_at = now
                for bag in manifest.bags:
                    if bag.status == BagStatus.IN_TRANSIT:
                        bag.status = BagStatus.RECEIVED
                        bag.received_at = now

            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        for b in broadcasts:
            ShipmentStateMachine.broadcast_milestone(**b)

        db.refresh(manifest)
        return ManifestReconciliationResponse(
            manifest=LinehaulService.to_manifest_response(manifest),
            received_count=received_count,
            damaged_count=damaged_count,
            missing_count=missing_count,
            excess_count=len(excess_set),
            discrepancies_created=discrepancies_created,
        )

    @staticmethod
    def cancel_manifest(
        db: Session, current_user: User, manifest_id: int, req: ManifestCancelRequest
    ) -> ManifestResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, manifest_id)
        LinehaulService._assert_origin_operator(current_user, manifest.origin_branch_id)
        if manifest.status not in (ManifestStatus.DRAFT, ManifestStatus.SEALED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel manifest in '{manifest.status.value}' status",
            )
        for bag in manifest.bags:
            bag.manifest_id = None
        for item in manifest.items:
            item.is_active = False
        manifest.status = ManifestStatus.CANCELLED
        manifest.notes = f"{manifest.notes} | Cancelled: {req.reason}" if manifest.notes else f"Cancelled: {req.reason}"
        db.commit()
        db.refresh(manifest)
        return LinehaulService.to_manifest_response(manifest)

    # --- Transfer Discrepancy Operations ---

    @staticmethod
    def create_discrepancy(
        db: Session, current_user: User, data: DiscrepancyCreate
    ) -> DiscrepancyResponse:
        manifest = LinehaulService._get_manifest_scoped(db, current_user, data.manifest_id)
        if manifest.status not in (
            ManifestStatus.IN_TRANSIT,
            ManifestStatus.ARRIVED,
            ManifestStatus.RECONCILED,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Discrepancies can only be logged after dispatch (current: {manifest.status.value})",
            )

        parcel_id = data.parcel_id
        if data.tracking_number and not parcel_id:
            parcel = (
                db.query(Parcel).filter(Parcel.tracking_number == data.tracking_number.strip()).first()
            )
            if not parcel:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
            p_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
            if p_org != manifest.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
            parcel_id = parcel.id

        now = datetime.now(timezone.utc)
        broadcast_args: Optional[Dict[str, Any]] = None

        if parcel_id and data.discrepancy_type in (DiscrepancyType.MISSING, DiscrepancyType.DAMAGED):
            item = (
                db.query(LinehaulManifestItem)
                .filter(
                    LinehaulManifestItem.manifest_id == manifest.id,
                    LinehaulManifestItem.parcel_id == parcel_id,
                )
                .first()
            )
            if item and item.parcel:
                item.status = (
                    ManifestItemStatus.MISSING
                    if data.discrepancy_type == DiscrepancyType.MISSING
                    else ManifestItemStatus.DAMAGED
                )
                item.is_active = False
                if item.parcel.delivery_status in (ParcelStatus.IN_TRANSIT, ParcelStatus.AT_DESTINATION_BRANCH):
                    dest_name = manifest.dest_branch.branch_name if manifest.dest_branch else "Destination Hub"
                    ShipmentStateMachine.transition(
                        db=db,
                        current_user=current_user,
                        parcel=item.parcel,
                        to_status=ParcelStatus.ON_HOLD,
                        remarks=data.description,
                        location_name=dest_name,
                        branch_id=manifest.dest_branch_id,
                        source="LINEHAUL_DISCREPANCY",
                        commit=False,
                    )
                    broadcast_args = {
                        "tracking_number": item.parcel.tracking_number,
                        "to_status": ParcelStatus.ON_HOLD,
                        "location": dest_name,
                        "remarks": data.description,
                        "timestamp": now,
                    }

        disc = TransferDiscrepancy(
            organization_id=manifest.organization_id,
            manifest_id=manifest.id,
            parcel_id=parcel_id,
            bag_id=data.bag_id,
            discrepancy_type=data.discrepancy_type,
            severity=data.severity,
            status=DiscrepancyStatus.OPEN,
            description=data.description,
            reported_by_id=current_user.id,
            reported_at=now,
        )
        db.add(disc)
        db.commit()
        if broadcast_args:
            ShipmentStateMachine.broadcast_milestone(**broadcast_args)
        db.refresh(disc)
        return LinehaulService.to_discrepancy_response(disc)

    @staticmethod
    def list_discrepancies(
        db: Session,
        current_user: User,
        manifest_id: Optional[int] = None,
        status_filter: Optional[DiscrepancyStatus] = None,
        discrepancy_type: Optional[DiscrepancyType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DiscrepancyResponse]:
        query = db.query(TransferDiscrepancy).join(
            LinehaulManifest, TransferDiscrepancy.manifest_id == LinehaulManifest.id
        )
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                return []
            query = query.filter(TransferDiscrepancy.organization_id == current_user.organization_id)
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                query = query.filter(
                    (LinehaulManifest.origin_branch_id == current_user.branch_id)
                    | (LinehaulManifest.dest_branch_id == current_user.branch_id)
                )
        if manifest_id is not None:
            query = query.filter(TransferDiscrepancy.manifest_id == manifest_id)
        if status_filter is not None:
            query = query.filter(TransferDiscrepancy.status == status_filter)
        if discrepancy_type is not None:
            query = query.filter(TransferDiscrepancy.discrepancy_type == discrepancy_type)
        records = query.order_by(TransferDiscrepancy.reported_at.desc()).offset(skip).limit(limit).all()
        return [LinehaulService.to_discrepancy_response(d) for d in records]

    @staticmethod
    def resolve_discrepancy(
        db: Session, current_user: User, discrepancy_id: int, req: DiscrepancyResolveRequest
    ) -> DiscrepancyResponse:
        disc = db.query(TransferDiscrepancy).filter(TransferDiscrepancy.id == discrepancy_id).first()
        if not disc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discrepancy not found")
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id or disc.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discrepancy not found")
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                m = disc.manifest
                if m and current_user.branch_id not in (m.origin_branch_id, m.dest_branch_id):
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discrepancy not found")

        if disc.status == DiscrepancyStatus.RESOLVED and req.status != DiscrepancyStatus.RESOLVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resolved discrepancies cannot be reopened",
            )

        now = datetime.now(timezone.utc)
        disc.status = req.status
        disc.resolution_notes = req.resolution_notes
        broadcast_args: Optional[Dict[str, Any]] = None

        if req.status == DiscrepancyStatus.RESOLVED:
            disc.resolved_by_id = current_user.id
            disc.resolved_at = now
            if req.release_parcel_to_dest and disc.parcel and disc.manifest:
                if disc.parcel.delivery_status == ParcelStatus.ON_HOLD:
                    dest_name = (
                        disc.manifest.dest_branch.branch_name
                        if disc.manifest.dest_branch
                        else "Destination Hub"
                    )
                    ShipmentStateMachine.transition(
                        db=db,
                        current_user=current_user,
                        parcel=disc.parcel,
                        to_status=ParcelStatus.AT_DESTINATION_BRANCH,
                        remarks=f"Discrepancy resolved: {req.resolution_notes}",
                        location_name=dest_name,
                        branch_id=disc.manifest.dest_branch_id,
                        source="LINEHAUL_RESOLUTION",
                        commit=False,
                    )
                    broadcast_args = {
                        "tracking_number": disc.parcel.tracking_number,
                        "to_status": ParcelStatus.AT_DESTINATION_BRANCH,
                        "location": dest_name,
                        "remarks": f"Discrepancy resolved: {req.resolution_notes}",
                        "timestamp": now,
                    }

        db.commit()
        if broadcast_args:
            ShipmentStateMachine.broadcast_milestone(**broadcast_args)
        db.refresh(disc)
        return LinehaulService.to_discrepancy_response(disc)
