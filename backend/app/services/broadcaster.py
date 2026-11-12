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
