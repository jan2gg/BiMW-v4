# main.py
import sys
from PyQt6.QtWidgets import QApplication
from controllers.main_controller import MainController


def main():
    app = QApplication(sys.argv)
    ctrl = MainController(app)   # controller creates and shows the window
    sys.exit(app.exec())


if __name__ == "__main__":
    main()