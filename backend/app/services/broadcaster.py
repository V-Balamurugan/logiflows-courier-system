import asyncio
import json
from typing import Dict, Set, Any


class MilestoneBroadcaster:
    """
    In-memory async pub/sub broadcaster for real-time shipment milestone updates.
    Powers Server-Sent Events (SSE) streaming with multi-subscriber support per tracking number.
    """
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, tracking_number: str) -> asyncio.Queue:
        clean_tn = tracking_number.strip().upper()
        q = asyncio.Queue()
        if clean_tn not in self._subscribers:
            self._subscribers[clean_tn] = set()
        self._subscribers[clean_tn].add(q)
        return q

    def unsubscribe(self, tracking_number: str, q: asyncio.Queue) -> None:
        clean_tn = tracking_number.strip().upper()
        if clean_tn in self._subscribers:
            self._subscribers[clean_tn].discard(q)
            if not self._subscribers[clean_tn]:
                del self._subscribers[clean_tn]

    def broadcast(self, tracking_number: str, data: Dict[str, Any]) -> None:
        clean_tn = tracking_number.strip().upper()
        if clean_tn in self._subscribers:
            for q in list(self._subscribers[clean_tn]):
                try:
                    q.put_nowait(data)
                except Exception:
                    pass


milestone_broadcaster = MilestoneBroadcaster()


class RouteEventBroadcaster:
    """
    In-memory async pub/sub broadcaster for real-time route lifecycle domain events:
    ROUTE_DISPATCHED, DRIVER_ASSIGNED, ROUTE_STARTED, STOP_COMPLETED,
    DELIVERY_FAILED, ETA_CHANGED, ROUTE_DELAYED, ROUTE_REOPTIMIZED.
    """
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._all_events_subscribers: Set[asyncio.Queue] = set()

    def subscribe(self, route_id_or_code: str) -> asyncio.Queue:
        key = str(route_id_or_code).strip().upper()
        q = asyncio.Queue()
        if key not in self._subscribers:
            self._subscribers[key] = set()
        self._subscribers[key].add(q)
        return q

    def unsubscribe(self, route_id_or_code: str, q: asyncio.Queue) -> None:
        key = str(route_id_or_code).strip().upper()
        if key in self._subscribers:
            self._subscribers[key].discard(q)
            if not self._subscribers[key]:
                del self._subscribers[key]

    def subscribe_all(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._all_events_subscribers.add(q)
        return q

    def unsubscribe_all(self, q: asyncio.Queue) -> None:
        self._all_events_subscribers.discard(q)

    def broadcast(self, route_id_or_code: str, event_type: str, data: Dict[str, Any]) -> None:
        key = str(route_id_or_code).strip().upper()
        payload = {
            "event_type": event_type,
            "route_id": data.get("route_id"),
            "route_code": data.get("route_code"),
            "data": data,
        }
        # Route-specific subscribers
        if key in self._subscribers:
            for q in list(self._subscribers[key]):
                try:
                    q.put_nowait(payload)
                except Exception:
                    pass
        # Broadcasters to global subscribers (e.g. testing or monitoring)
        for q in list(self._all_events_subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                pass


route_event_broadcaster = RouteEventBroadcaster()

