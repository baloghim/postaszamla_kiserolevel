import re
import shutil
import struct
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
APP = "Postaszamla"
GRAPHICS = Path("postaszamla/qt/edpd_graphics/assets")
APPLICATION_ICON = GRAPHICS / "application.ico"


def copy_notices(bundle: Path) -> None:
    licenses = bundle / "Licencek"
    licenses.mkdir()
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    shutil.copy2(python_license, licenses / "Python.txt")
    for name in ("python-docx", "lxml", "typing-extensions", "pypdfium2", "pywin32", "PySide2", "shiboken2", "pyinstaller"):
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


def verify_application_icon(application: Path) -> None:
    import pefile

    icon = (ROOT / APPLICATION_ICON).read_bytes()
    count = struct.unpack_from("<H", icon, 4)[0]
    expected = {}
    for index in range(count):
        entry = 6 + 16 * index
        width, height = icon[entry:entry + 2]
        size, offset = struct.unpack_from("<II", icon, entry + 8)
        expected[(width or 256, height or 256)] = (icon[entry:entry + 12], icon[offset:offset + size])
    if count != 7 or sorted(expected) != [(size, size) for size in (16, 24, 32, 48, 64, 128, 256)]:
        raise RuntimeError("A rögzített ICO nem tartalmazza az előírt hét képméretet.")

    with pefile.PE(str(application), fast_load=True) as executable:
        executable.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
        resources = {
            (resource.id, entry.id): executable.get_data(language.data.struct.OffsetToData,
                                                           language.data.struct.Size)
            for resource in executable.DIRECTORY_ENTRY_RESOURCE.entries
            for entry in resource.directory.entries
            for language in entry.directory.entries
        }
    group_type = pefile.RESOURCE_TYPE["RT_GROUP_ICON"]
    icon_type = pefile.RESOURCE_TYPE["RT_ICON"]
    groups = [data for (resource_type, _), data in resources.items() if resource_type == group_type]
    if len(groups) != 1 or len(groups[0]) != 6 + 14 * count or groups[0][:6] != icon[:6]:
        raise RuntimeError("Az EXE alkalmazásikon-csoportja hibás.")
    group = groups[0]
    actual = {}
    for entry in range(6, len(group), 14):
        width, height = group[entry:entry + 2]
        icon_id = struct.unpack_from("<H", group, entry + 12)[0]
        actual[(width or 256, height or 256)] = (group[entry:entry + 12], resources.get((icon_type, icon_id)))
    if expected != actual:
        raise RuntimeError("Az EXE erőforrás-ikonja eltér a rögzített alkalmazásikontól.")


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
                        f"/{GRAPHICS.as_posix()}/themes.json",
                        f"/{GRAPHICS.as_posix()}/manifest.json",
                        f"/{GRAPHICS.as_posix()}/role-icons.json",
                    ))):
                raise RuntimeError(f"Váratlan adatfájl a Windows ZIP-ben: {filename}")
        names = set(archive.namelist())
        for resource in (ROOT / GRAPHICS).rglob("*"):
            if resource.is_file():
                filename = f"{APP}/_internal/{resource.relative_to(ROOT).as_posix()}"
                if filename not in names or archive.read(filename) != resource.read_bytes():
                    raise RuntimeError(f"Hiányzó vagy eltérő EDPD grafikai erőforrás: {filename}")
        filenames = {Path(name).name.casefold() for name in archive.namelist()}
        for required in ("qt5core.dll", "qt5widgets.dll", "qwindows.dll", "qwindowsvistastyle.dll"):
            if required not in filenames:
                raise RuntimeError(f"A Windows Qt 5-csomagból hiányzik: {required}")
        archive.extractall(directory)
    application = directory / APP / f"{APP}.exe"
    with application.open("rb") as binary:
        if binary.read(2) != b"MZ":
            raise RuntimeError("A csomag nem Windows futtatható fájlt tartalmaz.")
        binary.seek(0x3c)
        binary.seek(struct.unpack("<I", binary.read(4))[0])
        if binary.read(6) != b"PE\0\0\x64\x86":
            raise RuntimeError("A futtatható fájl nem Windows x64 PE.")
    verify_application_icon(application)
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
            "--icon", str(ROOT / APPLICATION_ICON),
            "--paths", str(ROOT), "--distpath", str(temp / "dist"),
            "--workpath", str(temp / "work"), "--specpath", str(temp),
            "--add-data", f"{ROOT / 'postaszamla/templates/minta.docx'};postaszamla/templates",
            "--add-data", f"{ROOT / GRAPHICS};{GRAPHICS.as_posix()}",
            "--collect-data", "pypdfium2", "--collect-all", "pypdfium2_raw",
            "--hidden-import", "win32timezone", "--exclude-module", "tkinter",
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
