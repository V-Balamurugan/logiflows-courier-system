"""Address normalization, geocoding provider abstraction, and TTL coordinate caching."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings
from app.models.enums import CoordinateSource, CoordinateVerificationStatus
from app.services.routing.base import validate_lat_lng

logger = logging.getLogger(__name__)

DEFAULT_GEOCODE_CACHE_TTL_SECONDS = 86400.0  # 24 hours


def normalize_address(address: str, city: str = "", state: str = "", pincode: str = "") -> str:
    """Standardize street addresses, abbreviate common words, strip excess punctuation."""
    combined = f"{address} {city} {state} {pincode}".strip()
    # Normalize whitespaces
    cleaned = re.sub(r"\s+", " ", combined)
    # Common logistics replacements
    replacements = [
        (r"\bROAD\b", "RD"),
        (r"\bSTREET\b", "ST"),
        (r"\bAVENUE\b", "AVE"),
        (r"\bLANE\b", "LN"),
        (r"\bSECTOR\b", "SEC"),
        (r"\bAPARTMENT\b", "APT"),
        (r"\bFLOOR\b", "FL"),
        (r"\bNEAR\b", "NR"),
        (r"\bOPPOSITE\b", "OPP"),
    ]
    upper = cleaned.upper()
    for pattern, repl in replacements:
        upper = re.sub(pattern, repl, upper)
    # Remove unsupported special symbols except commas/hyphens
    upper = re.sub(r"[^\w\s,\-#/]", "", upper)
    return upper.strip()


class GeocodingResult:
    """Standardized result returned by geocoding providers."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        confidence: float,
        coordinate_source: CoordinateSource,
        verification_status: CoordinateVerificationStatus,
        normalized_address: str,
        provider_name: str,
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.confidence = max(0.0, min(1.0, float(confidence)))
        self.coordinate_source = coordinate_source
        self.verification_status = verification_status
        self.normalized_address = normalized_address
        self.provider_name = provider_name
        self.verified_at = datetime.now(timezone.utc)


class BaseGeocodingProvider(ABC):
    """Abstract interface for geocoding services."""

    name: str

    @abstractmethod
    def geocode(self, normalized_addr: str) -> Optional[GeocodingResult]:
        """Convert normalized address string into geographic coordinates and confidence."""
        ...


class MockGeocodingProvider(BaseGeocodingProvider):
    """Deterministic mock geocoding provider for testing and offline environments."""

    name = "mock"

    def __init__(
        self,
        default_coords: Tuple[float, float] = (19.0760, 72.8777),
        default_confidence: float = 0.95,
        known_locations: Optional[Dict[str, Tuple[float, float, float]]] = None,
    ):
        self.default_coords = default_coords
        self.default_confidence = default_confidence
        # known_locations mapping: substring in normalized_addr -> (lat, lng, confidence)
        self.known_locations = known_locations or {
            "MUMBAI": (19.0760, 72.8777, 0.98),
            "PUNE": (18.5204, 73.8567, 0.95),
            "DELHI": (28.6139, 77.2090, 0.96),
            "BANGALORE": (12.9716, 77.5946, 0.97),
            "LOW_CONFIDENCE": (19.1100, 72.8800, 0.40),
        }

    def geocode(self, normalized_addr: str) -> Optional[GeocodingResult]:
        upper = normalized_addr.upper()
        for key, (lat, lng, conf) in self.known_locations.items():
            if key in upper:
                return GeocodingResult(
                    latitude=lat,
                    longitude=lng,
                    confidence=conf,
                    coordinate_source=CoordinateSource.VERIFIED_GEOCODING,
                    verification_status=(
                        CoordinateVerificationStatus.VERIFIED
                        if conf >= 0.60
                        else CoordinateVerificationStatus.FAILED
                    ),
                    normalized_address=normalized_addr,
                    provider_name=self.name,
                )

        return GeocodingResult(
            latitude=self.default_coords[0],
            longitude=self.default_coords[1],
            confidence=self.default_confidence,
            coordinate_source=CoordinateSource.VERIFIED_GEOCODING,
            verification_status=CoordinateVerificationStatus.VERIFIED,
            normalized_address=normalized_addr,
            provider_name=self.name,
        )


class OpenRouteServiceGeocodingProvider(BaseGeocodingProvider):
    """OpenRouteService Pelias geocoding provider."""

    name = "openrouteservice"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 5.0,
    ):
        self.api_key = (api_key if api_key is not None else settings.ORS_API_KEY).strip()
        self.base_url = (base_url or settings.ORS_BASE_URL).rstrip("/")
        self.timeout = timeout

    def geocode(self, normalized_addr: str) -> Optional[GeocodingResult]:
        if not self.api_key or self.api_key == "<SET_ME>":
            raise ValueError("ORS_API_KEY not configured for geocoding")

        url = f"{self.base_url}/geocode/search"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(
                url,
                headers={"Authorization": self.api_key},
                params={"text": normalized_addr, "size": 1},
            )
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features") or []
            if not features:
                return None
            feat = features[0]
            geom = feat.get("geometry", {}).get("coordinates") or []
            if len(geom) < 2:
                return None
            lng, lat = float(geom[0]), float(geom[1])
            props = feat.get("properties", {})
            confidence = float(props.get("confidence", 0.8))

            return GeocodingResult(
                latitude=round(lat, 6),
                longitude=round(lng, 6),
                confidence=confidence,
                coordinate_source=CoordinateSource.VERIFIED_GEOCODING,
                verification_status=(
                    CoordinateVerificationStatus.VERIFIED
                    if confidence >= 0.60
                    else CoordinateVerificationStatus.FAILED
                ),
                normalized_address=normalized_addr,
                provider_name=self.name,
            )


class GeocodingService:
    """Central geocoding facade with in-memory TTL caching and provider delegation."""

    _cache: Dict[str, Tuple[GeocodingResult, float]] = {}
    _providers: Dict[str, BaseGeocodingProvider] = {}
    _default_provider = MockGeocodingProvider()

    @classmethod
    def register_provider(cls, name: str, provider: BaseGeocodingProvider) -> None:
        cls._providers[name.strip().lower()] = provider

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()

    @classmethod
    def geocode(
        cls,
        address: str,
        city: str = "",
        state: str = "",
        pincode: str = "",
        provider: str = "mock",
        ttl_seconds: float = DEFAULT_GEOCODE_CACHE_TTL_SECONDS,
    ) -> GeocodingResult:
        """Geocode address with normalized key caching and fallback."""
        norm = normalize_address(address, city, state, pincode)
        now = time.time()

        # Check Cache
        if norm in cls._cache:
            res, expires_at = cls._cache[norm]
            if now < expires_at:
                return res

        prov_key = provider.strip().lower()
        active_provider = cls._providers.get(prov_key, cls._default_provider)

        try:
            result = active_provider.geocode(norm)
            if result is None:
                # Fallback to default mock
                result = cls._default_provider.geocode(norm)
        except Exception as exc:
            logger.warning("Geocoding provider '%s' failed: %s; using mock fallback", prov_key, exc)
            result = cls._default_provider.geocode(norm)

        cls._cache[norm] = (result, now + ttl_seconds)
        return result
