import importlib
import sys
from pathlib import Path

from PySide2.QtGui import QColor, QIcon, QPalette, QPixmap
from PySide2.QtWidgets import QComboBox, QHeaderView, QLabel, QStyleFactory, QTableWidget, QVBoxLayout, QWidget

from postaszamla.settings import DEFAULT_UI_STYLE

ICON_DIR = Path(__file__).resolve().parents[1] / "icons"
# Sprite layout from the existing Postaszámla Crystal Remix assets.
ICON_NAMES = ("about", "docx", "edit", "first", "fit-page", "fit-width", "help", "last", "new", "next",
              "open", "pdf-missing", "pdf-present", "previous", "print", "refresh", "settings",
              "zoom-in", "zoom-out")

ICON_SIZES = (16, 20, 24, 28, 30, 32, 36, 42, 48, 56, 64)

THEME = "Windows XP Luna Blue"
FACTORY_STYLES = (("fusion", "Fusion"), ("windows", "Windows"), ("windowsvista", "Windows Vista"))
REFERENCE_ICONS = {
    "about": "about", "first": "first", "last": "last", "previous": "previous", "next": "next",
    "print": "print", "refresh": "refresh", "settings": "settings",
    "fit-width": "width", "fit-page": "page", "zoom-in": "zoom_in", "zoom-out": "zoom_out",
}


def style_choices():
    keys = {key.casefold() for key in QStyleFactory.keys()}
    return [(DEFAULT_UI_STYLE, THEME), *(
        (key, label) for key, label in FACTORY_STYLES
        if key in keys and QStyleFactory.create(key) is not None
    )]


class ProportionalTable(QTableWidget):
    def __init__(self, headers, ratios):
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.ratios = tuple(ratios)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(50)
        header.sectionResized.connect(self.remember)
        self.adjusting = False

    def resizeEvent(self, event):
        self.adjusting = True
        try:
            super().resizeEvent(event)
            available = self.viewport().width()
            for index, share in enumerate(self.ratios):
                self.setColumnWidth(index, max(50, round(available * share)))
        finally:
            self.adjusting = False

    def remember(self, *_):
        if not self.adjusting and self.isVisible():
            widths = [self.columnWidth(index) for index in range(self.columnCount())]
            self.ratios = tuple(width / sum(widths) for width in widths)


class Appearance:
    def __init__(self, app, edpd_checkout=None):
        self.app = app
        self.current_style = DEFAULT_UI_STYLE
        self.table = ProportionalTable
        self.combo = QComboBox
        self.reference_icons = None
        self.cache = {}
        self.sheets = {}
        self.source = None
        self.reference_style = None
        self.reference_default_surface = None
        if edpd_checkout is None:
            apply_standalone_theme(app)
        else:
            self.use_edpd(app, edpd_checkout)
        self.luna_palette = app.palette()
        self.luna_stylesheet = app.styleSheet()
        app.setProperty("surfaceTheme", THEME)

    def apply(self, requested):
        style = requested if requested in dict(style_choices()) else DEFAULT_UI_STYLE
        if style == self.current_style:
            return
        luna = style == DEFAULT_UI_STYLE
        factory_key = "fusion" if luna else style
        if self.reference_style:
            self.reference_style(factory_key, THEME if luna else self.reference_default_surface)
            if luna:
                self.app.setPalette(self.luna_palette)
        else:
            app = self.app
            # EDPD clears the surface before switching and explicitly restores the factory palette.
            app.setStyleSheet("")
            app.setStyle(QStyleFactory.create(factory_key))
            app.setPalette(self.luna_palette if luna else app.style().standardPalette())
            if luna:
                app.setStyleSheet(self.luna_stylesheet)
        self.current_style = style
        self.app.setProperty("surfaceTheme", THEME if luna else "")

    def use_edpd(self, app, checkout):
        root = Path(checkout).resolve() / "src"
        if not (root / "edpd" / "ui" / "appearance.py").is_file():
            raise ValueError("A megadott mappában nem található az EDPD 2.6.3 forrása.")
        sys.path.insert(0, str(root))
        try:
            edpd = importlib.import_module("edpd")
            if edpd.__version__ != "2.6.3" or Path(edpd.__file__).resolve().parent != root / "edpd":
                raise ValueError("A grafikai referencia az EDPD 2.6.3 helyi munkapéldánya.")
            appearance = importlib.import_module("edpd.ui.appearance")
            themes = importlib.import_module("edpd.ui.themes")
            surfaces = importlib.import_module("edpd.surface_styles")
            widgets = importlib.import_module("edpd.ui.themes.widgets")
            icons = importlib.import_module("edpd.ui.icons")
            tables = importlib.import_module("edpd.ui.proportional_table")
            appearance.apply_style("Fusion", THEME)
            if themes.manager().name != THEME or not app.styleSheet():
                raise RuntimeError("Az EDPD Luna témáját nem sikerült betölteni.")
            self.reference_style = appearance.apply_style
            self.reference_default_surface = surfaces.DEFAULT_SURFACE
            self.reference_icons = icons.IconThemeManager()
            self.table = tables.ProportionalTable
            self.combo = widgets.SurfaceComboBox
            self.source = root
        finally:
            sys.path.remove(str(root))

    def icon(self, name):
        if name in self.cache:
            return self.cache[name]
        if self.reference_icons and name in REFERENCE_ICONS:
            icon = self.reference_icons.icon(REFERENCE_ICONS[name])
        else:
            icon = QIcon()
            index = ICON_NAMES.index(name)
            for size in (16, 24, 32, 48, 64):
                if size not in self.sheets:
                    self.sheets[size] = QPixmap(str(ICON_DIR / "png" / f"{size}.png"))
                icon.addPixmap(self.sheets[size].copy(index * size, 0, size, size))
        self.cache[name] = icon
        return icon


def panel(title, content):
    widget = QWidget()
    widget.setObjectName("edpd-panel")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(5)
    header = QLabel(title)
    header.setObjectName("panel-title")
    header.setMinimumHeight(27)
    layout.addWidget(header)
    layout.addWidget(content, 1)
    return widget


def apply_standalone_theme(app):
    app.setStyle("Fusion")
    palette = app.palette()
    for role, color in (
        (QPalette.Window, "#ece9d8"), (QPalette.Base, "#fff"), (QPalette.Text, "#161b26"),
        (QPalette.Button, "#f1eedf"), (QPalette.AlternateBase, "#f0f5fc"),
        (QPalette.Highlight, "#3266b5"), (QPalette.HighlightedText, "#fff"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet("""
QMainWindow, QDialog { background: #ece9d8; }
QWidget#edpd-panel { background: white; border: 1px solid #7d9fd4; }
QLabel#panel-title { color: white; font-weight: bold; padding: 3px 8px; border: 1px solid #254b9d;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #5c98ee,stop:0.42 #2769c9,stop:1 #1a49a2); }
QToolBar, QStatusBar, QHeaderView::section, QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #fffefa,stop:1 #e1ddcb);
    border: 1px solid #aaa58e; border-top-color: #fff; padding: 4px; }
QHeaderView::section { font-weight: bold; }
QPushButton { padding: 5px 14px; }
QPushButton:hover, QToolButton:hover { background: #fff2c4; border: 1px solid #d99b31; }
QToolButton { border: 1px solid transparent; padding: 3px 5px; }
QToolButton:checked { background: #d5e3fb; border: 1px solid #5278af; }
QScrollArea#pdf-scroll, QWidget#pdf-viewport { background: #7f8ca1; }
QTableView { gridline-color: #dce5f1; border: 1px solid #9aacca; }
QLineEdit, QComboBox, QSpinBox, QDateEdit { background: white; border: 1px solid #8aa0bb; padding: 3px; }
""")
