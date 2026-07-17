from __future__ import annotations

import threading
from typing import Dict


class HueDeviceStateStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: Dict[str, bool] = {}
        self._timers: Dict[str, threading.Timer] = {}

    def get(self, key: str) -> bool:
        with self._lock:
            return bool(self._states.get(key, False))

    def set(self, key: str, value: bool, reset_after: float = 0.0) -> None:
        timer = None
        with self._lock:
            previous = self._timers.pop(key, None)
            if previous:
                previous.cancel()
            self._states[key] = bool(value)
            if value and reset_after > 0:
                timer = threading.Timer(reset_after, self._reset, args=(key,))
                timer.daemon = True
                self._timers[key] = timer
        if timer:
            timer.start()

    def close(self) -> None:
        with self._lock:
            timers = list(self._timers.values())
            self._timers.clear()
        for timer in timers:
            timer.cancel()

    def _reset(self, key: str) -> None:
        with self._lock:
            self._states[key] = False
            self._timers.pop(key, None)
