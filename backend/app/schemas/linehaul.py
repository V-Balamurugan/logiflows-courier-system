from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.enums import (
    BagStatus,
    DiscrepancySeverity,
    DiscrepancyStatus,
    DiscrepancyType,
    ManifestItemStatus,
    ManifestStatus,
)


def _clean_optional_code(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    cleaned = v.strip().upper()
    return cleaned or None


# --- Consolidation Bag Schemas ---


class BagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_branch_id: int
    dest_branch_id: int
    notes: Optional[str] = Field(None, max_length=1000)


class BagParcelAttachRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parcel_ids: List[int] = Field(default_factory=list)
    tracking_numbers: List[str] = Field(default_factory=list)


class BagSealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seal_number: Optional[str] = Field(None, min_length=3, max_length=64)

    @field_validator("seal_number")
    @classmethod
    def normalize_seal(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_code(v)


class BagDebagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(None, max_length=1000)


class BagParcelInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parcel_id: int
    tracking_number: str
    weight_kg: float
    delivery_status: str
    is_active: bool
    added_at: datetime
    debagged_at: Optional[datetime] = None


class BagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    bag_code: str
    origin_branch_id: int
    dest_branch_id: int
    origin_branch_name: Optional[str] = None
    dest_branch_name: Optional[str] = None
    manifest_id: Optional[int] = None
    seal_number: Optional[str] = None
    status: BagStatus
    total_weight_kg: float
    parcel_count: int
    notes: Optional[str] = None
    sealed_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    created_at: datetime
    parcels: List[BagParcelInfo] = Field(default_factory=list)


# --- Linehaul Manifest Schemas ---


class ManifestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_branch_id: int
    dest_branch_id: int
    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None
    seal_number: Optional[str] = Field(None, min_length=3, max_length=64)
    bag_ids: List[int] = Field(default_factory=list)
    parcel_ids: List[int] = Field(default_factory=list)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("seal_number")
    @classmethod
    def normalize_seal(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_code(v)


class ManifestAttachItemsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bag_ids: List[int] = Field(default_factory=list)
    parcel_ids: List[int] = Field(default_factory=list)
    tracking_numbers: List[str] = Field(default_factory=list)


class ManifestSealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seal_number: Optional[str] = Field(None, min_length=3, max_length=64)

    @field_validator("seal_number")
    @classmethod
    def normalize_seal(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_code(v)


class ManifestDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None
    seal_number: Optional[str] = Field(None, min_length=3, max_length=64)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("seal_number")
    @classmethod
    def normalize_seal(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_code(v)


class ManifestArriveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seal_intact: bool = True
    notes: Optional[str] = Field(None, max_length=1000)


class ManifestReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received_tracking_numbers: List[str] = Field(default_factory=list)
    damaged_tracking_numbers: List[str] = Field(default_factory=list)
    missing_tracking_numbers: List[str] = Field(default_factory=list)
    excess_tracking_numbers: List[str] = Field(default_factory=list)
    seal_intact: bool = True
    finalize: bool = True
    notes: Optional[str] = Field(None, max_length=1000)


class ManifestCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=3, max_length=500)


class ManifestItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parcel_id: int
    tracking_number: str
    weight_kg: float
    bag_id: Optional[int] = None
    bag_code: Optional[str] = None
    status: ManifestItemStatus
    is_active: bool
    scanned_out_at: Optional[datetime] = None
    scanned_in_at: Optional[datetime] = None
    remarks: Optional[str] = None


class DiscrepancyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_id: int
    parcel_id: Optional[int] = None
    tracking_number: Optional[str] = None
    bag_id: Optional[int] = None
    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity = DiscrepancySeverity.HIGH
    description: str = Field(..., min_length=5, max_length=2000)


class DiscrepancyResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DiscrepancyStatus = DiscrepancyStatus.RESOLVED
    resolution_notes: str = Field(..., min_length=3, max_length=2000)
    release_parcel_to_dest: bool = False


class DiscrepancyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    manifest_id: int
    manifest_number: Optional[str] = None
    parcel_id: Optional[int] = None
    tracking_number: Optional[str] = None
    bag_id: Optional[int] = None
    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity
    status: DiscrepancyStatus
    description: str
    resolution_notes: Optional[str] = None
    reported_by_id: Optional[int] = None
    reported_by_name: Optional[str] = None
    resolved_by_id: Optional[int] = None
    reported_at: datetime
    resolved_at: Optional[datetime] = None


class ManifestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    manifest_number: str
    origin_branch_id: int
    dest_branch_id: int
    origin_branch_name: Optional[str] = None
    dest_branch_name: Optional[str] = None
    vehicle_id: Optional[int] = None
    vehicle_number: Optional[str] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    seal_number: Optional[str] = None
    status: ManifestStatus
    expected_parcel_count: int
    received_parcel_count: int
    total_weight_kg: float
    notes: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    reconciled_at: Optional[datetime] = None
    created_at: datetime
    items: List[ManifestItemResponse] = Field(default_factory=list)
    bags: List[BagResponse] = Field(default_factory=list)
    discrepancies: List[DiscrepancyResponse] = Field(default_factory=list)


class ManifestReconciliationResponse(BaseModel):
    manifest: ManifestResponse
    received_count: int
    damaged_count: int
    missing_count: int
    excess_count: int
    discrepancies_created: int

