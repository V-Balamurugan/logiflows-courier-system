from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth_deps import require_branch_manager_or_higher, require_staff
from app.models.enums import BagStatus, DiscrepancyStatus, DiscrepancyType, ManifestStatus
from app.models.user import User
from app.schemas.linehaul import (
    BagCreate,
    BagDebagRequest,
    BagParcelAttachRequest,
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
    ManifestReconcileRequest,
    ManifestReconciliationResponse,
    ManifestResponse,
    ManifestSealRequest,
)
from app.services.linehaul_service import LinehaulService

router = APIRouter(prefix="/linehaul", tags=["Linehaul Transfers"])


# --- Consolidation Bags ---


@router.post("/bags", response_model=BagResponse, status_code=status.HTTP_201_CREATED)
def create_bag(
    data: BagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Creates an open consolidation bag for a branch-to-branch corridor."""
    return LinehaulService.create_bag(db, current_user, data)


@router.get("/bags", response_model=List[BagResponse])
def list_bags(
    status_filter: Optional[BagStatus] = Query(None, alias="status"),
    origin_branch_id: Optional[int] = Query(None),
    dest_branch_id: Optional[int] = Query(None),
    unassigned_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Lists tenant-scoped consolidation bags."""
    return LinehaulService.list_bags(
        db,
        current_user,
        status_filter=status_filter,
        origin_branch_id=origin_branch_id,
        dest_branch_id=dest_branch_id,
        unassigned_only=unassigned_only,
        skip=skip,
        limit=limit,
    )


@router.get("/bags/{bag_id}", response_model=BagResponse)
def get_bag(
    bag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Retrieves a consolidation bag with nested parcels."""
    return LinehaulService.get_bag(db, current_user, bag_id)


@router.post("/bags/{bag_id}/parcels", response_model=BagResponse)
def attach_parcels_to_bag(
    bag_id: int,
    req: BagParcelAttachRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Adds eligible AT_ORIGIN_BRANCH parcels to an OPEN consolidation bag."""
    return LinehaulService.attach_parcels_to_bag(db, current_user, bag_id, req)


@router.delete("/bags/{bag_id}/parcels/{parcel_id}", response_model=BagResponse)
def remove_parcel_from_bag(
    bag_id: int,
    parcel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Removes a parcel from an OPEN consolidation bag."""
    return LinehaulService.remove_parcel_from_bag(db, current_user, bag_id, parcel_id)


@router.post("/bags/{bag_id}/seal", response_model=BagResponse)
def seal_bag(
    bag_id: int,
    req: BagSealRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Seals a non-empty consolidation bag with a tamper-evident seal number."""
    return LinehaulService.seal_bag(db, current_user, bag_id, req)


@router.post("/bags/{bag_id}/debag", response_model=BagResponse)
def debag_bag(
    bag_id: int,
    req: BagDebagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """De-bags a RECEIVED consolidation bag at the destination hub."""
    return LinehaulService.debag_at_destination(db, current_user, bag_id, req)


# --- Linehaul Transfer Manifests ---


@router.post("/manifests", response_model=ManifestResponse, status_code=status.HTTP_201_CREATED)
def create_manifest(
    data: ManifestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Creates a branch-to-branch linehaul transfer manifest."""
    return LinehaulService.create_manifest(db, current_user, data)


@router.get("/manifests", response_model=List[ManifestResponse])
def list_manifests(
    status_filter: Optional[ManifestStatus] = Query(None, alias="status"),
    origin_branch_id: Optional[int] = Query(None),
    dest_branch_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Lists linehaul manifests visible to the caller's tenant/branch/driver scope."""
    return LinehaulService.list_manifests(
        db,
        current_user,
        status_filter=status_filter,
        origin_branch_id=origin_branch_id,
        dest_branch_id=dest_branch_id,
        skip=skip,
        limit=limit,
    )


@router.get("/manifests/{manifest_id}", response_model=ManifestResponse)
def get_manifest(
    manifest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Retrieves full manifest details, items, bags, and discrepancies."""
    return LinehaulService.get_manifest(db, current_user, manifest_id)


@router.post("/manifests/{manifest_id}/items", response_model=ManifestResponse)
def attach_manifest_items(
    manifest_id: int,
    req: ManifestAttachItemsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Attaches sealed bags or loose parcels to a DRAFT manifest."""
    return LinehaulService.attach_items_to_manifest(db, current_user, manifest_id, req)


@router.delete("/manifests/{manifest_id}/items/parcels/{parcel_id}", response_model=ManifestResponse)
def remove_manifest_parcel(
    manifest_id: int,
    parcel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Removes a loose parcel from a DRAFT manifest."""
    return LinehaulService.remove_parcel_from_manifest(db, current_user, manifest_id, parcel_id)


@router.delete("/manifests/{manifest_id}/items/bags/{bag_id}", response_model=ManifestResponse)
def detach_manifest_bag(
    manifest_id: int,
    bag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Detaches a consolidation bag and its parcels from a DRAFT manifest."""
    return LinehaulService.detach_bag_from_manifest(db, current_user, manifest_id, bag_id)


@router.post("/manifests/{manifest_id}/seal", response_model=ManifestResponse)
def seal_manifest(
    manifest_id: int,
    req: ManifestSealRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Locks manifest contents with a seal number prior to dispatch."""
    return LinehaulService.seal_manifest(db, current_user, manifest_id, req)


@router.post("/manifests/{manifest_id}/dispatch", response_model=ManifestResponse)
def dispatch_manifest(
    manifest_id: int,
    req: ManifestDispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Atomically locks the linehaul vehicle and transitions all parcels to IN_TRANSIT."""
    return LinehaulService.dispatch_manifest(db, current_user, manifest_id, req)


@router.post("/manifests/{manifest_id}/arrive", response_model=ManifestResponse)
def arrive_manifest(
    manifest_id: int,
    req: ManifestArriveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Records arrival of an IN_TRANSIT manifest at the destination branch and frees the vehicle."""
    return LinehaulService.mark_arrived(db, current_user, manifest_id, req)


@router.post("/manifests/{manifest_id}/reconcile", response_model=ManifestReconciliationResponse)
def reconcile_manifest(
    manifest_id: int,
    req: ManifestReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Scans inward parcels, flags missing/damaged/excess items, and reconciles manifest."""
    return LinehaulService.reconcile_manifest(db, current_user, manifest_id, req)


@router.post("/manifests/{manifest_id}/cancel", response_model=ManifestResponse)
def cancel_manifest(
    manifest_id: int,
    req: ManifestCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Cancels a DRAFT or SEALED manifest and releases its bags/parcels."""
    return LinehaulService.cancel_manifest(db, current_user, manifest_id, req)


# --- Discrepancy Management ---


@router.get("/discrepancies", response_model=List[DiscrepancyResponse])
def list_discrepancies(
    manifest_id: Optional[int] = Query(None),
    status_filter: Optional[DiscrepancyStatus] = Query(None, alias="status"),
    discrepancy_type: Optional[DiscrepancyType] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Lists transfer discrepancy incidents scoped by tenant and branch."""
    return LinehaulService.list_discrepancies(
        db,
        current_user,
        manifest_id=manifest_id,
        status_filter=status_filter,
        discrepancy_type=discrepancy_type,
        skip=skip,
        limit=limit,
    )


@router.post("/discrepancies", response_model=DiscrepancyResponse, status_code=status.HTTP_201_CREATED)
def report_discrepancy(
    data: DiscrepancyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Reports a shortage, damage, excess parcel, or broken seal incident on a manifest."""
    return LinehaulService.create_discrepancy(db, current_user, data)


@router.patch("/discrepancies/{discrepancy_id}", response_model=DiscrepancyResponse)
def resolve_discrepancy(
    discrepancy_id: int,
    req: DiscrepancyResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Updates or resolves an open transfer discrepancy."""
    return LinehaulService.resolve_discrepancy(db, current_user, discrepancy_id, req)

