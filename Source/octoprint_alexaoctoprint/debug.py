from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DebugEventLog:
    def __init__(self, max_events: int = 100) -> None:
        self._events: Deque[Dict[str, Any]] = deque(maxlen=max(10, int(max_events or 100)))

    def resize(self, max_events: int) -> None:
        maxlen = max(10, int(max_events or 100))
        current = list(self._events)[-maxlen:]
        self._events = deque(current, maxlen=maxlen)

    def record(self, event_type: str, message: str, **data: Any) -> Dict[str, Any]:
        event = {
            "time": utc_now_iso(),
            "type": event_type,
            "message": message,
            "data": data,
        }
        self._events.appendleft(event)
        return event

    def snapshot(self) -> List[Dict[str, Any]]:
        return list(self._events)
