"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    if "--self-test" in sys.argv:
        app = QApplication([sys.argv[0]])
        return 0 if app.platformName() else 1
    app = QApplication(sys.argv)
    window = MainWindow()
    app.setApplicationName(window.windowTitle())
    if window.needs_first_setup():
        window.run_first_setup()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
