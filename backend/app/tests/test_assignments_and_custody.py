from app.core.config import settings


def test_public_tracking_and_qr_custody(client, customer_headers, branchmanager_headers, agent_headers):
    # 1. Book a parcel as customer
    branches = client.get(f"{settings.API_V1_STR}/branches", headers=customer_headers).json()
    b_origin = branches[0]["id"]
    b_dest = branches[1]["id"]

    booking_payload = {
        "origin_branch_id": b_origin,
        "dest_branch_id": b_dest,
        "sender_name": "Custody Sender",
        "sender_phone": "+91 91111 22222",
        "sender_address": "Origin Address",
        "sender_city": "Mumbai",
        "sender_state": "Maharashtra",
        "sender_pincode": "400001",
        "receiver_name": "Custody Receiver",
        "receiver_phone": "+91 93333 44444",
        "receiver_address": "Dest Address",
        "receiver_city": "Delhi",
        "receiver_state": "Delhi",
        "receiver_pincode": "110001",
        "weight_kg": 2.0,
        "length_cm": 20.0,
        "width_cm": 15.0,
        "height_cm": 10.0,
        "service_type": "EXPRESS"
    }
    booking = client.post(f"{settings.API_V1_STR}/parcels", json=booking_payload, headers=customer_headers).json()
    parcel_id = booking["id"]
    tracking_no = booking["tracking_number"]

    # 2. Check public tracking
    pub_resp = client.get(f"{settings.API_V1_STR}/tracking/public/{tracking_no}")
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()
    assert pub_data["tracking_number"] == tracking_no
    assert pub_data["status"] == "BOOKED"
    assert "sender_phone" not in pub_data  # Private information is sanitized!

    # 3. Process QR Scan for Pickup
    scan_pickup = {
        "tracking_number": tracking_no,
        "scan_type": "PICKUP_VERIFICATION",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "notes": "Picked up from customer doorstep"
    }
    scan_resp = client.post(f"{settings.API_V1_STR}/custody/scan", json=scan_pickup, headers=agent_headers)
    assert scan_resp.status_code == 201
    assert scan_resp.json()["new_parcel_status"] == "PICKED_UP"

    # 4. Assign delivery to agent
    emps = client.get(f"{settings.API_V1_STR}/employees", headers=branchmanager_headers).json()
    agent = next(e for e in emps if e["role"] == "DELIVERY_AGENT")

    assign_payload = {
        "parcel_id": parcel_id,
        "employee_id": agent["id"],
        "assignment_type": "LAST_MILE",
        "notes": "Deliver by 5 PM"
    }
    assign_resp = client.post(f"{settings.API_V1_STR}/assignments", json=assign_payload, headers=branchmanager_headers)
    assert assign_resp.status_code == 201
    assignment_id = assign_resp.json()["id"]

    # 5. Agent marks assignment completed
    complete_resp = client.put(
        f"{settings.API_V1_STR}/assignments/{assignment_id}/status",
        json={"status": "COMPLETED", "notes": "Handed over to receiver with OTP"},
        headers=agent_headers
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "COMPLETED"

    # 6. Verify parcel status is now DELIVERED
    updated_parcel = client.get(f"{settings.API_V1_STR}/parcels/{tracking_no}", headers=customer_headers).json()
    assert updated_parcel["delivery_status"] == "DELIVERED"

