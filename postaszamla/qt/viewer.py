from contextlib import closing
from queue import Empty, Queue
from threading import Thread

import pypdfium2
from PySide2.QtCore import QEvent, QSize, Qt, QTimer
from PySide2.QtGui import QImage, QPixmap
from PySide2.QtWidgets import QComboBox, QLabel, QPlainTextEdit, QScrollArea, QToolBar, QVBoxLayout, QWidget

from postaszamla.preview import prepare_preview

ZOOMS = ("Szélesség", "Teljes oldal", "50%", "75%", "100%", "125%", "150%", "200%")
STEPS = (50, 75, 100, 125, 150, 200)


def prepare_worker(requests, results):
    while True:
        request = requests.get()
        while request is not None:
            try:
                request = requests.get_nowait()
            except Empty:
                break
        if request is None:
            return
        token, path = request
        try:
            kind, data = prepare_preview(path)
        except Exception:
            kind, data = "error", "Az előnézet nem készíthető el. Nyissa meg a dokumentumot Wordben."
        results.put((token, kind, data))


class Preview(QWidget):
    def __init__(self, appearance, zoom="Szélesség"):
        super().__init__()
        self.setObjectName("edpd-panel")
        self.requests, self.results = Queue(), Queue()
        self.token = object()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.viewer = DocumentViewer(appearance, zoom)
        self.layout.addWidget(self.viewer)
        self.timer = QTimer(self)
        self.timer.setInterval(70)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        Thread(target=prepare_worker, args=(self.requests, self.results), daemon=True).start()

    def select(self, path):
        self.token = object()
        message = "Előnézet készítése…" if path else "Válasszon egy kísérőlevelet a listából."
        self.viewer.show_text(message)
        if path:
            self.requests.put((self.token, path))

    def poll(self):
        while True:
            try:
                token, kind, data = self.results.get_nowait()
            except Empty:
                return
            if token is not self.token:
                continue
            if kind == "pdf":
                self.viewer.open_data(data)
            else:
                hint = "A Word-alapú előnézet nem érhető el.\n\n" if kind == "fallback" else ""
                self.viewer.show_text(hint + data, document=kind in ("text", "fallback"))

    def stop(self):
        self.timer.stop()
        self.requests.put(None)
        self.viewer.clear_pdf()


class DocumentViewer(QWidget):
    def __init__(self, appearance, zoom):
        super().__init__()
        self.pdf = None
        self.page = 0
        self.scale = 1.0
        self.layout = layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Dokumentum-előnézet")
        title.setObjectName("panel-title")
        title.setMinimumHeight(27)
        layout.addWidget(title)
        bar = QToolBar()
        bar.setObjectName("pdf-toolbar")
        bar.setIconSize(QSize(22, 22))
        self.navigation = []
        for icon, text, action in (
            ("first", "Első oldal", lambda: self.move(0)),
            ("previous", "Előző oldal", lambda: self.move(self.page - 1)),
            ("next", "Következő oldal", lambda: self.move(self.page + 1)),
            ("last", "Utolsó oldal", lambda: self.move(len(self.pdf) - 1) if self.pdf else None),
        ):
            self.navigation.append(appearance.action(bar, icon, text, action))
        self.page_label = QLabel("—")
        self.page_label.setMinimumWidth(48)
        self.page_label.setAlignment(Qt.AlignCenter)
        bar.addWidget(self.page_label)
        bar.addSeparator()
        self.scale_actions = [
            appearance.action(bar, "zoom-out", "Kicsinyítés", lambda: self.step_zoom(-1)),
            appearance.action(bar, "zoom-in", "Nagyítás", lambda: self.step_zoom(1)),
        ]
        self.fit_actions = {}
        for icon, text in (("fit-width", "Szélesség"), ("fit-page", "Teljes oldal")):
            action = appearance.action(bar, icon, text, lambda checked=False, mode=text: self.set_zoom(mode))
            action.setCheckable(True)
            bar.widgetForAction(action).setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self.fit_actions[text] = action
        self.zoom = appearance.combo()
        self.zoom.addItems(ZOOMS)
        self.zoom.setCurrentText(zoom)
        self.zoom.currentTextChanged.connect(self.render)
        bar.addWidget(self.zoom)
        layout.addWidget(bar)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("pdf-scroll")
        self.scroll.viewport().setObjectName("pdf-viewport")
        self.scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll, 1)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.hide()
        layout.addWidget(self.text, 1)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.render)
        self.scroll.viewport().installEventFilter(self)
        self.update_controls()

    def clear_pdf(self):
        if self.pdf is not None:
            self.pdf.close()
            self.pdf = None

    def show_text(self, content, *, document=False):
        self.clear_pdf()
        self.page = 0
        self.scroll.setVisible(not document)
        self.text.setVisible(document)
        if document:
            self.text.setPlainText(content)
        else:
            self.label.setText(content)
            self.label.adjustSize()
        self.update_controls()

    def open_data(self, data):
        self.clear_pdf()
        try:
            self.pdf = pypdfium2.PdfDocument(data)
        except Exception:
            self.show_text("A PDF nem nyitható meg. Nyissa meg a dokumentumot Wordben.")
            return
        self.page = 0
        self.text.hide()
        self.scroll.show()
        self.render()
        self.scroll.verticalScrollBar().setValue(0)
        self.scroll.horizontalScrollBar().setValue(0)

    def move(self, page):
        if self.pdf is not None:
            self.page = min(max(0, page), len(self.pdf) - 1)
            self.render()
            self.scroll.verticalScrollBar().setValue(0)
            self.scroll.horizontalScrollBar().setValue(0)

    def set_zoom(self, zoom):
        self.zoom.setCurrentText(zoom)
        self.update_controls()

    def step_zoom(self, direction):
        current = self.scale * 75
        for value in STEPS if direction > 0 else reversed(STEPS):
            if (value - current) * direction > 0.5:
                self.set_zoom(f"{value}%")
                break

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Resize and self.pdf is not None:
            if not self.zoom.currentText().endswith("%"):
                self.timer.start(0)
        return super().eventFilter(watched, event)

    def update_controls(self):
        loaded = self.pdf is not None
        count = len(self.pdf) if loaded else 0
        for index, action in enumerate(self.navigation):
            action.setEnabled(loaded and (self.page > 0 if index < 2 else self.page + 1 < count))
        for action in self.scale_actions:
            action.setEnabled(loaded)
        for mode, action in self.fit_actions.items():
            action.setEnabled(loaded)
            action.setChecked(mode == self.zoom.currentText())
        self.zoom.setEnabled(loaded)
        self.page_label.setText(f"{self.page + 1} / {count}" if loaded else "—")

    def render(self, *_):
        if self.pdf is None:
            return
        mode = self.zoom.currentText()
        try:
            with closing(self.pdf[self.page]) as page:
                width, height = page.get_size()
                viewport = self.scroll.viewport().size()
                scale = max(1, viewport.width() - 20) / width
                if mode == "Teljes oldal":
                    scale = min(scale, max(1, viewport.height() - 20) / height)
                elif mode.endswith("%"):
                    scale = int(mode[:-1]) / 75
                self.scale = min(scale, 4.0)
                with closing(page.render(scale=self.scale, rev_byteorder=True)) as pixels:
                    raster = bytes(pixels.buffer)
                    image = QImage(raster, pixels.width, pixels.height, pixels.stride, QImage.Format_RGB888)
                    self.label.setPixmap(QPixmap.fromImage(image))
                    self.label.resize(pixels.width, pixels.height)
        except Exception:
            self.show_text("A PDF-oldal nem jeleníthető meg. Nyissa meg a dokumentumot Wordben.")
            return
        self.update_controls()
