import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exc

from postaszamla.gui import main


def smoke_test() -> None:
    import pypdfium2
    import pythoncom
    import win32com.client
    from PySide2.QtCore import qVersion

    from postaszamla.archive import read_record, save_record
    from postaszamla.models import Cost, Costs
    from postaszamla.qt.app import create_application
    from postaszamla.qt.appearance import Appearance, FACTORY_STYLES, THEME
    from postaszamla.qt.window import MainWindow
    from postaszamla.records import Invoice, Record
    from postaszamla.settings import DEFAULT_UI_STYLE, program_directory
    from postaszamla.template import DEFAULT_TEMPLATE

    app = create_application()
    original_base = program_directory()
    appearance = Appearance(app)
    startup = MainWindow(appearance, original_base)
    startup.showMaximized()
    app.processEvents()
    if not startup.isVisible() or qVersion() != "5.15.2" or app.property("surfaceTheme") != THEME:
        raise RuntimeError("A Qt 5 Luna főablak nem jelent meg.")
    if not (original_base / "beallitasok.json").is_file():
        raise FileNotFoundError("A beállítások nem az EXE mellett jöttek létre.")
    for key, label in FACTORY_STYLES:
        appearance.apply(key)
        if app.style().objectName().casefold() != key or app.styleSheet():
            raise RuntimeError(f"A csomagolt Qt 5 stílus nem tölthető be: {label}.")
    appearance.apply(DEFAULT_UI_STYLE)
    if app.property("surfaceTheme") != THEME or not app.styleSheet():
        raise RuntimeError("A Luna felület nem állt vissza.")
    startup.close()

    zero = Cost(0, 0)
    day = date(2026, 1, 1)
    invoice = Invoice("0001", day, day, Costs(Cost(0, 100), zero, zero, zero))
    record = Record("MINTA-001", "Minta Anna", "Minta Aláíró", "vezető", day, day, (invoice,))
    with TemporaryDirectory() as directory:
        root = Path(directory)
        archive = root / "dokumentumok"
        archive.mkdir()
        docx = save_record(archive, DEFAULT_TEMPLATE, record)
        saved = read_record(docx)
        if saved is None or saved.record != record:
            raise RuntimeError("A mintasablonból készült DOCX és JSON nem egyezik.")
        window = MainWindow(Appearance(app), root)
        try:
            window.showMaximized()
            window.restore_panels()
            window.reload(preferred=docx)
            if window.metadata != saved or not window.actions["edit"].isEnabled():
                raise RuntimeError("A dokumentumtár nem tölti be az elmentett levelet.")
            contents = BytesIO()
            with pypdfium2.PdfDocument.new() as pdf:
                pdf.new_page(595, 842).close()
                pdf.save(contents)
            window.preview.select(None)
            window.preview.viewer.open_data(contents.getvalue())
            app.processEvents()
            if window.preview.viewer.label.pixmap() is None:
                raise RuntimeError("A csomagolt PDF-előnézet ellenőrzése sikertelen.")
            dialog = window.open_editor()
            app.processEvents()
            if not dialog.isVisible() or dialog.style().objectName() != window.style().objectName():
                raise RuntimeError("Az Új kísérőlevél ablak nem jelent meg Luna stílusban.")
            dialog.reject()
        finally:
            window.close()
            app.processEvents()

    pythoncom.CoInitialize()
    try:
        if not callable(win32com.client.DispatchEx):
            raise RuntimeError("A Word COM-modul nem érhető el.")
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--ellenorzes":
        report = Path(sys.argv[2])
        try:
            smoke_test()
        except Exception:
            report.write_text(format_exc(), encoding="utf-8")
            raise SystemExit(1)
        report.write_text("OK\n", encoding="utf-8")
    else:
        raise SystemExit(main())
