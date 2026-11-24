from PySide2.QtWidgets import QHeaderView, QLabel, QMessageBox, QStyleFactory, QTableWidget, QVBoxLayout, QWidget

from postaszamla.settings import DEFAULT_UI_STYLE

from .edpd_graphics.appearance import apply_style
from .edpd_graphics.icons import ICON_ROLE, IconThemeManager
from .edpd_graphics.surface_styles import DEFAULT_SURFACE, LUNA as THEME, POSTAS_GREEN
from .edpd_graphics.themes.widgets import SurfaceComboBox

SURFACES = {DEFAULT_UI_STYLE: THEME, "longhorn-blue": "Longhorn Blue", "longhorn-slate": "Longhorn Slate",
            "postas-zold": POSTAS_GREEN}
FACTORY_STYLES = (("fusion", "Fusion"), ("windows", "Windows"), ("windowsvista", "Windows Vista"))


def style_choices():
    keys = {key.casefold() for key in QStyleFactory.keys()}
    return [*SURFACES.items(), *((key, label) for key, label in FACTORY_STYLES
                                if key in keys and QStyleFactory.create(key) is not None)]


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
    def __init__(self, app):
        self.app = app
        self.current_style = None
        self.table = ProportionalTable
        self.combo = SurfaceComboBox
        self.icons = IconThemeManager()
        app.setWindowIcon(self.icons.icon("application"))
        self.apply(DEFAULT_UI_STYLE)

    def apply(self, requested, icon_theme=None):
        style = requested
        if style not in SURFACES and style not in dict(style_choices()):
            style = DEFAULT_UI_STYLE
        style_changed = style != self.current_style
        if style_changed:
            surface = SURFACES.get(style, DEFAULT_SURFACE)
            apply_style("fusion" if style in SURFACES else style, surface)
            self.current_style = style
            self.app.setProperty("surfaceTheme", SURFACES.get(style, ""))

        previous_icons = self.icons.name
        if icon_theme is not None:
            self.icons.set_theme(icon_theme)
        if style_changed and self.icons.name == previous_icons:
            self.icons.refresh_standard_icons()

    def icon(self, role):
        return self.icons.icon(role)

    def action(self, toolbar, role, text, callback):
        action = toolbar.addAction(text)
        action.triggered.connect(callback)
        return self.icons.bind(action, role)

    def message(self, kind, parent, title, text, buttons=QMessageBox.Ok, default=QMessageBox.NoButton, *, role=None):
        dialog = QMessageBox(kind, title, text, buttons, parent)
        dialog.setDefaultButton(default)
        role = role or {QMessageBox.Information: "about", QMessageBox.Question: "question"}.get(kind, "warning")
        dialog.setProperty(ICON_ROLE, role)

        def refresh(box):
            box.setIconPixmap(self.icon(role).pixmap(32, 32))

        refresh(dialog)
        if role != "application":
            self.icons.subscribe(dialog, refresh)
        for button, icon in ((QMessageBox.Yes, "confirm"), (QMessageBox.No, "cancel"),
                             (QMessageBox.Ok, "confirm"), (QMessageBox.Cancel, "cancel")):
            if widget := dialog.button(button):
                self.icons.bind(widget, icon)
        result = dialog.exec_()
        dialog.deleteLater()
        return result


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
