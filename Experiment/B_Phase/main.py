#!/usr/bin/env python3
"""Entry point for the Haptic Controller 4x4 GUI."""
from PyQt6.QtWidgets import QApplication
import sys

from main_window import MainWindow
from serial_backend import SerialBackend, MockBackend


def pick_backend():
    try:
        # Prefer the real backend if serial_api.py is present and importable
        backend = SerialBackend()
        return backend
    except Exception as e:
        print(f"[WARN] Falling back to MockBackend: {e}")
        return MockBackend()


def main():
    app = QApplication(sys.argv)
    # Load optional stylesheet
    try:
        with open("style.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"[WARN] Style not loaded: {e}")
    backend = pick_backend()
    win = MainWindow(backend=backend)
    win.resize(1100, 700)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()