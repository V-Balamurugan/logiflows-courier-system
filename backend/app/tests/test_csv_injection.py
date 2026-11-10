import pytest
import csv
import io
from app.models.parcel import Parcel
from app.models.enums import ParcelStatus, ServiceType, PaymentStatus
from datetime import datetime, timezone


def test_csv_formula_injection_neutralized(client, orgadmin_headers, db_session):
    # Retrieve test branch IDs
    from app.models.branch import Branch
    branch = db_session.query(Branch).first()
    assert branch is not None

    # Inject parcel with formula injection payloads in text fields
    malicious_parcel = Parcel(
        tracking_number="LOGI-FORMULA-TEST",
        customer_id=None,
        origin_branch_id=branch.id,
        dest_branch_id=branch.id,
        sender_name="=cmd|'/C calc'!A0",
        sender_phone="+919999999999",
        sender_email="test@exploit.com",
        sender_address="123 Malicious St",
        sender_city="@SUM(1+1)",
        sender_state="State",
        sender_pincode="123456",
        receiver_name="+1234567890",
        receiver_phone="+918888888888",
        receiver_email="receiver@test.com",
        receiver_address="456 Target Rd",
        receiver_city="-calc|'arg'!B2",
        receiver_state="State",
        receiver_pincode="654321",
        weight_kg=2.5,
        length_cm=10.0,
        width_cm=10.0,
        height_cm=10.0,
        volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD,
        base_charge=50.0,
        weight_charge=20.0,
        service_charge=0.0,
        tax_amount=12.6,
        total_charge=82.6,
        payment_status=PaymentStatus.PENDING,
        delivery_status=ParcelStatus.BOOKED,
        booking_date=datetime.now(timezone.utc),
        notes="\tTAB_INJECTION"
    )
    db_session.add(malicious_parcel)
    db_session.commit()

    # Request CSV export
    response = client.get("/api/v1/analytics/export/csv", headers=orgadmin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    content = response.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    # Find the row for LOGI-FORMULA-TEST
    target_row = next((r for r in rows if len(r) > 0 and r[0] == "LOGI-FORMULA-TEST"), None)
    assert target_row is not None, "Exported CSV must contain the injected parcel record"

    # Verify each sensitive cell is neutralized with leading single quote
    sender_name = target_row[4]
    sender_city = target_row[5]
    receiver_name = target_row[6]
    receiver_city = target_row[7]

    assert sender_name.startswith("'="), f"Expected '= neutralized, got: {sender_name}"
    assert sender_city.startswith("'@"), f"Expected '@ neutralized, got: {sender_city}"
    assert receiver_name.startswith("'+"), f"Expected '+ neutralized, got: {receiver_name}"
    assert receiver_city.startswith("'-"), f"Expected '- neutralized, got: {receiver_city}"
