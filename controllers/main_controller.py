# controllers/main_controller.py
from PyQt6.QtWidgets import QApplication
from views.main_window import MainWindow
from models.measurement_config import MeasurementConfig
from models.calibration_result import CalibrationResult
from services.logger_service import LoggerService
from controllers.measurement_setup_controller import MeasurementSetupController
from controllers.data_controller import DataController
from controllers.calibration_controller import CalibrationController
from controllers.measurement_controller import MeasurementController
from controllers.processing_controller import ProcessingController
from core.daq.acquisition import AcquisitionTask
from core.daq.device_discovery import NO_DEVICE
from controllers.intensity_controller import IntensityController



class MainController:
    def __init__(self, app: QApplication):
        self.app = app

        # Shared services
        self._log = LoggerService("log.txt")
        self._config = MeasurementConfig()
        self._daq = AcquisitionTask()
        self._cal_result = CalibrationResult()

        # Window
        self._window = MainWindow()
        self._window.close_event_signal.connect(self._on_close)

        # Shared controllers
        self._setup = MeasurementSetupController(self._config, self._log)
        self._data = DataController(self._window, self._log)

        # Tab controllers
        self._calibration_ctrl = CalibrationController(
            tab=self._window.tab_calibration,
            config=self._config,
            setup=self._setup,
            daq=self._daq,
            calibration_result=self._cal_result,
            data_ctrl=self._data,
            logger=self._log,
        )
        self._measurement_ctrl = MeasurementController(
            tab=self._window.tab_measure,
            config=self._config,
            setup=self._setup,
            daq=self._daq,
            calibration_result=self._cal_result,
            data_ctrl=self._data,
            logger=self._log,
        )
        self._processing_ctrl = ProcessingController(
            tab=self._window.tab_processing,
            data_ctrl=self._data,
            logger=self._log,
        )
        self._intensity_ctrl = IntensityController(
            tab=self._window.tab_intensity,
            logger=self._log,
            setup=self._setup,
        )

        # Cross-controller wiring
        self._calibration_ctrl.calibration_finished.connect(
            self._measurement_ctrl.notify_calibration_done
        )
        self._calibration_ctrl.switch_to_measure.connect(
            lambda: self._window.tab_widget.setCurrentIndex(2)
        )
        self._calibration_ctrl._intensity_ctrl = self._intensity_ctrl
        self._intensity_ctrl._cal_ctrl = self._calibration_ctrl
        self._measurement_ctrl._processing_tab = self._window.tab_processing

        # Exit confirmation
        self._calibration_ctrl.request_exit.connect(self._confirm_exit)
        self._measurement_ctrl.request_exit.connect(self._confirm_exit)
        self._intensity_ctrl.request_exit.connect(self._confirm_exit)
        self._processing_ctrl.request_exit.connect(self._confirm_exit)

        self._window.show()

        self._calibration_ctrl.refresh_combos()
        self._measurement_ctrl.refresh_combos()

        self._setup.reload_devices()
        if self._setup.device_selected != NO_DEVICE:
            self._daq.init_read_task()
            self._daq.init_write_task()
            self._calibration_ctrl._add_channels()
            self._daq.start_read_task()
            self._calibration_ctrl.start_couple_timer()

        self._log.log("MainController", "Application started")

    def _on_close(self):
        try:
            self._daq.stop_read_task()
            self._daq.stop_write_task()
            self._daq.close_read_task()
            self._daq.close_write_task()
            self._data.close_phase_file()
            self._log.log("MainController", "Application closed cleanly")
            self._log.close()
        except Exception as exc:
            self._log.log_exception("MainController._on_close", exc)
        finally:
            self.app.quit()

    def _confirm_exit(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self._window,
            "Exit BiMW Software",
            "Are you sure you want to close the application?\n\n"
            "Any unsaved measurement data will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._window.close()