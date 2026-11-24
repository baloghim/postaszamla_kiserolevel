"""Publish a verified PDF and remove one confirmed archive entry safely."""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from stat import FILE_ATTRIBUTE_REPARSE_POINT, S_ISREG
from tempfile import TemporaryDirectory
from uuid import uuid4

from .archive import archive_lock, publish_new, sidecar
from .preview import PDFIUM_LOCK, word_pdf


def archive_docx(root: Path, path: Path) -> Path:
    root = root.resolve()
    folder = path.parent.resolve()
    if (folder.parent != root or not re.fullmatch(r"[0-9]{4}", folder.name)
            or path.parent.name != folder.name or path.suffix.lower() != ".docx"
            or path.name.startswith((".", "~$"))):
        raise ValueError("A kijelölt DOCX nincs a dokumentumtár egyik éves mappájában.")
    return folder / path.name


def pdf_for(path: Path) -> Path | None:
    matches = [item for item in path.parent.iterdir()
               if item.name.casefold() == path.with_suffix(".pdf").name.casefold()]
    if len(matches) > 1:
        raise ValueError("Több azonos alapnevű PDF található. Frissítse a listát, és ellenőrizze a fájlokat.")
    return matches[0] if matches else None


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    identity: tuple[int, ...]

    @classmethod
    def read(cls, path):
        stat = path.lstat()
        if not S_ISREG(stat.st_mode) or getattr(stat, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"A művelet csak normál fájlon végezhető el: {path.name}")
        return cls(path, (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))


def generate_pdf(root: Path, path: Path) -> Path:
    import pypdfium2

    source = FileSnapshot.read(archive_docx(root, path))
    if pdf_for(source.path):
        raise FileExistsError("Az azonos nevű PDF már létezik.")
    try:
        data = word_pdf(source.path)
    except Exception as error:
        raise OSError(f"A Microsoft Word nem tudta elkészíteni a PDF-et.\n{error}") from error
    try:
        with PDFIUM_LOCK, pypdfium2.PdfDocument(data) as pdf:
            if not len(pdf):
                raise ValueError("A PDF egyetlen oldalt sem tartalmaz.")
    except (ValueError, pypdfium2.PdfiumError) as error:
        raise ValueError("A Word által készített PDF üres vagy nem olvasható.") from error
    target = source.path.with_suffix(".pdf")
    with TemporaryDirectory(prefix=".postaszamla-pdf-", dir=target.parent) as folder:
        staged = Path(folder) / target.name
        staged.write_bytes(data)
        with archive_lock(root):
            if source != FileSnapshot.read(source.path):
                raise ValueError("A DOCX a konvertálás közben megváltozott. Válassza ki újra a levelet.")
            if pdf_for(source.path):
                raise FileExistsError("Az azonos nevű PDF időközben létrejött.")
            publish_new(staged, target)
    return target


@dataclass(frozen=True)
class DeletionPlan:
    root: Path
    document: FileSnapshot
    data: FileSnapshot | None
    pdf: FileSnapshot | None

    @classmethod
    def read(cls, root, path):
        doc = FileSnapshot.read(archive_docx(root, path))
        try:
            data = FileSnapshot.read(sidecar(doc.path))
        except FileNotFoundError:
            data = None
        pdf = pdf_for(doc.path)
        return cls(root.resolve(), doc, data, FileSnapshot.read(pdf) if pdf else None)

    def files(self, include_pdf=False):
        return tuple(item for item in (self.document, self.data, self.pdf if include_pdf else None) if item)


def move_to_windows_trash(path: Path) -> bool:
    if os.name != "nt":
        return False
    from PySide2.QtCore import QFile
    # Qt 5.15/MSVC uses IFileOperation with recycling flags and refuses permanent deletion.
    return QFile(str(path)).moveToTrash()


def delete_document(plan: DeletionPlan, include_pdf=False) -> Path | None:
    """Remove precisely the confirmed files from the archive and return any local trash folder."""
    with archive_lock(plan.root):
        if DeletionPlan.read(plan.root, plan.document.path) != plan:
            raise ValueError("A fájllista időközben megváltozott. Frissítse a listát, és erősítse meg újra a törlést.")
        trash = plan.root / ".postaszamla-trash"
        trash.mkdir(exist_ok=True)
        if trash.resolve() != trash or getattr(trash.lstat(), "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("A dokumentumtár lomtármappája átirányított elérési út.")
        destination = trash / f"{plan.document.path.parent.name}-{uuid4().hex}"
        destination.mkdir()
        moved = []
        try:
            for item in plan.files(include_pdf):
                if FileSnapshot.read(item.path) != item:
                    raise ValueError(f"A fájl időközben megváltozott: {item.path.name}")
                target = destination / item.path.name
                item.path.rename(target)
                moved.append((target, item.path))
        except (OSError, ValueError) as error:
            failures = []
            for source, original in reversed(moved):
                try:
                    publish_new(source, original)
                    source.unlink(missing_ok=True)
                except OSError:
                    failures.append(original.name)
            if failures:
                raise OSError(f"Részleges törlés. A kézi visszaállításhoz szükséges fájlok itt vannak: {destination}\n"
                              + "\n".join(failures)) from error
            destination.rmdir()
            raise OSError(f"A törlés megszakadt. Az addig áthelyezett fájlok visszakerültek.\n{error}") from error

    for source, _ in moved:
        try:
            if move_to_windows_trash(source):
                continue
            if not source.is_file():
                raise OSError(f"A fájl lomtári helye nem ellenőrizhető: {source.name}")
        except OSError as error:
            raise OSError(f"A Windows Lomtárba helyezés csak részben sikerült.\n"
                          f"A helyi lomtármappa: {destination}\n{error}") from error
    if any(source.exists() for source, _ in moved):
        return destination
    destination.rmdir()
    return None
