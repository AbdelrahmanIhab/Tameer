"""
Tameer — Debug Event Bus
=========================
Thread-safe rolling buffer of pipeline events for the developer dashboard.
Any thread (MQTT, InfluxDB) can call emit(); the async SSE endpoint polls via
get_events_since(cursor).
"""

from __future__ import annotations
import threading
from collections import deque
from datetime import datetime, timezone

_lock:   threading.Lock       = threading.Lock()
_events: deque[dict]          = deque(maxlen=500)


def emit(event: dict) -> None:
    with _lock:
        _events.append(event)


def get_events_since(cursor: int) -> list[dict]:
    with _lock:
        all_events = list(_events)
    return all_events[cursor:]


def get_all_events() -> list[dict]:
    with _lock:
        return list(_events)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
