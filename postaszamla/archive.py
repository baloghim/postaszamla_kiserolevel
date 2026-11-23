import errno
import hashlib
import json
import os
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from .filename import make_filename
from .generator import generate
from .records import Record
from .settings import atomic_json

PERIOD = re.compile(r"^postaszámla_(\d{4})\.(\d{2})\.(\d{2})-(?:(\d{4})\.)?(\d{2})\.(\d{2})(?:_|\.docx$)", re.I)


def year_folders(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted((item.name for item in root.iterdir()
                   if re.fullmatch(r"[0-9]{4}", item.name) and item.is_dir()), reverse=True)


def initial_year() -> str:
    return str(date.today().year)


def filename_period(name: str) -> tuple[date, date] | None:
    match = PERIOD.match(name)
    if not match:
        return None
    year, month, day, end_year, end_month, end_day = match.groups()
    try:
        start = date(int(year), int(month), int(day))
        end = date(int(end_year or year), int(end_month), int(end_day))
    except ValueError:
        return None
    return (start, end) if start <= end else None


def sidecar(path: Path) -> Path:
    return path.with_suffix(".postaszamla.json")


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(256 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


@dataclass(frozen=True)
class SavedRecord:
    record: Record
    docx_hash: str
    data_hash: str


def read_record(path: Path) -> SavedRecord | None:
    try:
        raw = sidecar(path).read_bytes()
        data = json.loads(raw)
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            return None
        if data["docx_sha256"] != digest(path):
            return None
        return SavedRecord(Record.from_data(data["letter"]), data["docx_sha256"],
                           hashlib.sha256(raw).hexdigest())
    except (OSError, UnicodeError, KeyError, ValueError):
        return None


@dataclass(frozen=True)
class ArchiveEntry:
    path: Path
    period: tuple[date, date] | None
    pdf: Path | None
    count: int | None


def documents(root: Path, year: str, query: str = "") -> list[ArchiveEntry]:
    if not re.fullmatch(r"[0-9]{4}", year):
        return []
    folder = root / year
    if not folder.is_dir():
        return []
    paths = [item for item in folder.iterdir() if item.is_file()]
    pdfs = {item.stem.casefold(): item for item in paths if item.suffix.casefold() == ".pdf"}
    entries = []
    for path in paths:
        if path.name.startswith(("~$", ".")) or path.suffix.casefold() != ".docx":
            continue
        if query.casefold().strip() not in path.name.casefold():
            continue
        saved = read_record(path)
        letter = saved.record.to_letter() if saved else None
        dates = (letter.start, letter.end) if letter else filename_period(path.name)
        entries.append(ArchiveEntry(path, dates, pdfs.get(path.stem.casefold()),
                                    letter.invoice_count if letter else None))
    return sorted(entries, key=lambda item: (item.period or (date.min, date.min),
                                             item.path.name.casefold()), reverse=True)


@contextmanager
def archive_lock(root: Path):
    lock = root / ".postaszamla-lock"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError("A dokumentumtárban mentés zajlik, vagy egy korábbi mentés megszakadt.") from error
    try:
        yield
    finally:
        lock.rmdir()


def publish_new(source: Path, target: Path) -> None:
    # Windows rename is atomic and fails if the target exists.
    if os.name == "nt":
        source.rename(target)
        return
    try:
        os.link(source, target)
        return
    except FileExistsError:
        raise
    except OSError as error:
        if error.errno not in (errno.EACCES, errno.EPERM, errno.ENOTSUP, errno.EXDEV):
            raise
    # A shared drive can deny hard-link creation; keep exclusive publication.
    stream = target.open("xb")
    try:
        with stream, source.open("rb") as original:
            shutil.copyfileobj(original, stream)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def save_record(root: Path, template: Path, record: Record, *, previous: Path | None = None,
                expected: SavedRecord | None = None) -> Path:
    letter = record.to_letter()
    basename = make_filename(letter.start, letter.end, letter.costs)
    folder = root / f"{letter.start.year:04d}"
    target = folder / basename
    if not root.is_dir():
        raise ValueError("A dokumentumtár nem érhető el.")
    with archive_lock(root):
        if previous is not None:
            if previous.parent.parent.resolve() != root.resolve():
                raise ValueError("A korábbi dokumentum nincs a kiválasztott dokumentumtárban.")
            if expected is None or read_record(previous) != expected:
                raise ValueError("A levél vagy adatfájl időközben megváltozott. Frissítse a listát.")
        same_name = previous is not None and previous == target
        if not same_name and folder.is_dir():
            reserved = {target.name.casefold(), sidecar(target).name.casefold(),
                        target.with_suffix(".pdf").name.casefold()}
            if any(item.name.casefold() in reserved for item in folder.iterdir()):
                raise FileExistsError(f"Már létezik az új névhez tartozó fájl: {target.name}")
        folder.mkdir(exist_ok=True)
        with TemporaryDirectory(prefix=".postaszamla-stage-", dir=folder) as directory:
            staging = Path(directory)
            staged_doc = generate(letter, staging, template, year_subfolder=False)
            staged_data = sidecar(staged_doc)
            atomic_json(staged_data, {"version": 1, "docx_sha256": digest(staged_doc),
                                      "letter": record.to_data()})
            backup = None
            if previous is not None:
                backup = root / ".postaszamla-backups" / uuid4().hex / previous.parent.name
                backup.mkdir(parents=True)
                for path in (previous, sidecar(previous)):
                    copy = backup / path.name
                    shutil.copy2(path, copy)
                    wanted = expected.docx_hash if path == previous else expected.data_hash
                    if digest(copy) != wanted:
                        raise ValueError("A biztonsági másolat ellenőrzése sikertelen.")
            changed = []
            removed = []
            try:
                for staged, final in ((staged_data, sidecar(target)), (staged_doc, target)):
                    if same_name:
                        os.replace(staged, final)
                    else:
                        publish_new(staged, final)
                    changed.append(final)
                saved = read_record(target)
                if saved is None or saved.record != record:
                    raise ValueError("A mentett fájlpár ellenőrzése sikertelen.")
                if previous is not None and not same_name:
                    for path in (previous, sidecar(previous)):
                        path.unlink()
                        removed.append(path)
            except BaseException as error:
                try:
                    for path in reversed(changed):
                        if same_name:
                            restore_file(backup / path.name, path)
                        else:
                            path.unlink()
                    for path in removed:
                        restore_file(backup / path.name, path)
                except OSError as restore_error:
                    raise OSError(f"A visszaállítás kézi beavatkozást igényel: {backup or target}") from restore_error
                raise error
    return target


def restore_file(source: Path, target: Path) -> None:
    with TemporaryDirectory(prefix=".postaszamla-restore-", dir=target.parent) as directory:
        staging = Path(directory) / target.name
        shutil.copy2(source, staging)
        os.replace(staging, target)
