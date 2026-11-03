from sqlalchemy.orm import Session
from app.models import (
    Base,
    Organization,
    Branch,
    User,
    Vehicle,
    Parcel,
    TrackingHistory,
    UserRole,
    OperatingStatus,
    VehicleType,
    VehicleStatus,
    ServiceType,
    PaymentStatus,
    ParcelStatus
)
from app.core.security import get_password_hash
from app.core.config import settings
from datetime import datetime, timezone, timedelta
import secrets


def init_db(db: Session) -> None:
    """Initializes schema and seeds baseline organization, branches, and admin accounts if empty."""
    # Check if SuperAdmin exists
    super_admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    if not super_admin:
        # Create default organization
        org = db.query(Organization).first()
        if not org:
            org = Organization(
                name="LogiFlows Global Logistics Ltd",
                code="LOGIFLOWS-GLOBAL",
                contact_email="ops@logiflows.com",
                contact_phone="+91 98765 43210",
                address="Logistics Park, Gateway Corridor, Mumbai, MH",
                is_active=True
            )
            db.add(org)
            db.flush()

        # Create branches
        branch_mumbai = db.query(Branch).filter(Branch.branch_code == "BOM-001").first()
        if not branch_mumbai:
            branch_mumbai = Branch(
                organization_id=org.id,
                branch_code="BOM-001",
                branch_name="Mumbai Central Sorting Hub",
                address="Sector 14, Andheri East Industrial Zone",
                pincode="400069",
                city="Mumbai",
                state="Maharashtra",
                country="India",
                contact_email="mumbai.hub@logiflows.com",
                contact_phone="+91 98765 00001",
                latitude=19.0760,
                longitude=72.8777,
                operating_status=OperatingStatus.ACTIVE,
                is_active=True
            )
            db.add(branch_mumbai)
            db.flush()

        branch_delhi = db.query(Branch).filter(Branch.branch_code == "DEL-001").first()
        if not branch_delhi:
            branch_delhi = Branch(
                organization_id=org.id,
                branch_code="DEL-001",
                branch_name="Delhi NCR Terminal Hub",
                address="Cargo Complex, IGI Airport Zone, New Delhi",
                pincode="110037",
                city="New Delhi",
                state="Delhi",
                country="India",
                contact_email="delhi.hub@logiflows.com",
                contact_phone="+91 98765 00002",
                latitude=28.6139,
                longitude=77.2090,
                operating_status=OperatingStatus.ACTIVE,
                is_active=True
            )
            db.add(branch_delhi)
            db.flush()

        branch_bengaluru = db.query(Branch).filter(Branch.branch_code == "BLR-001").first()
        if not branch_bengaluru:
            branch_bengaluru = Branch(
                organization_id=org.id,
                branch_code="BLR-001",
                branch_name="Bengaluru Tech Logistics Hub",
                address="Electronic City Phase 1, Bengaluru",
                pincode="560100",
                city="Bengaluru",
                state="Karnataka",
                country="India",
                contact_email="blr.hub@logiflows.com",
                contact_phone="+91 98765 00003",
                latitude=12.9716,
                longitude=77.5946,
                operating_status=OperatingStatus.ACTIVE,
                is_active=True
            )
            db.add(branch_bengaluru)
            db.flush()

        # Seed Users
        # 1. Super Admin
        admin = User(
            email=settings.FIRST_SUPERADMIN_EMAIL.lower(),
            hashed_password=get_password_hash(settings.FIRST_SUPERADMIN_PASSWORD),
            full_name="Super Administrator",
            phone="+91 98765 99999",
            role=UserRole.SUPER_ADMIN,
            is_active=True
        )
        db.add(admin)

        # 2. Org Admin
        org_admin = User(
            email="orgadmin@logiflows.com",
            hashed_password=get_password_hash("OrgAdmin@123"),
            full_name="Vikram Sethi (Org Admin)",
            phone="+91 98765 11111",
            role=UserRole.ORG_ADMIN,
            organization_id=org.id,
            is_active=True
        )
        db.add(org_admin)

        # 3. Branch Manager
        bm = User(
            email="manager.mumbai@logiflows.com",
            hashed_password=get_password_hash("Manager@123"),
            full_name="Priya Sharma (Mumbai Manager)",
            phone="+91 98765 22222",
            role=UserRole.BRANCH_MANAGER,
            organization_id=org.id,
            branch_id=branch_mumbai.id,
            is_active=True
        )
        db.add(bm)

        # 4. Delivery Agent
        agent = User(
            email="agent.rahul@logiflows.com",
            hashed_password=get_password_hash("Agent@123"),
            full_name="Rahul Verma (Delivery Agent)",
            phone="+91 98765 33333",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org.id,
            branch_id=branch_mumbai.id,
            is_active=True
        )
        db.add(agent)

        # 5. Customer
        cust = User(
            email="customer@example.com",
            hashed_password=get_password_hash("Customer@123"),
            full_name="Ananya Rao (Retail Customer)",
            phone="+91 98765 44444",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db.add(cust)

        # 6. Fleet Vehicles
        v1 = Vehicle(
            organization_id=org.id,
            branch_id=branch_mumbai.id,
            vehicle_number="MH-02-CB-4091",
            vehicle_type=VehicleType.VAN,
            model="Tata Winger Cargo Express",
            max_weight_kg=1200.0,
            max_volume_cbm=12.0,
            status=VehicleStatus.AVAILABLE,
            is_active=True
        )
        v2 = Vehicle(
            organization_id=org.id,
            branch_id=branch_delhi.id,
            vehicle_number="DL-01-AX-9912",
            vehicle_type=VehicleType.TRUCK,
            model="Eicher Pro 2049 Medium Cargo",
            max_weight_kg=2500.0,
            max_volume_cbm=24.0,
            status=VehicleStatus.AVAILABLE,
            is_active=True
        )
        db.add_all([v1, v2])

        db.commit()

