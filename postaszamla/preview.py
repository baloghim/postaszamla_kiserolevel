import os
import shutil
import sys
from contextlib import closing
from math import nextafter
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
            import pypdfium2  # noqa: F401
            return "pdf", word_pdf(path)
        except Exception:
            # The text fallback can still display documents when Office or PDF rendering is unavailable.
            return "fallback", text_preview(path)
    return "text", text_preview(path)


def render_pdf(data: bytes, page: int, zoom: str, width: int, height: int):
    import pypdfium2

    with pypdfium2.PdfDocument(data) as document, closing(document[page]) as current:
        page_width, page_height = current.get_size()
        scale = width / page_width
        if zoom == "Teljes oldal":
            scale = min(scale, height / page_height)
        elif zoom.endswith("%"):
            scale = float(zoom[:-1]) / 100 * 96 / 72
        if not zoom.endswith("%"):
            scale = nextafter(scale, 0.0)
        scale = min(scale, 4.0)
        with closing(current.render(scale=scale, rev_byteorder=True)) as image:
            # Tk can load raw RGB PPM. Remove each PDFium row's alignment padding.
            row_size = image.width * 3
            raster = bytes(image.buffer)
            header = f"P6\n{image.width} {image.height}\n255\n".encode("ascii")
            return len(document), header + b"".join(
                raster[offset:offset + row_size]
                for offset in range(0, image.stride * image.height, image.stride)
            )


def word_action(path: Path, *, printing: bool = False) -> None:
    if sys.platform != "win32":
        raise OSError("Ez a művelet Windows és Microsoft Word alatt érhető el.")
    os.startfile(path, "print" if printing else "open")
