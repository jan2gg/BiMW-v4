# controllers/data_controller.py
import csv
import datetime
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget
from services.logger_service import LoggerService


class DataController:
    """Manages all file operations: save dialogs, CSV writing."""

    def __init__(self, parent_widget: QWidget, logger: LoggerService):
        self._parent = parent_widget
        self._log = logger
        self._phase_file = None
        self._phase_writer = None
        self._current_data_file = None
        self.data_saved: bool = False

    # ----------------------------------------------------------------- dialogs
    def open_save_dialog(self, default_name: str = "measurePhase.DAT") -> str:
        filepath, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Save Phase Data",
            default_name,
            "Data files (*.DAT);;All files (*)"
        )
        return filepath

    def show_warning_save(self, message: str) -> QMessageBox.StandardButton:
        return QMessageBox.warning(
            self._parent,
            "Unsaved Data",
            message,
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Close,
        )

    def show_critical(self, message: str):
        QMessageBox.critical(self._parent, "Error", message)

    # ----------------------------------------------------------- phase file I/O
    def open_phase_file(self, filepath: str) -> bool:
        """Open a new DAT file for streaming phase data.
        Returns True on success."""
        try:
            if self._phase_file:
                self._phase_file.close()
            self._phase_file = open(filepath, "w", newline="")
            self._phase_writer = csv.writer(self._phase_file, delimiter="\t")
            self._phase_writer.writerow([
                "Time(s)", "Phase1(rad)", "Phase2(rad)", "Phase3(rad)",
                "Phase4(rad)", "Phase5(rad)", "Phase6(rad)", "Phase7(rad)",
            ])
            self.data_saved = True
            return True
        except Exception as exc:
            self._log.log_exception("DataController.open_phase_file", exc)
            self.data_saved = False
            return False

    def write_phase_row(self, time_values: list, phase_arrays: list):
        """Append two rows (start + end of current window) to the phase file."""
        if not self._phase_writer or not self.data_saved:
            return
        try:
            n = len(phase_arrays[0]) if phase_arrays else 0
            if n < 2:
                return
            for row_idx in [n - 2, n - 1]:
                row = [round(time_values[row_idx], 4)]
                for phase_arr in phase_arrays:
                    row.append(round(float(phase_arr[row_idx]), 5))
                self._phase_writer.writerow(row)
            self._phase_file.flush()
        except Exception as exc:
            self._log.log_exception("DataController.write_phase_row", exc)

    def close_phase_file(self):
        if self._phase_file:
            self._phase_file.close()
            self._phase_file = None
            self._phase_writer = None

    # --------------------------------------------------------- snapshot export
    def save_current_snapshot(
            self,
            time_arrays: dict,
            phase_arrays: dict,
            point_selected: dict,
            default_name: str = None,
    ):
        if default_name is None:
            default_name = (
                    datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_snapshot.DAT"
            )

        filepath = self.open_save_dialog(default_name)
        if not filepath:
            return

        try:
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f, delimiter="\t")
                header = []
                arrays = []

                for i in range(7):
                    header += [f"Time{i + 1}(s)", f"Phase{i + 1}(rad)"]
                writer.writerow(header)

                for i in range(7):
                    sel = int(point_selected.get(f"selected_{i}", 1)) - 1
                    sel = max(0, sel)

                    t = list(time_arrays.get(f"time_{i}", []))
                    p_all = phase_arrays.get(f"unphase_{i}", [[]])
                    p = list(p_all[sel]) if sel < len(p_all) else []

                    if len(t) != len(p):
                        self._log.log_exception(
                            "DataController.save_current_snapshot",
                            ValueError(f"Length mismatch in channel {i}: len(time)={len(t)}, len(phase)={len(p)}")
                        )
                        return

                    arrays.append(t)
                    arrays.append(p)

                for row in zip(*arrays):
                    writer.writerow([round(v, 5) for v in row])

        except Exception as exc:
            self._log.log_exception("DataController.save_current_snapshot", exc)