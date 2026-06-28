# views/main_window.py
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QStatusBar
from PyQt6.QtCore import pyqtSignal
from views.tab_calibration import TabCalibration
from views.tab_measure import TabMeasure
from views.tab_intensity import TabIntensity
from views.tab_processing import TabProcessing

# Inside __init__, after adding tab_measure:



class MainWindow(QMainWindow):
    close_event_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BiMW Modulation Software v4")
        self.setMinimumSize(1200, 800)

        self.tab_widget = QTabWidget()
        self.tab_calibration = TabCalibration()
        self.tab_measure = TabMeasure()
        self.tab_processing = TabProcessing()
        self.tab_widget.addTab(self.tab_processing, "Processing")
        self.tab_widget.addTab(self.tab_calibration, "Calibration")
        self.tab_widget.addTab(self.tab_measure, "Measure")
        self.tab_widget.addTab(self.tab_processing, "Processing")  # ← registered

        self.setCentralWidget(self.tab_widget)
        self.setStatusBar(QStatusBar())
        self.tab_intensity = TabIntensity()
        self.tab_widget.addTab(self.tab_intensity, "Intensity Check")  # index 0
        self.tab_widget.addTab(self.tab_calibration, "Calibration")  # index 1
        self.tab_widget.addTab(self.tab_measure, "Measure")  # index 2
        self.tab_widget.addTab(self.tab_processing, "Processing")  # index 3

    def closeEvent(self, event):
        self.close_event_signal.emit()
        event.accept()