from PySide2.QtCore import QSize, Qt
from PySide2.QtWidgets import (
    QAbstractItemView, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QSizePolicy,
    QSplitter, QTableWidgetItem, QToolBar, QVBoxLayout, QWidget,
)

from .appearance import THEME, panel
from .demo import archive_rows, demo_pdf, filename
from .editor import LetterDialog
from .viewer import Preview


def period_label(letters):
    return f"{letters.start:%Y.%m.%d.} – {letters.end:%Y.%m.%d.}"


class MainWindow(QMainWindow):
    def __init__(self, appearance):
        super().__init__()
        self.setObjectName("edpd-window")
        self.setWindowTitle("Postaszámla – Kísérőlevelek | Qt 5 prototípus")
        self.setWindowIcon(appearance.icon("docx"))
        self.setMinimumSize(1000, 650)
        self.appearance = appearance
        self.rows = tuple(archive_rows())
        self.visible_rows = []
        self.current = None
        self.dialog = None
        self.pdfs = {}
        self.build_toolbar()
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        left = QSplitter(Qt.Vertical)
        left.setChildrenCollapsible(False)
        left.addWidget(self.build_archive())
        left.addWidget(self.build_details())
        left.setStretchFactor(0, 5)
        left.setStretchFactor(1, 1)
        left.setSizes((720, 185))
        self.preview = Preview(appearance)
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)
        bar = self.statusBar()
        bar.setObjectName("edpd-status")
        self.count = QLabel()
        bar.addPermanentWidget(self.count)
        bar.addPermanentWidget(QLabel("Qt 5 prototípus"))
        self.reload()

    def build_toolbar(self):
        toolbar = QToolBar(self)
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        for icon, text, action in (
            ("new", "Új kísérőlevél", self.open_editor),
            ("edit", "Szerkesztés", lambda: self.open_editor(use_selection=True)),
            ("open", "Megnyitás Wordben", None),
            ("print", "Nyomtatás", None),
            ("refresh", "Frissítés", self.reload),
        ):
            button = toolbar.addAction(self.appearance.icon(icon), text)
            if action is None:
                button.setEnabled(False)
                button.setToolTip(f"{text} · a fiktív dokumentumtárhoz nem elérhető")
            else:
                button.triggered.connect(action)
            if icon == "edit":
                self.edit_action = button
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        for icon, text, message in (
            ("settings", "Beállítások", f"A prototípus felületi témája: {THEME}."),
            ("about", "Névjegy", "Postaszámla · PySide2 és Qt 5 felületi prototípus."),
            ("help", "Súgó", "Válasszon mintalevelet, vagy nyissa meg az Új kísérőlevél ablakot."),
        ):
            action = toolbar.addAction(self.appearance.icon(icon), text)
            action.triggered.connect(lambda checked=False, hint=message: self.statusBar().showMessage(hint, 6000))

    def build_archive(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Év"))
        self.year = self.appearance.combo()
        self.year.addItems(sorted({str(record.invoices[0].start.year) for record, _ in self.rows}, reverse=True))
        filter_row.addWidget(self.year)
        filter_row.addWidget(QLabel("Fájlnév keresése"))
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        filter_row.addWidget(self.search, 1)
        layout.addLayout(filter_row)
        self.table = self.appearance.table(("Fájlnév", "Időszak", "Számlák", "PDF"), (.58, .25, .10, .07))
        if self.appearance.source:
            self.table.minimum_widths = (260, 190, 85, 52)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setIconSize(QSize(20, 20))
        self.table.cellDoubleClicked.connect(lambda *_: self.open_editor(use_selection=True))
        self.table.itemSelectionChanged.connect(self.select)
        layout.addWidget(self.table, 1)
        self.year.currentTextChanged.connect(self.reload)
        self.search.textChanged.connect(self.reload)
        return panel("Kísérőlevelek", content)

    def build_details(self):
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(4, 4, 4, 4)
        self.details = {}
        labels = ("Iktatószám", "Ügyintéző", "Aláíró", "Beosztás",
                  "Keltezés", "Megküldés dátuma", "Számlák száma", "Összesített időszak")
        for index, label in enumerate(labels):
            column, row = divmod(index, 4)
            grid.addWidget(QLabel(label), row, column * 2)
            value = QLabel("—")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.details[label] = value
            grid.addWidget(value, row, column * 2 + 1)
            grid.setColumnStretch(column * 2 + 1, 1)
        return panel("A kijelölt kísérőlevél adatai", content)

    def reload(self, *_):
        current = self.current
        self.visible_rows = [
            (record, has_pdf) for record, has_pdf in self.rows
            if str(record.invoices[0].start.year) == self.year.currentText()
            and self.search.text().casefold() in filename(record).casefold()
        ]
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.visible_rows))
            self.table.clearSelection()
            for row, (record, has_pdf) in enumerate(self.visible_rows):
                letter = record.to_letter()
                values = (filename(record), period_label(letter), f"{len(record.invoices)} db", "")
                for column, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    if column == 0:
                        item.setIcon(self.appearance.icon("docx"))
                        item.setToolTip(text)
                    else:
                        item.setTextAlignment(Qt.AlignCenter)
                    if column == 3:
                        item.setIcon(self.appearance.icon("pdf-present" if has_pdf else "pdf-missing"))
                        item.setToolTip("Van kapcsolódó PDF" if has_pdf else "Nincs kapcsolódó PDF")
                    self.table.setItem(row, column, item)
                if record == current:
                    self.table.selectRow(row)
        finally:
            self.table.blockSignals(False)
        self.count.setText(f"{self.year.currentText()}  |  {len(self.visible_rows)} mintalevél")
        self.select()

    def select(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            self.current = None
            self.edit_action.setEnabled(False)
            for value in self.details.values():
                value.setText("—")
            self.preview.clear()
            self.statusBar().showMessage("Válasszon egy fiktív kísérőlevelet.")
            return
        record, has_pdf = self.visible_rows[selected[0].row()]
        self.current = record
        self.edit_action.setEnabled(True)
        values = (record.reference, record.clerk, record.signer, record.position,
                  f"{record.dated:%Y.%m.%d.}", f"{record.sent:%Y.%m.%d.}",
                  f"{len(record.invoices)} db", period_label(record.to_letter()))
        for label, value in zip(self.details.values(), values, strict=True):
            label.setText(value)
        if record not in self.pdfs:
            self.pdfs[record] = demo_pdf(record)
        self.preview.open_data(self.pdfs[record], filename(record))
        self.statusBar().showMessage("Fiktív előnézet  |  " + ("Van kapcsolódó PDF" if has_pdf else "Nincs kapcsolódó PDF"))

    def open_editor(self, checked=False, *, use_selection=False):
        if self.dialog and self.dialog.isVisible():
            self.dialog.raise_()
            return self.dialog
        kwargs = {"record": self.current} if use_selection and self.current else {}
        self.dialog = LetterDialog(self.appearance, self, **kwargs)
        self.dialog.open()
        return self.dialog
