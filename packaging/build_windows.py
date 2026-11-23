import re
import shutil
import struct
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from postaszamla.gui_icons import ICON_NAMES, ICON_SIZES

ROOT = Path(__file__).resolve().parent.parent
APP = "Postaszamla"


def copy_notices(bundle: Path) -> None:
    licenses = bundle / "Licencek"
    licenses.mkdir()
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    shutil.copy2(python_license, licenses / "Python.txt")
    for name in ("python-docx", "lxml", "typing-extensions", "pypdfium2", "pywin32", "pyinstaller"):
        package = distribution(name)
        for path in package.files or ():
            if re.search(r"licen[cs]e|copying|notice", str(path), re.IGNORECASE):
                # Keep subdirectories because the PDFium wheel ships several notices with the same name.
                source = Path(package.locate_file(path))
                if ".." not in path.parts and source.is_file():
                    target = licenses / name / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    shutil.copy2(ROOT / "README.md", bundle / "README.md")


def verify(package: Path, directory: Path) -> None:
    with ZipFile(package) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("A Windows ZIP sérült.")
        for filename in archive.namelist():
            path = Path(filename)
            if (path.name.casefold().startswith("beallitasok.json")
                    or path.suffix.casefold() in {".json", ".pdf", ".doc", ".docx"}
                    and not filename.endswith((
                        "/postaszamla/templates/minta.docx", "/docx/templates/default.docx",
                        "/pypdfium2/version.json",
                        "/pypdfium2_raw/version.json",
                    ))):
                raise RuntimeError(f"Váratlan adatfájl a Windows ZIP-ben: {filename}")
        icons = f"{APP}/_internal/postaszamla/icons"
        expected_icons = {
            *(f"{icons}/png/{size}.png" for size in ICON_SIZES),
            *(f"{icons}/svg/{name}.svg" for name in ICON_NAMES),
            *(f"{icons}/{name}" for name in ("COPYING", "COPYING.LESSER", "AUTHORS", "UPSTREAM-README.md",
                                           "LICENSE-KDE-Classic.txt", "FORRAS.md")),
        }
        if missing := expected_icons - set(archive.namelist()):
            raise RuntimeError(f"Az ikoncsomag hiányos: {', '.join(sorted(missing))}")
        archive.extractall(directory)
    application = directory / APP / f"{APP}.exe"
    with application.open("rb") as binary:
        if binary.read(2) != b"MZ":
            raise RuntimeError("A csomag nem Windows futtatható fájlt tartalmaz.")
        binary.seek(0x3c)
        binary.seek(struct.unpack("<I", binary.read(4))[0])
        if binary.read(6) != b"PE\0\0\x64\x86":
            raise RuntimeError("A futtatható fájl nem Windows x64 PE.")
    report = directory / "ellenorzes.txt"
    result = subprocess.run([application, "--ellenorzes", report], cwd=directory, timeout=90)
    output = report.read_text(encoding="utf-8") if report.exists() else "(nincs napló)"
    if result.returncode or output.strip() != "OK":
        raise RuntimeError(f"A kicsomagolt EXE ellenőrzése sikertelen. {result.returncode}\n{output}")
    print("A kicsomagolt x64 EXE, a felület, a DOCX, a PDFium és a COM-import ellenőrzése sikeres.")


def main(tag: str, output: Path) -> None:
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        raise SystemExit("A PyInstaller-csomagot 64 bites Windows alatt kell elkészíteni.")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise SystemExit("Érvénytelen verziócímke.")
    with TemporaryDirectory(prefix="postaszamla-build-") as temporary:
        temp = Path(temporary)
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--noupx",
            "--onedir", "--windowed", "--name", APP, "--contents-directory", "_internal",
            "--paths", str(ROOT), "--distpath", str(temp / "dist"),
            "--workpath", str(temp / "work"), "--specpath", str(temp),
            "--add-data", f"{ROOT / 'postaszamla/templates/minta.docx'};postaszamla/templates",
            "--add-data", f"{ROOT / 'postaszamla/icons'};postaszamla/icons",
            "--collect-data", "pypdfium2", "--collect-all", "pypdfium2_raw",
            "--hidden-import", "win32timezone",
        ]
        for name in ("vcruntime140.dll", "vcruntime140_1.dll"):
            runtime = Path(sys.base_prefix) / name
            if runtime.is_file():
                command.extend(("--add-binary", f"{runtime};."))
        build = subprocess.run(
            [*command, str(ROOT / "packaging" / "windows_entry.py")],
            cwd=ROOT, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        print(build.stdout)
        if build.returncode:
            tail = "\n".join(build.stdout.splitlines()[-12:])
            raise RuntimeError(f"A PyInstaller kilépési kódja: {build.returncode}\n{tail}")
        dist = temp / "dist"
        for name in ("vcruntime140.dll", "vcruntime140_1.dll"):
            if not (dist / APP / "_internal" / name).is_file():
                raise FileNotFoundError(f"A csomagból hiányzik a Visual C++ futtatókörnyezet: {name}")
        copy_notices(dist / APP)
        package = Path(shutil.make_archive(str(temp / f"{APP}-{tag}-win64"), "zip", dist, APP))
        verify(package, temp / "extracted")
        output.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package, output / package.name)


if __name__ == "__main__":
    try:
        main(sys.argv[1], Path(sys.argv[2]).resolve())
    except Exception as error:
        detail = f"{type(error).__name__}: {error}".replace("%", "%25")
        print("::error::" + detail.replace("\r", "%0D").replace("\n", "%0A"), flush=True)
        raise
