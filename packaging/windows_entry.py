import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exc

from postaszamla.gui import main


def has_native_window_icon(window) -> bool:
    from ctypes import WinDLL, c_int, c_ssize_t, c_void_p
    from ctypes.wintypes import HWND, LPARAM, UINT, WPARAM

    user32 = WinDLL("user32")
    send_message = user32.SendMessageW
    send_message.argtypes = (HWND, UINT, WPARAM, LPARAM)
    send_message.restype = c_ssize_t
    get_class_icon = user32.GetClassLongPtrW
    get_class_icon.argtypes = (HWND, c_int)
    get_class_icon.restype = c_void_p
    handle = int(window.winId())
    wm_geticon, icon_big, gclp_hicon = 0x007F, 1, -14
    return bool(send_message(handle, wm_geticon, icon_big, 0) or get_class_icon(handle, gclp_hicon))


def smoke_test() -> None:
    import pypdfium2
    import pythoncom
    import win32com.client
    from PySide2.QtCore import qVersion

    from postaszamla.archive import read_record, save_record
    from postaszamla.models import Cost, Costs
    from postaszamla.qt.app import create_application
    from postaszamla.qt.appearance import Appearance, FACTORY_STYLES, SURFACES
    from postaszamla.qt.edpd_graphics.icons import APP_ROLES
    from postaszamla.qt.window import MainWindow
    from postaszamla.records import Invoice, Record
    from postaszamla.settings import DEFAULT_ICON_THEME, DEFAULT_UI_STYLE, program_directory
    from postaszamla.template import DEFAULT_TEMPLATE

    app = create_application()
    original_base = program_directory()
    appearance = Appearance(app)
    startup = MainWindow(appearance, original_base)
    startup.showMaximized()
    app.processEvents()
    if not startup.isVisible() or qVersion() != "5.15.2" or app.property("surfaceTheme") != SURFACES[DEFAULT_UI_STYLE]:
        raise RuntimeError("A Qt 5 főablak nem a várt alapbeállítással jelent meg.")
    if startup.appearance.icons.name != DEFAULT_ICON_THEME:
        raise RuntimeError("A csomagolt kiadás alapértelmezett ikontémája hibás.")
    if not (original_base / "beallitasok.json").is_file():
        raise FileNotFoundError("A beállítások nem az EXE mellett jöttek létre.")
    for key, label in FACTORY_STYLES:
        appearance.apply(key)
        if app.style().objectName().casefold() != key or app.styleSheet():
            raise RuntimeError(f"A csomagolt Qt 5 stílus nem tölthető be: {label}.")
    for key, label in SURFACES.items():
        appearance.apply(key)
        if app.property("surfaceTheme") != label or not app.styleSheet():
            raise RuntimeError(f"A csomagolt EDPD stílus nem tölthető be: {label}.")
    themes = appearance.icons.choices()
    if len(themes) != 12:
        raise RuntimeError("A csomagolt ikontémák száma eltér a várt tizenkettőtől.")
    identity = app.windowIcon().pixmap(32, 32).toImage()
    if identity.isNull() or not has_native_window_icon(startup):
        raise RuntimeError("A csomagolt alkalmazásikon nem töltődött be.")
    for theme in themes:
        appearance.apply(appearance.current_style, theme)
        graphic = appearance.icon("refresh").pixmap(22, 22)
        if graphic.isNull() or appearance.icons.sources["refresh"] != theme:
            raise RuntimeError(f"A csomagolt ikontéma nem tölthető be: {theme}.")
        for role in APP_ROLES:
            expected = appearance.icons.describe(role)["kind"] != "none"
            if appearance.icon(role).pixmap(22, 22).isNull() == expected:
                raise RuntimeError(f"Hibás csomagolt ikonszerep: {theme} / {role}.")
        if startup.windowIcon().pixmap(32, 32).toImage() != identity:
            raise RuntimeError("Az alkalmazásikon megváltozott az ikontémával.")
    appearance.apply(DEFAULT_UI_STYLE, DEFAULT_ICON_THEME)
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
                raise RuntimeError("Az Új kísérőlevél ablak nem jelent meg az alapértelmezett stílusban.")
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
