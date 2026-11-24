"""EDPD's manifest-driven icon loader with Postaszámla roles."""
import json
import weakref
from pathlib import Path

import shiboken2
from PySide2.QtCore import QObject, Signal
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication, QStyle

from postaszamla.settings import DEFAULT_ICON_THEME

ASSETS = Path(__file__).resolve().parent / "assets"

# Reuse EDPD artwork for equivalent actions. The remaining document and dialog
# actions use Qt's standard icons via the last step of EDPD's fallback.
ROLE_ALIASES = {
    "new": "mail", "pdf-present": "pdf", "pdf-missing": "warning",
    "invoice-add": "mail", "invoice-delete": "delete", "question": "warning",
    "zoom-in": "zoom_in", "zoom-out": "zoom_out", "fit-width": "width", "fit-page": "page",
}
STANDARD = {
    "about": QStyle.SP_MessageBoxInformation, "warning": QStyle.SP_MessageBoxWarning,
    "first": QStyle.SP_MediaSkipBackward, "previous": QStyle.SP_ArrowLeft,
    "next": QStyle.SP_ArrowRight, "last": QStyle.SP_MediaSkipForward,
    "save": QStyle.SP_DialogSaveButton, "edit": QStyle.SP_FileDialogContentsView,
    "open": QStyle.SP_DialogOpenButton, "help": QStyle.SP_DialogHelpButton,
    "cancel": QStyle.SP_DialogCancelButton, "confirm": QStyle.SP_DialogYesButton,
    "delete": QStyle.SP_TrashIcon, "refresh": QStyle.SP_BrowserReload,
    "settings": QStyle.SP_FileDialogDetailedView, "pdf": QStyle.SP_FileIcon,
}


class IconThemeManager(QObject):
    changed = Signal(str)

    def __init__(self, root=ASSETS):
        super().__init__()
        self.root = Path(root)
        self.name = DEFAULT_ICON_THEME
        self.cache = {}
        self.sources = {}
        self.themes = json.loads((self.root / "themes.json").read_text(encoding="utf-8"))["themes"]

    def choices(self):
        return tuple(name for name, record in self.themes.items()
                     if name == DEFAULT_ICON_THEME or (self.root / "themes" / record["id"]).is_dir())

    def set_theme(self, name):
        if name not in self.choices():
            name = DEFAULT_ICON_THEME
        if self.name != name:
            self.name = name
            self.cache.clear()
            self.sources.clear()
            self.changed.emit(name)
        return name

    def refresh_standard_icons(self):
        for role in tuple(self.sources):
            if self.sources[role] == "Qt standard":
                self.sources.pop(role)
                self.cache.pop(role)
        self.changed.emit(self.name)

    def icon(self, name):
        role = ROLE_ALIASES.get(name, name)
        if role in self.cache:
            return self.cache[role]
        result = QIcon()
        source = self.name
        record = self.themes.get(self.name, {})
        if self.name != DEFAULT_ICON_THEME and role in record.get("icons", {}):
            for size in (22, 40):
                path = self.root / "themes" / record["id"] / str(size) / (role + ".png")
                if path.is_file():
                    result.addFile(str(path))
        if result.isNull():
            source = DEFAULT_ICON_THEME
            for size in (22, 32, 48):
                path = self.root / "icons" / str(size) / (role + ".png")
                if path.is_file():
                    result.addFile(str(path))
        if result.isNull():
            source = "Qt standard"
            result = QApplication.instance().style().standardIcon(STANDARD.get(role, QStyle.SP_FileIcon))
        self.cache[role], self.sources[role] = result, source
        return result

    def subscribe(self, widget, refresh):
        reference = weakref.ref(widget)

        def update(*_):
            target = reference()
            if target is not None and shiboken2.isValid(target):
                refresh(target)

        self.changed.connect(update)

        def disconnect(*_):
            try:
                self.changed.disconnect(update)
            except (RuntimeError, TypeError):
                pass

        widget.destroyed.connect(disconnect)

    def bind(self, widget, role, setter="setIcon"):
        def refresh(target):
            getattr(target, setter)(self.icon(role))

        refresh(widget)
        self.subscribe(widget, refresh)
        return widget
