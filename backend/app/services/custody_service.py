from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.parcel import Parcel
from app.models.custody import CustodyScan
from app.models.user import User
from app.models.enums import ScanType, ParcelStatus, UserRole
from app.schemas.custody import CustodyScanRequest, CustodyScanResponse
from app.services.state_machine import ShipmentStateMachine
from app.utils.qr_security import verify_secure_qr_payload


class CustodyService:
    SCAN_STATUS_MAPPING = {
        ScanType.PICKUP_VERIFICATION: ParcelStatus.PICKED_UP,
        ScanType.ORIGIN_INWARD: ParcelStatus.AT_ORIGIN_BRANCH,
        ScanType.HUB_OUTWARD: ParcelStatus.IN_TRANSIT,
        ScanType.DEST_INWARD: ParcelStatus.AT_DESTINATION_BRANCH,
        ScanType.OUT_FOR_DELIVERY: ParcelStatus.OUT_FOR_DELIVERY,
        ScanType.DELIVERY_CONFIRMATION: ParcelStatus.DELIVERED,
    }

    @staticmethod
    def process_scan(db: Session, current_user: User, req: CustodyScanRequest) -> CustodyScanResponse:
        raw_code = req.tracking_number.strip()
        branch_id = req.branch_id or current_user.branch_id

        # 1. Cryptographic QR Verification
        parcel_id = None
        try:
            verified = verify_secure_qr_payload(raw_code)
            tracking_number = verified["tracking_number"]
        except ValueError as e:
            # Audit log failed scan attempt
            if raw_code.startswith("LFQR."):
                parts = raw_code.split(".")
                if len(parts) >= 2:
                    p = db.query(Parcel).filter(Parcel.tracking_number == parts[1]).first()
                    if p:
                        parcel_id = p.id
            scan_failed = CustodyScan(
                parcel_id=parcel_id,
                scanned_by_id=current_user.id,
                branch_id=branch_id,
                scan_type=req.scan_type,
                is_successful=False,
                failure_reason=str(e),
                latitude=req.latitude,
                longitude=req.longitude,
                notes=req.notes
            )
            db.add(scan_failed)
            db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # 2. Lookup Parcel
        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
        if not parcel:
            scan_failed = CustodyScan(
                parcel_id=None,
                scanned_by_id=current_user.id,
                branch_id=branch_id,
                scan_type=req.scan_type,
                is_successful=False,
                failure_reason="Parcel not found",
                latitude=req.latitude,
                longitude=req.longitude,
                notes=req.notes
            )
            db.add(scan_failed)
            db.commit()
            raise HTTPException(status_code=404, detail="Parcel not found")

        # 3. Tenant Isolation
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                raise HTTPException(status_code=404, detail="Parcel not found")
            origin_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
            dest_org = parcel.dest_branch.organization_id if parcel.dest_branch else None
            if origin_org != current_user.organization_id and dest_org != current_user.organization_id:
                # Audit log cross-tenant failure
                scan_failed = CustodyScan(
                    parcel_id=parcel.id,
                    scanned_by_id=current_user.id,
                    branch_id=branch_id,
                    scan_type=req.scan_type,
                    is_successful=False,
                    failure_reason="Cross-tenant scan attempt rejected",
                    latitude=req.latitude,
                    longitude=req.longitude,
                    notes=req.notes
                )
                db.add(scan_failed)
                db.commit()
                raise HTTPException(status_code=404, detail="Parcel not found")

        # 4. Map Scan Type to Status
        new_status = CustodyService.SCAN_STATUS_MAPPING.get(req.scan_type)
        if not new_status:
            scan_failed = CustodyScan(
                parcel_id=parcel.id,
                scanned_by_id=current_user.id,
                branch_id=branch_id,
                scan_type=req.scan_type,
                is_successful=False,
                failure_reason="Unsupported scan type",
                latitude=req.latitude,
                longitude=req.longitude,
                notes=req.notes
            )
            db.add(scan_failed)
            db.commit()
            raise HTTPException(status_code=400, detail="Unsupported scan type")

        location_desc = f"Branch #{branch_id}" if branch_id else f"Scanned by {current_user.full_name}"

        # 5. Route Status Mutation Through Centralized State Machine
        try:
            ShipmentStateMachine.transition(
                db=db,
                current_user=current_user,
                parcel=parcel,
                to_status=new_status,
                remarks=f"Custody verified via QR Scan ({req.scan_type.value}). Notes: {req.notes or 'None'}",
                location_name=location_desc,
                branch_id=branch_id,
                latitude=req.latitude,
                longitude=req.longitude,
                source="QR_SCAN"
            )
        except HTTPException as exc:
            # Audit log failed scan attempt with transition error
            scan_failed = CustodyScan(
                parcel_id=parcel.id,
                scanned_by_id=current_user.id,
                branch_id=branch_id,
                scan_type=req.scan_type,
                is_successful=False,
                failure_reason=str(exc.detail),
                latitude=req.latitude,
                longitude=req.longitude,
                notes=req.notes
            )
            db.add(scan_failed)
            db.commit()
            raise

        # 6. Record Successful Custody Scan
        scan_record = CustodyScan(
            parcel_id=parcel.id,
            scanned_by_id=current_user.id,
            branch_id=branch_id,
            scan_type=req.scan_type,
            is_successful=True,
            failure_reason=None,
            latitude=req.latitude,
            longitude=req.longitude,
            notes=req.notes
        )
        db.add(scan_record)
        db.commit()
        db.refresh(scan_record)

        return CustodyScanResponse(
            id=scan_record.id,
            parcel_id=parcel.id,
            tracking_number=parcel.tracking_number,
            scan_type=scan_record.scan_type,
            new_parcel_status=new_status,
            scanned_by_id=current_user.id,
            scanned_by_name=current_user.full_name,
            branch_id=branch_id,
            notes=scan_record.notes,
            created_at=scan_record.created_at
        )

