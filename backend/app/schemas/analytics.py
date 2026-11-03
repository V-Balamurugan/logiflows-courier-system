from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import date


class MetricCard(BaseModel):
    title: str
    value: int | float
    change_percentage: Optional[float] = None
    trend: Optional[str] = None


class StatusCount(BaseModel):
    status: str
    count: int


class BranchMetric(BaseModel):
    branch_id: int
    branch_name: str
    branch_code: str
    parcels_handled: int
    deliveries_completed: int


class DashboardStatsResponse(BaseModel):
    role: str
    total_parcels: int
    pending_deliveries: int
    delivered_parcels: int
    failed_deliveries: int
    active_employees: int
    available_vehicles: int
    delivery_success_rate: float
    status_breakdown: List[StatusCount]
    branch_performance: Optional[List[BranchMetric]] = []
    recent_activities: Optional[List[Dict]] = []

