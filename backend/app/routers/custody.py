from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.custody import CustodyScanRequest, CustodyScanResponse
from app.models.user import User
from app.models.custody import CustodyScan
from app.models.parcel import Parcel
from app.services.custody_service import CustodyService
from app.dependencies.auth_deps import require_staff

router = APIRouter(prefix="/custody", tags=["QR Custody"])


@router.post("/scan", response_model=CustodyScanResponse, status_code=status.HTTP_201_CREATED)
def process_qr_scan(
    req: CustodyScanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Processes employee QR scan, validates transition eligibility, and records chain-of-custody transfer."""
    return CustodyService.process_scan(db, current_user, req)


@router.get("/{tracking_number}/history")
def get_custody_history(
    tracking_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Retrieves full custody scan audit logs for a parcel."""
    parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
    if not parcel:
        return []
    
    scans = db.query(CustodyScan).filter(CustodyScan.parcel_id == parcel.id).order_by(CustodyScan.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "scan_type": s.scan_type.value,
            "scanned_by": s.scanned_by.full_name if s.scanned_by else None,
            "branch": s.branch.branch_name if s.branch else None,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "notes": s.notes,
            "created_at": s.created_at
        }
        for s in scans
    ]

