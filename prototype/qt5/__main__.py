from time import perf_counter

STARTED = perf_counter()


def main():
    import argparse
    import json
    from pathlib import Path

    from PySide2.QtCore import QLocale, QTimer, Qt, qVersion
    from PySide2.QtWidgets import QApplication

    from .appearance import Appearance
    from .window import MainWindow

    parser = argparse.ArgumentParser(description="Postaszámla Qt 5 felületi prototípus")
    parser.add_argument("--edpd-source", type=Path, help="Az EDPD 2.6.3 meglévő helyi checkoutja.")
    parser.add_argument("--measure", action="store_true", help="Indulási mérés, majd kilépés.")
    parser.add_argument("--screenshots", type=Path, help="Képek mentése a megjelenített ablakokról.")
    args = parser.parse_args()

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication([])
    QLocale.setDefault(QLocale(QLocale.Hungarian, QLocale.Hungary))
    app.setApplicationName("Postaszámla")
    appearance = Appearance(app, args.edpd_source)
    window = MainWindow(appearance)
    window.resize(app.primaryScreen().availableGeometry().size())
    window.showMaximized()
    exit_code = 0

    def prepare():
        nonlocal exit_code
        width = window.splitter.width() // 2
        window.splitter.setSizes([width, width])
        app.processEvents()
        visible = perf_counter()
        window.table.selectRow(0)
        app.processEvents()
        rendered = perf_counter()
        if args.measure or args.screenshots:
            if not window.isVisible() or window.preview.viewer.label.pixmap() is None:
                exit_code = 1
                app.quit()
                return
            print(json.dumps({
                "qt": qVersion(), "platform": app.platformName(),
                "screen": tuple((app.primaryScreen().size().width(), app.primaryScreen().size().height())),
                "window": (window.width(), window.height()), "split": window.splitter.sizes(),
                "window_ms": round((visible - STARTED) * 1000),
                "first_pdf_ms": round((rendered - STARTED) * 1000),
                "edpd": appearance.source is not None,
            }), flush=True)
        if args.screenshots:
            output = args.screenshots
            output.mkdir(parents=True, exist_ok=True)
            main_saved = window.grab().save(str(output / "foablak.png"))
            dialog = window.open_editor()

            def capture_dialog():
                nonlocal exit_code
                saved = dialog.isVisible() and dialog.grab().save(str(output / "uj-kiserolevel.png"))
                exit_code = 0 if main_saved and saved else 1
                app.quit()

            QTimer.singleShot(180, capture_dialog)
        elif args.measure:
            app.quit()

    QTimer.singleShot(0, prepare)
    return app.exec_() or exit_code


if __name__ == "__main__":
    raise SystemExit(main())
