import hmac
import hashlib
import secrets
import time
from typing import Dict, Any, Tuple
from app.core.config import settings
from app.utils.qr_generator import generate_qr_base64


def generate_secure_qr_payload(tracking_number: str, expires_in_days: int = 30) -> str:
    """
    Generates a cryptographically signed, unguessable QR payload bound to tracking number.
    Format: LFQR.<tracking_number>.<issued_at>.<expires_at>.<nonce>.<signature>
    """
    now = int(time.time())
    expires_at = now + (expires_in_days * 86400)
    nonce = secrets.token_hex(8)

    message = f"{tracking_number}:{now}:{expires_at}:{nonce}"
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:32]

    return f"LFQR.{tracking_number}.{now}.{expires_at}.{nonce}.{signature}"


def verify_secure_qr_payload(raw_payload: str) -> Dict[str, Any]:
    """
    Validates QR payload signature, expiration, and format.
    Raises ValueError on tampering, expiration, or malformed data.
    """
    cleaned = (raw_payload or "").strip()
    if not cleaned:
        raise ValueError("QR code content is empty")

    if cleaned.startswith("LFQR."):
        parts = cleaned.split(".")
        if len(parts) != 6:
            raise ValueError("Malformed QR code payload structure")

        prefix, tracking_number, issued_at_str, expires_at_str, nonce, signature = parts
        try:
            now = int(time.time())
            issued_at = int(issued_at_str)
            expires_at = int(expires_at_str)
        except ValueError:
            raise ValueError("Invalid timestamps in QR payload")

        if now > expires_at:
            raise ValueError("QR code has expired; request a new label")

        # Verify HMAC signature
        message = f"{tracking_number}:{issued_at}:{expires_at}:{nonce}"
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()[:32]

        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("Invalid QR code signature: potential tampering detected")

        return {
            "tracking_number": tracking_number,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "nonce": nonce,
            "is_signed": True,
            "raw": cleaned
        }

    # Fallback to plain tracking number if formatted like LF-YYYY-NNNNNN
    if cleaned.startswith("LF-"):
        return {
            "tracking_number": cleaned,
            "issued_at": None,
            "expires_at": None,
            "nonce": None,
            "is_signed": False,
            "raw": cleaned
        }

    raise ValueError(f"Unrecognized QR payload format: '{cleaned}'")


def generate_secure_qr_code(tracking_number: str) -> Tuple[str, str]:
    """Generates the signed payload and its Base64 PNG QR code."""
    payload = generate_secure_qr_payload(tracking_number)
    qr_data_uri = generate_qr_base64(payload)
    return payload, qr_data_uri

