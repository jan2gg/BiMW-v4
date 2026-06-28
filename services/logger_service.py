# services/logger_service.py
import csv
import datetime
import os


class LoggerService:
    """Centralised CSV logger. Replaces the scattered writerow/flush/fsync
    pattern from the old Controller.py."""

    def __init__(self, filepath: str = "log.txt"):
        self.filepath = filepath
        self._file = open(self.filepath, "a", newline="")
        self._writer = csv.writer(self._file, delimiter="\t")
        self._write_header()

    def _write_header(self):
        self._writer.writerow(["---", "---", "---"])
        self._writer.writerow(["Date", "Function", "Comment"])
        self.log("System", "Logger started")

    def log(self, context: str, message: str):
        """Write an info entry."""
        self._writer.writerow([datetime.datetime.now(), context, message])
        self._flush()

    def log_exception(self, context: str, exc: Exception):
        """Write an exception entry."""
        self._writer.writerow([datetime.datetime.now(), context, str(exc)])
        self._flush()

    def _flush(self):
        self._file.flush()
        os.fsync(self._file.fileno())

    def close(self):
        self._file.close()