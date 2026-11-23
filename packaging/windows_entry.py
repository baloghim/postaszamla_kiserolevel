import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exc

from postaszamla.gui import Application, main
from postaszamla.settings import program_directory


def smoke_test() -> None:
    import tkinter as tk

    import pypdfium2
    import pythoncom
    import win32com.client

    from postaszamla.generator import generate
    from postaszamla.models import Cost, Costs, Letter
    from postaszamla.preview import render_pdf

    root = tk.Tk()
    try:
        Application(root, program_directory())
        root.update()
        if not root.winfo_viewable():
            raise RuntimeError("A főablak nem jelent meg.")
        if not (Path(sys.executable).parent / "beallitasok.json").is_file():
            raise FileNotFoundError("A beállítások nem az EXE mellett jöttek létre.")

        zero = Cost(0, 0)
        day = date(2026, 1, 1)
        letter = Letter(day, day, "MINTA-001", day, ("0001",), None, day,
                        Costs(Cost(0, 100), zero, zero, zero))
        with TemporaryDirectory() as directory:
            docx = generate(letter, Path(directory))
            if not docx.is_file():
                raise FileNotFoundError("A mintasablonból nem készült DOCX.")

        contents = BytesIO()
        with pypdfium2.PdfDocument.new() as pdf:
            pdf.new_page(595, 842).close()
            pdf.save(contents)
        page_count, raster = render_pdf(contents.getvalue(), 0, "Szélesség", 321, 480)
        image = tk.PhotoImage(data=raster, format="ppm")
        if page_count != 1 or image.width() != 321:
            raise RuntimeError("A csomagolt PDF-előnézet ellenőrzése sikertelen.")

        pythoncom.CoInitialize()
        try:
            if not callable(win32com.client.DispatchEx):
                raise RuntimeError("A Word COM-modul nem érhető el.")
        finally:
            pythoncom.CoUninitialize()
    finally:
        root.destroy()


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
        main()
