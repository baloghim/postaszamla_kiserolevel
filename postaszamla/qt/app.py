import argparse
import sys
from pathlib import Path

from PySide2.QtCore import QLocale, QTimer, Qt
from PySide2.QtWidgets import QApplication, QMessageBox

from postaszamla.settings import program_directory

from .appearance import Appearance
from .window import MainWindow


def create_application():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication([])
    app.setApplicationName("Postaszámla")
    QLocale.setDefault(QLocale(QLocale.Hungarian, QLocale.Hungary))
    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description="Postaszámla – Kísérőlevelek (Qt 5)")
    parser.add_argument("--edpd-source", type=Path, help="Az EDPD 2.6.3 helyi munkapéldánya.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    app = create_application()
    try:
        appearance = Appearance(app, args.edpd_source)
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        QMessageBox.critical(None, "Megjelenés", str(error))
        return 1
    window = MainWindow(appearance, program_directory())
    if window.settings.window_state == "zoomed":
        window.showMaximized()
    else:
        window.show()
    QTimer.singleShot(0, window.restore_panels)
    return app.exec_()
