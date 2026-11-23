import os
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document


def word_pdf(source: Path) -> bytes:
    import pythoncom
    import win32com.client

    with TemporaryDirectory(prefix="postaszamla-preview-") as directory:
        copy = Path(directory) / "level.docx"
        pdf = copy.with_suffix(".pdf")
        shutil.copyfile(source, copy)
        pythoncom.CoInitialize()
        try:
            word = win32com.client.DispatchEx("Word.Application")
            try:
                word.DisplayAlerts = 0
                word.AutomationSecurity = 3
                word.Options.UpdateLinksAtOpen = False
                document = word.Documents.Open(
                    str(copy), ReadOnly=True, AddToRecentFiles=False, ConfirmConversions=False,
                    Visible=False,
                )
                try:
                    document.ExportAsFixedFormat(str(pdf), 17)
                finally:
                    document.Close(False)
            finally:
                word.Quit(False)
        finally:
            pythoncom.CoUninitialize()
        return pdf.read_bytes()


def text_preview(path: Path) -> str:
    document = Document(path)
    blocks = []
    for section in document.sections:
        blocks.extend(p.text for p in section.header.paragraphs if p.text)
    for block in document.iter_inner_content():
        if hasattr(block, "rows"):
            blocks.extend("  |  ".join(cell.text for cell in row.cells) for row in block.rows)
        elif block.text:
            blocks.append(block.text)
    for section in document.sections:
        blocks.extend(p.text for p in section.footer.paragraphs if p.text)
    return "\n\n".join(blocks)


def prepare_preview(path: Path) -> tuple[str, bytes | str]:
    if sys.platform == "win32":
        try:
            import pymupdf  # noqa: F401
            return "pdf", word_pdf(path)
        except Exception:
            # The text fallback can still display documents when Office or PDF rendering is unavailable.
            return "fallback", text_preview(path)
    return "text", text_preview(path)


def render_pdf(data: bytes, page: int, zoom: str, width: int, height: int):
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as document:
        current = document[page]
        scale = width / current.rect.width
        if zoom == "Teljes oldal":
            scale = min(scale, height / current.rect.height)
        elif zoom.endswith("%"):
            scale = float(zoom[:-1]) / 100 * 96 / 72
        scale = max(0.1, min(scale, 4.0))
        image = current.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        return len(document), image.tobytes("png")


def word_action(path: Path, *, printing: bool = False) -> None:
    if sys.platform != "win32":
        raise OSError("Ez a művelet Windows és Microsoft Word alatt érhető el.")
    os.startfile(path, "print" if printing else "open")
