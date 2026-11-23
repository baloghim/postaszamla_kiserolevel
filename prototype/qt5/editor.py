from dataclasses import replace
from datetime import date

from PySide2.QtCore import QDate, Qt
from PySide2.QtWidgets import (
    QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSpinBox, QTabBar, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from postaszamla.finance import calculate, forints
from postaszamla.models import Cost, Costs
from postaszamla.records import Invoice, Record, total_costs

from .appearance import panel
from .demo import DEMO, EMPTY_COSTS, SERVICE_NAMES, filename


def date_box(value):
    widget = QDateEdit(QDate(value.year, value.month, value.day))
    widget.setDisplayFormat("yyyy.MM.dd.")
    widget.setCalendarPopup(True)
    return widget


def cost_table():
    widget = QTableWidget(len(SERVICE_NAMES), 4)
    widget.setHorizontalHeaderLabels(("Szolgáltatás megnevezése", "Működési (Ft)", "Ellátás (Ft)", "Összesen (Ft)"))
    widget.verticalHeader().hide()
    widget.verticalHeader().setDefaultSectionSize(30)
    header = widget.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Stretch)
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    header.setMinimumSectionSize(83)
    widget.setAlternatingRowColors(True)
    widget.setSelectionMode(QTableWidget.NoSelection)
    widget.setEditTriggers(QTableWidget.NoEditTriggers)
    widget.setMinimumHeight(188)
    for row, text in enumerate(SERVICE_NAMES):
        for column in range(4):
            item = QTableWidgetItem(text if column == 0 else "")
            if column:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if row == len(SERVICE_NAMES) - 1:
                face = item.font()
                face.setBold(True)
                item.setFont(face)
            widget.setItem(row, column, item)
    return widget


def show_amounts(table, costs):
    for row, amounts in enumerate(calculate(costs, allow_zero=True)):
        for column, amount in enumerate(amounts, start=1):
            table.item(row, column).setText(forints(amount))


class LetterDialog(QDialog):
    def __init__(self, appearance, parent=None, record=DEMO):
        super().__init__(parent)
        self.setWindowTitle("Új kísérőlevél létrehozása")
        self.setWindowModality(Qt.WindowModal)
        self.resize(1320, 775)
        self.setMinimumSize(900, 700)
        self.invoices = list(record.invoices)
        self.current = -1
        self.loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(panel("Kísérőlevél közös adatai", self.build_common(record)))
        layout.addWidget(panel("Postaszámlák", self.build_invoices(appearance)), 3)
        self.summary = cost_table()
        layout.addWidget(panel("Kísérőlevél összesítése", self.summary), 2)

        self.file_preview = QLabel()
        self.file_preview.setObjectName("file-preview")
        self.file_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.file_preview.setWordWrap(True)
        self.file_preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.file_preview)
        row = QHBoxLayout()
        self.feedback = QLabel()
        row.addWidget(self.feedback, 1)
        buttons = QDialogButtonBox()
        check = buttons.addButton("Adatok ellenőrzése", QDialogButtonBox.ActionRole)
        check.setIcon(appearance.icon("docx"))
        check.clicked.connect(self.validate_draft)
        buttons.addButton("Bezárás", QDialogButtonBox.RejectRole)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        layout.addLayout(row)

        for index in range(len(self.invoices)):
            self.tabs.addTab(f"{index + 1}. számla")
        self.select_invoice(0)

    def build_common(self, record):
        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setContentsMargins(4, 2, 4, 2)
        self.common = {
            "reference": QLineEdit(record.reference),
            "clerk": QLineEdit(record.clerk),
            "dated": date_box(record.dated),
            "sent": date_box(record.sent),
            "signer": QLineEdit(record.signer),
            "position": QLineEdit(record.position),
        }
        labels = ("Iktatószám", "Ügyintéző", "Levél keltezése", "Megküldés dátuma", "Aláíró", "Beosztás")
        for index, (widget_field, label) in enumerate(zip(self.common.values(), labels, strict=True)):
            row, column = divmod(index, 3)
            grid.addWidget(QLabel(label), row * 2, column)
            grid.addWidget(widget_field, row * 2 + 1, column)
            grid.setColumnStretch(column, 1)
            signal = widget_field.textChanged if isinstance(widget_field, QLineEdit) else widget_field.dateChanged
            signal.connect(self.refresh_summary)
        return widget

    def build_invoices(self, appearance):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        top.addWidget(self.tabs, 1)
        add = QPushButton(appearance.icon("new"), "Számla hozzáadása")
        add.clicked.connect(self.add_invoice)
        top.addWidget(add)
        layout.addLayout(top)
        row = QHBoxLayout()
        fields = QFormLayout()
        self.number = QLineEdit()
        self.start = date_box(DEMO.dated)
        self.end = date_box(DEMO.dated)
        fields.addRow("Számlaszám", self.number)
        fields.addRow("Időszak kezdete", self.start)
        fields.addRow("Időszak vége", self.end)
        row.addLayout(fields, 1)
        self.costs = cost_table()
        self.editors = []
        for index in range(4):
            pair = []
            for column in (1, 2):
                field = QSpinBox()
                field.setAlignment(Qt.AlignRight)
                field.setRange(0, 2147483647)
                field.setGroupSeparatorShown(True)
                field.valueChanged.connect(self.update_invoice)
                self.costs.setCellWidget(index, column, field)
                pair.append(field)
            self.editors.append(pair)
        row.addWidget(self.costs, 3)
        layout.addLayout(row, 1)
        self.tabs.currentChanged.connect(self.select_invoice)
        self.number.textChanged.connect(self.update_invoice)
        self.start.dateChanged.connect(self.update_invoice)
        self.end.dateChanged.connect(self.update_invoice)
        return widget

    def select_invoice(self, index):
        if not 0 <= index < len(self.invoices):
            return
        self.current = index
        invoice = self.invoices[index]
        self.loading = True
        try:
            self.number.setText(invoice.number)
            self.start.setDate(QDate(invoice.start.year, invoice.start.month, invoice.start.day))
            self.end.setDate(QDate(invoice.end.year, invoice.end.month, invoice.end.day))
            for cost, (operating, benefits) in zip(invoice.costs.rows(), self.editors, strict=True):
                operating.setValue(cost.operating)
                benefits.setValue(cost.benefits)
        finally:
            self.loading = False
        show_amounts(self.costs, invoice.costs)
        self.refresh_summary()

    def add_invoice(self):
        today = date.today()
        self.invoices.append(Invoice("", today, today, EMPTY_COSTS))
        self.tabs.setCurrentIndex(self.tabs.addTab(f"{len(self.invoices)}. számla"))
        self.number.setFocus()

    def update_invoice(self, *_):
        if self.loading or self.current < 0:
            return
        costs = Costs(*(Cost(operating.value(), benefits.value()) for operating, benefits in self.editors))
        self.invoices[self.current] = replace(self.invoices[self.current], number=self.number.text(),
                                             start=self.start.date().toPython(), end=self.end.date().toPython(),
                                             costs=costs)
        show_amounts(self.costs, costs)
        self.refresh_summary()

    def draft(self):
        return Record(self.common["reference"].text(), self.common["clerk"].text(),
                      self.common["signer"].text(), self.common["position"].text(),
                      self.common["dated"].date().toPython(), self.common["sent"].date().toPython(),
                      tuple(self.invoices))

    def refresh_summary(self, *_):
        show_amounts(self.summary, total_costs(tuple(invoice.costs for invoice in self.invoices)))
        try:
            name = filename(self.draft())
        except ValueError:
            name = "A kötelező adatok kitöltése után jelenik meg."
        self.file_preview.setText(f"Fájlnév előnézete  |  {name}")
        self.feedback.clear()

    def validate_draft(self):
        try:
            self.draft().to_letter()
        except ValueError as error:
            self.feedback.setText(str(error))
        else:
            self.feedback.setText("A próbaadatok érvényesek.")
