import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from .template import DEFAULT_TEMPLATE

DEFAULT_UI_STYLE = "xp-luna-blue"
DEFAULT_ICON_THEME = "Crystal SVG"


class InvalidSettings(ValueError):
    pass


def program_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def atomic_json(path: Path, data: dict) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                prefix=".postaszamla-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@dataclass
class Settings:
    version: int = 1
    archive: str = "dokumentumok"
    template: str = ""
    clerk: str = ""
    signer: str = ""
    position: str = ""
    geometry: str = ""
    window_state: str = "zoomed"
    main_sash: int = 0
    list_sash: int = 0
    columns: tuple[int, ...] = (330, 155, 66, 78)
    zoom: str = "Szélesség"
    last_year: str = ""
    ui_style: str = DEFAULT_UI_STYLE
    icon_theme: str = DEFAULT_ICON_THEME

    def resolve(self, base: Path, value: str) -> Path:
        return base / Path(value).expanduser()

    def archive_path(self, base: Path) -> Path:
        return self.resolve(base, self.archive)

    def template_path(self, base: Path) -> Path:
        return self.resolve(base, self.template) if self.template else DEFAULT_TEMPLATE

    def save(self, base: Path) -> None:
        atomic_json(base / "beallitasok.json", asdict(self))


def load_settings(base: Path) -> Settings:
    path = base / "beallitasok.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        settings = Settings()
        settings.save(base)
        return settings
    except (UnicodeError, json.JSONDecodeError) as error:
        raise InvalidSettings("A beallitasok.json fájl nem olvasható JSON-ként.") from error

    defaults = Settings()
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise InvalidSettings("A beállítások formátuma vagy verziója érvénytelen.")
    for name, default in asdict(defaults).items():
        value = data.get(name, default)
        if isinstance(default, tuple):
            if (not isinstance(value, (list, tuple)) or len(value) != len(default)
                    or any(type(item) is not int or not 30 <= item <= 4000 for item in value)):
                raise InvalidSettings(f"Érvénytelen beállítás: {name}.")
            value = tuple(value)
        elif type(value) is not type(default):
            raise InvalidSettings(f"Érvénytelen beállítás: {name}.")
        setattr(defaults, name, value)
    if defaults.window_state not in ("normal", "zoomed") or (
        defaults.geometry and not re.fullmatch(r"[0-9]+x[0-9]+[+-][0-9]+[+-][0-9]+", defaults.geometry)
    ):
        raise InvalidSettings("Érvénytelen főablakméret vagy ablakállapot.")
    if not defaults.archive.strip() or defaults.zoom not in (
        "Szélesség", "Teljes oldal", "50%", "75%", "100%", "125%", "150%", "200%"
    ) or min(defaults.main_sash, defaults.list_sash) < 0:
        raise InvalidSettings("Érvénytelen dokumentumtár, nagyítás vagy panelméret.")
    return defaults


def backup_settings(base: Path) -> Path:
    source = base / "beallitasok.json"
    backup = source.with_name(f"{source.name}.hibas-{uuid4().hex}")
    shutil.copy2(source, backup)
    return backup
