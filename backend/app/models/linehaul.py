from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Text,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.enums import (
    ManifestStatus,
    BagStatus,
    ManifestItemStatus,
    DiscrepancyType,
    DiscrepancySeverity,
    DiscrepancyStatus,
)


class LinehaulManifest(Base):
    """Represents a branch-to-branch linehaul vehicle transfer manifest."""

    __tablename__ = "linehaul_manifests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    manifest_number = Column(String(64), unique=True, index=True, nullable=False)
    origin_branch_id = Column(
        Integer, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dest_branch_id = Column(
        Integer, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    vehicle_id = Column(
        Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    driver_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    seal_number = Column(String(64), nullable=True)
    status = Column(
        SQLEnum(ManifestStatus), default=ManifestStatus.DRAFT, nullable=False, index=True
    )
    expected_parcel_count = Column(Integer, default=0, nullable=False)
    received_parcel_count = Column(Integer, default=0, nullable=False)
    total_weight_kg = Column(Float, default=0.0, nullable=False)
    notes = Column(Text, nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    dispatched_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    dispatched_at = Column(DateTime, nullable=True)
    arrived_at = Column(DateTime, nullable=True)
    reconciled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    organization = relationship("Organization")
    origin_branch = relationship("Branch", foreign_keys=[origin_branch_id])
    dest_branch = relationship("Branch", foreign_keys=[dest_branch_id])
    vehicle = relationship("Vehicle")
    driver = relationship("User", foreign_keys=[driver_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    dispatched_by = relationship("User", foreign_keys=[dispatched_by_id])
    received_by = relationship("User", foreign_keys=[received_by_id])
    bags = relationship("ConsolidationBag", back_populates="manifest")
    items = relationship(
        "LinehaulManifestItem", back_populates="manifest", cascade="all, delete-orphan"
    )
    discrepancies = relationship(
        "TransferDiscrepancy", back_populates="manifest", cascade="all, delete-orphan"
    )


class ConsolidationBag(Base):
    """Represents a sealed consolidation bag grouping parcels for a shared destination branch."""

    __tablename__ = "consolidation_bags"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bag_code = Column(String(64), unique=True, index=True, nullable=False)
    origin_branch_id = Column(
        Integer, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dest_branch_id = Column(
        Integer, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    manifest_id = Column(
        Integer, ForeignKey("linehaul_manifests.id", ondelete="SET NULL"), nullable=True, index=True
    )
    seal_number = Column(String(64), nullable=True)
    status = Column(SQLEnum(BagStatus), default=BagStatus.OPEN, nullable=False, index=True)
    total_weight_kg = Column(Float, default=0.0, nullable=False)
    parcel_count = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sealed_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    organization = relationship("Organization")
    origin_branch = relationship("Branch", foreign_keys=[origin_branch_id])
    dest_branch = relationship("Branch", foreign_keys=[dest_branch_id])
    manifest = relationship("LinehaulManifest", back_populates="bags")
    created_by = relationship("User", foreign_keys=[created_by_id])
    bag_items = relationship("BagItem", back_populates="bag", cascade="all, delete-orphan")


class BagItem(Base):
    """Tracks parcel membership inside a consolidation bag with active uniqueness protection."""

    __tablename__ = "bag_items"
    __table_args__ = (
        UniqueConstraint("bag_id", "parcel_id", name="uq_bag_parcel"),
        Index(
            "uq_active_parcel_in_bag",
            "parcel_id",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    bag_id = Column(
        Integer, ForeignKey("consolidation_bags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parcel_id = Column(
        Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active = Column(Boolean, default=True, nullable=False)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    debagged_at = Column(DateTime, nullable=True)

    bag = relationship("ConsolidationBag", back_populates="bag_items")
    parcel = relationship("Parcel")


class LinehaulManifestItem(Base):
    """Links expected consignments (loose or bagged) to a linehaul manifest and tracks inward receipt."""

    __tablename__ = "linehaul_manifest_items"
    __table_args__ = (
        UniqueConstraint("manifest_id", "parcel_id", name="uq_manifest_parcel"),
        Index(
            "uq_active_parcel_on_manifest",
            "parcel_id",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    manifest_id = Column(
        Integer, ForeignKey("linehaul_manifests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parcel_id = Column(
        Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bag_id = Column(
        Integer, ForeignKey("consolidation_bags.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status = Column(
        SQLEnum(ManifestItemStatus),
        default=ManifestItemStatus.EXPECTED,
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    scanned_out_at = Column(DateTime, nullable=True)
    scanned_in_at = Column(DateTime, nullable=True)
    scanned_in_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    remarks = Column(Text, nullable=True)

    manifest = relationship("LinehaulManifest", back_populates="items")
    parcel = relationship("Parcel")
    bag = relationship("ConsolidationBag")
    scanned_in_by = relationship("User", foreign_keys=[scanned_in_by_id])


class TransferDiscrepancy(Base):
    """Audit record for missing, damaged, excess, or seal-tampered transfer incidents."""

    __tablename__ = "transfer_discrepancies"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    manifest_id = Column(
        Integer, ForeignKey("linehaul_manifests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parcel_id = Column(
        Integer, ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bag_id = Column(
        Integer, ForeignKey("consolidation_bags.id", ondelete="SET NULL"), nullable=True
    )
    discrepancy_type = Column(SQLEnum(DiscrepancyType), nullable=False, index=True)
    severity = Column(
        SQLEnum(DiscrepancySeverity), default=DiscrepancySeverity.HIGH, nullable=False
    )
    status = Column(
        SQLEnum(DiscrepancyStatus), default=DiscrepancyStatus.OPEN, nullable=False, index=True
    )
    description = Column(Text, nullable=False)
    resolution_notes = Column(Text, nullable=True)
    reported_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    organization = relationship("Organization")
    manifest = relationship("LinehaulManifest", back_populates="discrepancies")
    parcel = relationship("Parcel")
    bag = relationship("ConsolidationBag")
    reported_by = relationship("User", foreign_keys=[reported_by_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])

