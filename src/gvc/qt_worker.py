from __future__ import annotations

from threading import Event
from typing import Callable

from PySide6.QtCore import QObject, Signal


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[object], None]
WorkerFn = Callable[[Event, ProgressCallback, StatusCallback], None]


class Worker(QObject):
    progress = Signal(int)
    status = Signal(object)
    done = Signal(bool)

    def __init__(self, fn: WorkerFn, cancel_event: Event):
        super().__init__()
        self._fn = fn
        self._cancel_event = cancel_event

    def run(self) -> None:
        try:
            self._fn(self._cancel_event, self.progress.emit, self.status.emit)
            self.done.emit(True)
        except Exception as exc:
            if self._cancel_event.is_set() or "cancel" in str(exc).lower():
                self.status.emit({"key": "cancelled", "kwargs": {}})
            else:
                self.status.emit({"error": str(exc)})
            self.done.emit(False)
