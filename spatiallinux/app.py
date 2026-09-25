import signal
import sys
import traceback

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui import theme
from . import presets


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.STYLESHEET)

    presets.migrate_old_data()
    window = MainWindow()

    def shutdown(*_):
        # The engine owns the system default sink while it runs, so it must
        # be torn down on every exit path -- clean quit, Ctrl-C, SIGTERM, or
        # an unhandled error -- otherwise audio is left routed at a sink that
        # no longer exists.
        try:
            window._save_if_changed()     # a kill never reaches closeEvent
        except Exception:
            traceback.print_exc()
        try:
            window.engine.stop()
        except Exception:
            traceback.print_exc()
        app.quit()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    app.aboutToQuit.connect(lambda: window.engine.stop())

    # Python only runs signal handlers between bytecodes, and Qt's event loop
    # sits in C++ the whole time -- without something that periodically
    # returns to the interpreter, SIGTERM/SIGINT are never delivered and the
    # engine would be left owning the default sink after a kill or logout.
    heartbeat = QTimer()
    heartbeat.start(250)
    heartbeat.timeout.connect(lambda: None)

    def excepthook(exc_type, exc, tb):
        traceback.print_exception(exc_type, exc, tb)
        shutdown()

    sys.excepthook = excepthook

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
