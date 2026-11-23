import fitz
from PySide2.QtCore import QEvent, QSize, Qt, QTimer
from PySide2.QtGui import QImage, QPixmap
from PySide2.QtWidgets import QLabel, QScrollArea, QToolBar, QVBoxLayout, QWidget


class Preview(QWidget):
    def __init__(self, appearance):
        super().__init__()
        self.setObjectName("edpd-panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.viewer = appearance.viewer() if appearance.viewer else StandaloneViewer(appearance)
        if appearance.viewer:
            self.viewer.layout().setContentsMargins(0, 0, 0, 0)
            self.viewer.theme_title.setText("Dokumentum-előnézet")
            self.viewer.theme_title.setMinimumHeight(27)
            self.viewer.label.setText("Válasszon egy kísérőlevelet a listából.")
            for action in (self.viewer.print_action, self.viewer.save_action):
                action.setVisible(False)
        layout.addWidget(self.viewer)

    def open_data(self, data, filename):
        self.viewer.open_data(data, filename)

    def clear(self):
        if self.viewer.pdf:
            self.viewer.pdf.close()
            self.viewer.pdf = None
        self.viewer.page = 0
        self.viewer.label.setText("Válasszon egy kísérőlevelet a listából.")
        self.viewer.label.adjustSize()
        self.viewer.page_label.setText("—")


class StandaloneViewer(QWidget):
    def __init__(self, appearance):
        super().__init__()
        self.pdf = None
        self.page = 0
        self.mode = "width"
        self.scale = 1.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Dokumentum-előnézet")
        title.setObjectName("panel-title")
        title.setMinimumHeight(27)
        layout.addWidget(title)
        bar = QToolBar()
        bar.setObjectName("pdf-toolbar")
        bar.setIconSize(QSize(22, 22))
        for icon, text, action in (
            ("first", "Első oldal", lambda: self.move(0)),
            ("previous", "Előző oldal", lambda: self.move(self.page - 1)),
            ("next", "Következő oldal", lambda: self.move(self.page + 1)),
            ("last", "Utolsó oldal", lambda: self.move(len(self.pdf) - 1) if self.pdf else None),
        ):
            bar.addAction(appearance.icon(icon), text, action)
        self.page_label = QLabel("—")
        self.page_label.setMinimumWidth(48)
        self.page_label.setAlignment(Qt.AlignCenter)
        bar.addWidget(self.page_label)
        bar.addSeparator()
        bar.addAction(appearance.icon("zoom-out"), "Kicsinyítés", lambda: self.zoom(0.8))
        bar.addAction(appearance.icon("zoom-in"), "Nagyítás", lambda: self.zoom(1.25))
        bar.addSeparator()
        for icon, text, mode in (("fit-width", "Szélesség", "width"), ("fit-page", "Teljes oldal", "page")):
            action = bar.addAction(appearance.icon(icon), text, lambda checked=False, current=mode: self.fit(current))
            bar.widgetForAction(action).setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        layout.addWidget(bar)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("pdf-scroll")
        self.scroll.viewport().setObjectName("pdf-viewport")
        self.scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.label = QLabel("Válasszon egy kísérőlevelet a listából.")
        self.label.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll, 1)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.render)
        self.scroll.viewport().installEventFilter(self)

    def open_data(self, data, filename):
        if self.pdf:
            self.pdf.close()
        self.pdf = fitz.open(stream=data, filetype="pdf")
        self.page = 0
        self.mode = "width"
        self.render()

    def move(self, page):
        if self.pdf is not None:
            self.page = min(max(0, page), len(self.pdf) - 1)
            self.render()
            self.scroll.verticalScrollBar().setValue(0)

    def fit(self, mode):
        self.mode = mode
        self.render()

    def zoom(self, factor):
        self.mode = None
        self.scale = min(4.0, max(0.1, self.scale * factor))
        self.render()

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Resize and self.mode:
            self.timer.start(0)
        return super().eventFilter(watched, event)

    def render(self):
        if self.pdf is None:
            return
        page = self.pdf[self.page]
        if self.mode:
            available = self.scroll.viewport().size()
            self.scale = max(1, available.width() - 20) / page.rect.width
            if self.mode == "page":
                self.scale = min(self.scale, max(1, available.height() - 20) / page.rect.height)
        pixels = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale), alpha=False)
        image = QImage(pixels.samples, pixels.width, pixels.height, pixels.stride, QImage.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(image))
        self.label.resize(pixels.width, pixels.height)
        self.page_label.setText(f"{self.page + 1} / {len(self.pdf)}")
