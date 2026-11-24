"""Resolve and bind EDPD and Postaszámla icon roles."""
import json
from pathlib import Path

import shiboken2
from PySide2.QtCore import QObject, Signal
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication, QStyle

from postaszamla.settings import DEFAULT_ICON_THEME

ASSETS = Path(__file__).resolve().parent / "assets"
APPLICATION_ICON = "application.ico"
ICON_ROLE = "postaszamlaIconRole"
CRYSTAL_ICON_THEME = "Crystal SVG"

ALIASES = {
    "pdf-present": "pdf", "generate-pdf": "pdf", "invoice-delete": "delete",
    "zoom-in": "zoom_in", "zoom-out": "zoom_out", "fit-width": "width", "fit-page": "page",
}
STANDARD = {
    "about": "SP_MessageBoxInformation", "warning": "SP_MessageBoxWarning",
    "question": "SP_MessageBoxQuestion", "first": "SP_MediaSkipBackward",
    "previous": "SP_ArrowLeft", "next": "SP_ArrowRight", "last": "SP_MediaSkipForward",
    "new": "SP_FileIcon", "docx": "SP_FileIcon", "save": "SP_DialogSaveButton",
    "edit": "SP_FileDialogContentsView", "open": "SP_DialogOpenButton",
    "help": "SP_DialogHelpButton", "cancel": "SP_DialogCancelButton",
    "confirm": "SP_DialogYesButton", "delete": "SP_TrashIcon", "refresh": "SP_BrowserReload",
    "settings": "SP_FileDialogDetailedView", "pdf": "SP_FileIcon",
    "clear-input": "SP_LineEditClearButton",
}
APP_ROLES = (
    "new", "edit", "open", "print", "refresh", "settings", "about", "help",
    "docx", "pdf-present", "generate-pdf", "invoice-add", "invoice-delete",
    "save", "cancel", "confirm", "question", "warning", "first", "previous", "next", "last",
    "zoom-in", "zoom-out", "fit-width", "fit-page", "clear-input",
    "undo", "redo", "cut", "copy", "paste", "delete", "select-all",
)


class IconThemeManager(QObject):
    changed = Signal(str)

    def __init__(self, root=ASSETS):
        super().__init__()
        self.root = Path(root)
        self.name = DEFAULT_ICON_THEME
        self.cache = {}
        self.sources = {}
        self.provenance = {}
        self.themes = self.read_json("themes.json")["themes"]
        self.supplement = self.read_json("role-icons.json")
        self.application_icon = QIcon(str(self.root / APPLICATION_ICON))

    def read_json(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def choices(self):
        return tuple(name for name, record in self.themes.items()
                     if name == CRYSTAL_ICON_THEME or (self.root / "themes" / record["id"]).is_dir())

    def set_theme(self, name):
        if name not in self.choices():
            name = DEFAULT_ICON_THEME
        if self.name != name:
            self.name = name
            self.cache.clear()
            self.sources.clear()
            self.provenance.clear()
            self.changed.emit(name)
        return name

    def refresh_standard_icons(self):
        for role in tuple(self.provenance):
            if self.provenance[role]["kind"] == "qt":
                self.provenance.pop(role)
                self.sources.pop(role)
                self.cache.pop(role)
        self.changed.emit(self.name)

    def themed_paths(self, theme, role, asset_role):
        extra = self.supplement.get(theme, {}).get("roles", {}).get(role)
        if extra and (self.root / extra["icon"]).is_file():
            return [extra["icon"]]
        record = self.themes[theme]
        if theme == CRYSTAL_ICON_THEME:
            paths = [f"icons/{size}/{asset_role}.png" for size in (22, 32, 48)]
        elif asset_role in record["icons"]:
            paths = [f"themes/{record['id']}/{size}/{asset_role}.png" for size in (22, 40)]
        else:
            paths = []
        return [path for path in paths if (self.root / path).is_file()]

    def describe(self, role):
        """Report the chosen source without depending on pixmap cache keys or the OS."""
        if role == "application":
            return {"kind": "fixed", "source": "Postaszámla", "paths": [APPLICATION_ICON]}
        canonical = ALIASES.get(role, role)
        if role not in self.provenance:
            for theme in dict.fromkeys((self.name, CRYSTAL_ICON_THEME)):
                if paths := self.themed_paths(theme, role, canonical):
                    return {"kind": "theme" if theme == self.name else "crystal", "source": theme, "paths": paths}
            if standard := STANDARD.get(canonical):
                return {"kind": "qt", "source": "Qt standard", "standard": standard, "paths": []}
            return {"kind": "none", "source": "none", "paths": []}
        return self.provenance[role]

    def icon(self, role):
        if role == "application":
            return self.application_icon
        if role not in self.cache:
            rule = self.describe(role)
            result = QIcon()
            for path in rule["paths"]:
                result.addFile(str(self.root / path))
            if rule["kind"] == "qt":
                style = QApplication.instance().style()
                result = style.standardIcon(getattr(QStyle, rule["standard"]))
            self.cache[role] = result
            self.sources[role] = rule["source"]
            self.provenance[role] = rule
        return self.cache[role]

    def subscribe(self, widget, refresh):
        # Qt owns the C++ objects. Keep the Python wrapper for the duration of
        # the binding as actions and buttons may have no other Python reference.
        def update(*_):
            if shiboken2.isValid(widget):
                refresh(widget)

        self.changed.connect(update)

        def disconnect(*_):
            try:
                self.changed.disconnect(update)
            except (RuntimeError, TypeError):
                pass

        widget.destroyed.connect(disconnect)

    def bind(self, widget, role):
        widget.setProperty(ICON_ROLE, role)

        def refresh(target):
            target.setIcon(self.icon(role))

        refresh(widget)
        self.subscribe(widget, refresh)
        return widget
