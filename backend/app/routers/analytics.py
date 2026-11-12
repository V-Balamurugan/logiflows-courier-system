import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.analytics import DashboardStatsResponse
from app.models.user import User
from app.models.parcel import Parcel
from app.models.enums import ParcelStatus, UserRole
from app.services.analytics_service import AnalyticsService
from app.dependencies.auth_deps import get_current_user, require_staff

router = APIRouter(prefix="/analytics", tags=["Analytics & Reports"])


@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns role-specific KPI summary cards, status breakdowns, and performance analytics."""
    return AnalyticsService.get_dashboard_stats(db, current_user)


@router.get("/export/csv")
def export_parcels_csv(
    status: Optional[ParcelStatus] = Query(None),
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Generates and downloads a CSV export of parcel records (tenant-scoped)."""
    query = db.query(Parcel)

    if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id:
        org_branch_ids = [b.id for b in current_user.organization.branches] if current_user.organization else []
        query = query.filter(
            (Parcel.origin_branch_id.in_(org_branch_ids)) |
            (Parcel.dest_branch_id.in_(org_branch_ids))
        )
    elif current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
        query = query.filter(
            (Parcel.origin_branch_id == current_user.branch_id) |
            (Parcel.dest_branch_id == current_user.branch_id)
        )

    if status:
        query = query.filter(Parcel.delivery_status == status)
    if branch_id:
        query = query.filter((Parcel.origin_branch_id == branch_id) | (Parcel.dest_branch_id == branch_id))

    parcels = query.order_by(Parcel.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Tracking Number",
        "Booking Date",
        "Status",
        "Service Type",
        "Sender Name",
        "Sender City",
        "Receiver Name",
        "Receiver City",
        "Weight (kg)",
        "Total Charge (INR)",
        "Payment Status"
    ])

    for p in parcels:
        row = [
            p.tracking_number,
            p.booking_date.strftime("%Y-%m-%d %H:%M"),
            p.delivery_status.value,
            p.service_type.value,
            p.sender_name,
            p.sender_city,
            p.receiver_name,
            p.receiver_city,
            p.weight_kg,
            p.total_charge,
            p.payment_status.value
        ]
        # Neutralize CSV formula injection (=, +, -, @, \t, \r) by prepending single quote
        sanitized_row = [
            f"'{cell}" if isinstance(cell, str) and cell and cell[0] in ("=", "+", "-", "@", "\t", "\r") else cell
            for cell in row
        ]
        writer.writerow(sanitized_row)

    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=logiflows_parcels_export.csv"
        }
    )

