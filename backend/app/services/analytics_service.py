from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.parcel import Parcel
from app.models.user import User
from app.models.branch import Branch
from app.models.vehicle import Vehicle
from app.models.assignment import DeliveryAssignment
from app.models.enums import ParcelStatus, UserRole, VehicleStatus, AssignmentStatus
from app.schemas.analytics import DashboardStatsResponse, StatusCount, BranchMetric


class AnalyticsService:
    @staticmethod
    def get_dashboard_stats(db: Session, current_user: User) -> DashboardStatsResponse:
        role = current_user.role

        parcel_q = db.query(Parcel)
        emp_q = db.query(User).filter(User.role.in_([UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER]))
        veh_q = db.query(Vehicle)

        if role == UserRole.CUSTOMER:
            parcel_q = parcel_q.filter(Parcel.customer_id == current_user.id)
        elif role == UserRole.DELIVERY_AGENT:
            # Deliveries assigned to this agent
            agent_assignments = db.query(DeliveryAssignment.parcel_id).filter(
                DeliveryAssignment.employee_id == current_user.id
            ).subquery()
            parcel_q = parcel_q.filter(Parcel.id.in_(agent_assignments))
        elif role == UserRole.BRANCH_MANAGER:
            parcel_q = parcel_q.filter(
                (Parcel.origin_branch_id == current_user.branch_id) |
                (Parcel.dest_branch_id == current_user.branch_id)
            )
            emp_q = emp_q.filter(User.branch_id == current_user.branch_id)
            veh_q = veh_q.filter(Vehicle.branch_id == current_user.branch_id)
        elif role == UserRole.ORG_ADMIN and current_user.organization_id:
            emp_q = emp_q.filter(User.organization_id == current_user.organization_id)
            veh_q = veh_q.filter(Vehicle.organization_id == current_user.organization_id)

        all_parcels = parcel_q.all()
        total_parcels = len(all_parcels)
        delivered_count = sum(1 for p in all_parcels if p.delivery_status == ParcelStatus.DELIVERED)
        failed_count = sum(1 for p in all_parcels if p.delivery_status == ParcelStatus.DELIVERY_FAILED)
        pending_count = total_parcels - delivered_count - failed_count

        active_employees = emp_q.filter(User.is_active == True).count()
        available_vehicles = veh_q.filter(Vehicle.status == VehicleStatus.AVAILABLE).count()

        success_rate = round((delivered_count / total_parcels * 100), 1) if total_parcels > 0 else 100.0

        # Status breakdown
        counts_dict: Dict[str, int] = {}
        for p in all_parcels:
            s_val = p.delivery_status.value
            counts_dict[s_val] = counts_dict.get(s_val, 0) + 1

        status_breakdown = [
            StatusCount(status=k, count=v) for k, v in counts_dict.items()
        ]

        # Branch performance (for Admin & Org Admin)
        branch_metrics = []
        if role in [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN]:
            b_query = db.query(Branch)
            if role == UserRole.ORG_ADMIN and current_user.organization_id:
                b_query = b_query.filter(Branch.organization_id == current_user.organization_id)
            
            for b in b_query.all():
                handled = db.query(Parcel).filter(
                    (Parcel.origin_branch_id == b.id) | (Parcel.dest_branch_id == b.id)
                ).count()
                deliv = db.query(Parcel).filter(
                    Parcel.dest_branch_id == b.id,
                    Parcel.delivery_status == ParcelStatus.DELIVERED
                ).count()
                branch_metrics.append(
                    BranchMetric(
                        branch_id=b.id,
                        branch_name=b.branch_name,
                        branch_code=b.branch_code,
                        parcels_handled=handled,
                        deliveries_completed=deliv
                    )
                )

        return DashboardStatsResponse(
            role=role.value,
            total_parcels=total_parcels,
            pending_deliveries=max(0, pending_count),
            delivered_parcels=delivered_count,
            failed_deliveries=failed_count,
            active_employees=active_employees,
            available_vehicles=available_vehicles,
            delivery_success_rate=success_rate,
            status_breakdown=status_breakdown,
            branch_performance=branch_metrics
        )

