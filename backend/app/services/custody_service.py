import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.parcel import Parcel
from app.models.custody import CustodyScan
from app.models.user import User
from app.models.enums import ScanType, ParcelStatus, UserRole
from app.schemas.custody import (
    CustodyScanRequest,
    CustodyScanResponse,
    ChainVerificationRecord,
    CustodyChainVerificationResponse
)
from app.services.state_machine import ShipmentStateMachine
from app.utils.qr_security import verify_secure_qr_payload


class CustodyService:
    SCAN_STATUS_MAPPING = {
        ScanType.PICKUP_VERIFICATION: ParcelStatus.PICKED_UP,
        ScanType.ORIGIN_INWARD: ParcelStatus.AT_ORIGIN_BRANCH,
        ScanType.HUB_OUTWARD: ParcelStatus.IN_TRANSIT,
        ScanType.DEST_INWARD: ParcelStatus.AT_DESTINATION_BRANCH,
        ScanType.OUT_FOR_DELIVERY: ParcelStatus.OUT_FOR_DELIVERY,
        ScanType.DELIVERY_CONFIRMATION: ParcelStatus.DELIVERED,
    }

    @staticmethod
    def process_scan(db: Session, current_user: User, req: CustodyScanRequest) -> CustodyScanResponse:
        raw_code = req.tracking_number.strip()
        branch_id = req.branch_id or current_user.branch_id

        # 1. Cryptographic QR Verification
        parcel_id = None
        try:
            verified = verify_secure_qr_payload(raw_code)
            tracking_number = verified["tracking_number"]
        except ValueError as e:
            # Audit log failed scan attempt
            if raw_code.startswith("LFQR."):
                parts = raw_code.split(".")
                if len(parts) >= 2:
                    p = db.query(Parcel).filter(Parcel.tracking_number == parts[1]).first()
                    if p:
                        parcel_id = p.id
            scan_failed = CustodyScan(
                parcel_id=parcel_id,
                scanned_by_id=current_user.id,
                branch_id=branch_id,
                scan_type=req.scan_type,
                is_successful=False,
                failure_reason=str(e),
                latitude=req.latitude,
                longitude=req.longitude,
                notes=req.notes
            )
            db.add(scan_failed)
            db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # 2. Lookup Parcel
        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")

        # 3. Tenant Isolation
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                raise HTTPException(status_code=404, detail="Parcel not found")
            origin_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
            dest_org = parcel.dest_branch.organization_id if parcel.dest_branch else None
            if origin_org != current_user.organization_id and dest_org != current_user.organization_id:
                # Audit log cross-tenant failure
                scan_failed = CustodyScan(
                    parcel_id=parcel.id,
                    scanned_by_id=current_user.id,
                    branch_id=branch_id,
                    scan_type=req.scan_type,
                    is_successful=False,
                    failure_reason="Cross-tenant scan attempt rejected",
                    latitude=req.latitude,
                    longitude=req.longitude,
                    notes=req.notes
                )
                db.add(scan_failed)
                db.commit()
                raise HTTPException(status_code=404, detail="Parcel not found")

        # 4. Map Scan Type to Status
        new_status = CustodyService.SCAN_STATUS_MAPPING.get(req.scan_type)
        if not new_status:
            scan_failed = CustodyScan(
                parcel_id=parcel.id,
                scanned_by_id=current_user.id,
                branch_id=branch_id,
                scan_type=req.scan_type,
                is_successful=False,
                failure_reason="Unsupported scan type",
                latitude=req.latitude,
                longitude=req.longitude,
                notes=req.notes
            )
            db.add(scan_failed)
            db.commit()
            raise HTTPException(status_code=400, detail="Unsupported scan type")

        location_desc = f"Branch #{branch_id}" if branch_id else f"Scanned by {current_user.full_name}"

        # 5. Route Status Mutation Through Centralized State Machine
        try:
            ShipmentStateMachine.transition(
                db=db,
                current_user=current_user,
                parcel=parcel,
                to_status=new_status,
                remarks=f"Custody verified via QR Scan ({req.scan_type.value}). Notes: {req.notes or 'None'}",
                location_name=location_desc,
                branch_id=branch_id,
                latitude=req.latitude,
                longitude=req.longitude,
                source="QR_SCAN"
            )
        except HTTPException as exc:
            # Audit log failed scan attempt with transition error
            scan_failed = CustodyScan(
                parcel_id=parcel.id,
                scanned_by_id=current_user.id,
                branch_id=branch_id,
                scan_type=req.scan_type,
                is_successful=False,
                failure_reason=str(exc.detail),
                latitude=req.latitude,
                longitude=req.longitude,
                notes=req.notes
            )
            db.add(scan_failed)
            db.commit()
            raise

        # 6. Cryptographic Chain-of-Custody Hash Linking
        latest_scan = (
            db.query(CustodyScan)
            .filter(CustodyScan.parcel_id == parcel.id, CustodyScan.is_successful == True)
            .order_by(CustodyScan.created_at.desc(), CustodyScan.id.desc())
            .first()
        )
        prev_hash = latest_scan.record_hash if (latest_scan and latest_scan.record_hash) else "GENESIS_CUSTODY_HASH"
        scan_time = req.timestamp or datetime.now(timezone.utc)
        if not scan_time.tzinfo:
            scan_time = scan_time.replace(tzinfo=timezone.utc)
        iso_timestamp = scan_time.astimezone(timezone.utc).isoformat()
        record_payload = f"{prev_hash}:{parcel.id}:{req.scan_type.value}:{current_user.id}:{branch_id}:{iso_timestamp}"
        rec_hash = hashlib.sha256(record_payload.encode("utf-8")).hexdigest()

        # Record Successful Custody Scan
        scan_record = CustodyScan(
            parcel_id=parcel.id,
            scanned_by_id=current_user.id,
            branch_id=branch_id,
            scan_type=req.scan_type,
            is_successful=True,
            failure_reason=None,
            latitude=req.latitude,
            longitude=req.longitude,
            notes=req.notes,
            previous_hash=prev_hash,
            record_hash=rec_hash,
            created_at=scan_time
        )
        db.add(scan_record)
        db.commit()
        db.refresh(scan_record)

        return CustodyScanResponse(
            id=scan_record.id,
            parcel_id=parcel.id,
            tracking_number=parcel.tracking_number,
            scan_type=scan_record.scan_type,
            new_parcel_status=new_status,
            scanned_by_id=current_user.id,
            scanned_by_name=current_user.full_name,
            branch_id=branch_id,
            notes=scan_record.notes,
            previous_hash=scan_record.previous_hash,
            record_hash=scan_record.record_hash,
            created_at=scan_record.created_at
        )

    @staticmethod
    def verify_custody_chain(
        db: Session,
        current_user: User,
        tracking_number: str
    ) -> CustodyChainVerificationResponse:
        """
        Cryptographically verifies the complete custody audit chain for a parcel.
        Ensures zero tampering, unbroken hash sequence, and data integrity.
        """
        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number.strip()).first()
        if not parcel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

        # Tenant / Owner isolation
        if current_user.role == UserRole.CUSTOMER:
            if parcel.customer_id != current_user.id and parcel.sender_email != current_user.email:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
        elif current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
            origin_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
            dest_org = parcel.dest_branch.organization_id if parcel.dest_branch else None
            if origin_org != current_user.organization_id and dest_org != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

        scans = (
            db.query(CustodyScan)
            .filter(CustodyScan.parcel_id == parcel.id)
            .order_by(CustodyScan.created_at.asc(), CustodyScan.id.asc())
            .all()
        )

        chain_records = []
        expected_prev = "GENESIS_CUSTODY_HASH"
        tamper_detected = False

        for scan in scans:
            if not scan.is_successful:
                chain_records.append(ChainVerificationRecord(
                    id=scan.id,
                    scan_type=scan.scan_type,
                    is_successful=False,
                    failure_reason=scan.failure_reason,
                    scanned_by_id=scan.scanned_by_id,
                    scanned_by_name=scan.scanned_by.full_name if scan.scanned_by else None,
                    branch_id=scan.branch_id,
                    created_at=scan.created_at,
                    previous_hash=scan.previous_hash,
                    record_hash=scan.record_hash,
                    computed_hash=None,
                    verified=True
                ))
                continue

            ts = scan.created_at
            if not ts.tzinfo:
                ts = ts.replace(tzinfo=timezone.utc)
            iso_timestamp = ts.astimezone(timezone.utc).isoformat()
            expected_payload = f"{expected_prev}:{parcel.id}:{scan.scan_type.value}:{scan.scanned_by_id}:{scan.branch_id}:{iso_timestamp}"
            computed = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
            is_record_valid = (scan.previous_hash == expected_prev) and (scan.record_hash == computed)

            if not is_record_valid:
                tamper_detected = True

            chain_records.append(ChainVerificationRecord(
                id=scan.id,
                scan_type=scan.scan_type,
                is_successful=True,
                failure_reason=None,
                scanned_by_id=scan.scanned_by_id,
                scanned_by_name=scan.scanned_by.full_name if scan.scanned_by else None,
                branch_id=scan.branch_id,
                created_at=scan.created_at,
                previous_hash=scan.previous_hash,
                record_hash=scan.record_hash,
                computed_hash=computed,
                verified=is_record_valid
            ))
            expected_prev = scan.record_hash

        return CustodyChainVerificationResponse(
            tracking_number=parcel.tracking_number,
            parcel_id=parcel.id,
            total_scans=len(scans),
            is_valid=not tamper_detected,
            tamper_detected=tamper_detected,
            chain=chain_records
        )

