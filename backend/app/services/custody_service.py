from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.parcel import Parcel
from app.models.custody import CustodyScan
from app.models.tracking import TrackingHistory
from app.models.user import User
from app.models.enums import ScanType, ParcelStatus
from app.schemas.custody import CustodyScanRequest, CustodyScanResponse


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
        parcel = db.query(Parcel).filter(Parcel.tracking_number == req.tracking_number.strip()).first()
        if not parcel:
            raise HTTPException(status_code=404, detail=f"No parcel found with tracking # {req.tracking_number}")

        if parcel.delivery_status in [ParcelStatus.DELIVERED, ParcelStatus.CANCELLED]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot scan parcel with status '{parcel.delivery_status.value}'"
            )

        new_status = CustodyService.SCAN_STATUS_MAPPING.get(req.scan_type)
        if not new_status:
            raise HTTPException(status_code=400, detail="Unsupported scan type")

        now = datetime.now(timezone.utc)
        parcel.delivery_status = new_status
        if new_status == ParcelStatus.DELIVERED:
            parcel.actual_delivery_date = now

        branch_id = req.branch_id or current_user.branch_id
        location_desc = f"Branch #{branch_id}" if branch_id else f"Scanned by {current_user.full_name}"

        # Record Custody Scan
        scan_record = CustodyScan(
            parcel_id=parcel.id,
            scanned_by_id=current_user.id,
            branch_id=branch_id,
            scan_type=req.scan_type,
            latitude=req.latitude,
            longitude=req.longitude,
            notes=req.notes
        )
        db.add(scan_record)

        # Record Tracking History
        th = TrackingHistory(
            parcel_id=parcel.id,
            status=new_status,
            branch_id=branch_id,
            employee_id=current_user.id,
            location_name=location_desc,
            latitude=req.latitude,
            longitude=req.longitude,
            remarks=f"Custody verified via QR Scan ({req.scan_type.value}). Notes: {req.notes or 'None'}"
        )
        db.add(th)
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

