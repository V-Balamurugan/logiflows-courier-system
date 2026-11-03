from app.core.config import settings


def test_calculate_quote(client):
    payload = {
        "weight_kg": 2.5,
        "length_cm": 30.0,
        "width_cm": 20.0,
        "height_cm": 15.0,
        "service_type": "EXPRESS"
    }
    response = client.post(f"{settings.API_V1_STR}/parcels/quote", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["weight_kg"] == 2.5
    assert data["total_charge"] > 0
    assert data["estimated_delivery_days"] == 2


def test_book_parcel_and_verify_tracking(client, customer_headers):
    # Fetch branches
    branches = client.get(f"{settings.API_V1_STR}/branches", headers=customer_headers).json()
    b_origin = branches[0]["id"]
    b_dest = branches[1]["id"]

    payload = {
        "origin_branch_id": b_origin,
        "dest_branch_id": b_dest,
        "sender_name": "Rajesh Gupta",
        "sender_phone": "+91 98200 11223",
        "sender_email": "rajesh@example.com",
        "sender_address": "Flat 302, Sea View Towers",
        "sender_city": "Mumbai",
        "sender_state": "Maharashtra",
        "sender_pincode": "400001",
        "receiver_name": "Suresh Patel",
        "receiver_phone": "+91 98111 33445",
        "receiver_email": "suresh@example.com",
        "receiver_address": "Plot 12, Connaught Place",
        "receiver_city": "New Delhi",
        "receiver_state": "Delhi",
        "receiver_pincode": "110001",
        "weight_kg": 1.5,
        "length_cm": 25.0,
        "width_cm": 15.0,
        "height_cm": 10.0,
        "service_type": "STANDARD",
        "notes": "Fragile electronics"
    }

    response = client.post(f"{settings.API_V1_STR}/parcels", json=payload, headers=customer_headers)
    assert response.status_code == 201
    data = response.json()
    assert "tracking_number" in data
    assert data["tracking_number"].startswith("LF-")
    assert data["delivery_status"] == "BOOKED"
    assert "qr_code_data" in data

    tracking_no = data["tracking_number"]

    # Verify retrieval
    get_resp = client.get(f"{settings.API_V1_STR}/parcels/{tracking_no}", headers=customer_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["tracking_number"] == tracking_no

    # Verify PDF label generation
    pdf_resp = client.get(f"{settings.API_V1_STR}/parcels/{tracking_no}/label", headers=customer_headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 1000  # valid PDF binary content


def test_cancel_booked_parcel(client, customer_headers):
    branches = client.get(f"{settings.API_V1_STR}/branches", headers=customer_headers).json()
    payload = {
        "origin_branch_id": branches[0]["id"],
        "dest_branch_id": branches[1]["id"],
        "sender_name": "Cancel Sender",
        "sender_phone": "+91 99999 11111",
        "sender_address": "Test address",
        "sender_city": "Mumbai",
        "sender_state": "MH",
        "sender_pincode": "400001",
        "receiver_name": "Cancel Receiver",
        "receiver_phone": "+91 99999 22222",
        "receiver_address": "Test receiver address",
        "receiver_city": "Delhi",
        "receiver_state": "DL",
        "receiver_pincode": "110001",
        "weight_kg": 1.0,
        "length_cm": 10.0,
        "width_cm": 10.0,
        "height_cm": 10.0,
        "service_type": "STANDARD"
    }
    booking = client.post(f"{settings.API_V1_STR}/parcels", json=payload, headers=customer_headers).json()
    tracking_no = booking["tracking_number"]

    cancel_resp = client.post(
        f"{settings.API_V1_STR}/parcels/{tracking_no}/cancel",
        json={"cancellation_reason": "Item no longer needed"},
        headers=customer_headers
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["delivery_status"] == "CANCELLED"
    assert cancel_resp.json()["payment_status"] == "REFUNDED"

