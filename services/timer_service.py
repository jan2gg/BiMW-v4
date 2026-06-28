# services/timer_service.py
from PyQt6.QtCore import QTimer


class TimerService:
    """Thin wrapper around QTimer with a cleaner API.
    stime: interval in seconds (float)."""

    def __init__(self, stime: float):
        self._timer = QTimer()
        self._timer.setInterval(int(stime * 1000))
        self._timer.setSingleShot(False)

    @property
    def timeout(self):
        """Expose the underlying Qt signal for .connect() calls."""
        return self._timer.timeout

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def set_interval(self, stime: float):
        self._timer.setInterval(int(stime * 1000))

    def is_active(self) -> bool:
        return self._timer.isActive()