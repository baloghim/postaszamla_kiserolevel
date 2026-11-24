from dataclasses import replace
from datetime import date

from PySide2.QtCore import QDate, QPoint, Qt, Signal
from PySide2.QtWidgets import (
    QCalendarWidget, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QSizePolicy, QTabBar, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout, QWidget, QWidgetAction,
)

from postaszamla.finance import calculate, forints
from postaszamla.filename import make_filename
from postaszamla.forms import amount, form_date
from postaszamla.models import Cost, Costs, SERVICES
from postaszamla.records import Invoice, Record, period, total_costs

from .appearance import panel
from .icon_widgets import IconLineEdit
EMPTY_COSTS = Costs(*(Cost(0, 0) for _ in SERVICES))
SERVICE_NAMES = tuple(name for name, _ in SERVICES) + ("Mindösszesen",)
EMPTY_DATE = date.min


def blank_invoice():
    return Invoice("", EMPTY_DATE, EMPTY_DATE, EMPTY_COSTS)


class DateBox(QWidget):
    dateChanged = Signal()

    def __init__(self, value, icons):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        self.input = IconLineEdit(icons)
        self.input.setPlaceholderText("ÉÉÉÉ.HH.NN.")
        self.input.textChanged.connect(lambda _: self.dateChanged.emit())
        self.setFocusProxy(self.input)
        row.addWidget(self.input)
        button = QToolButton()
        button.setArrowType(Qt.DownArrow)
        button.setToolTip("Naptár megnyitása")
        button.setAccessibleName("Naptár megnyitása")
        button.clicked.connect(self.show_calendar)
        row.addWidget(button)
        self.menu = QMenu(self)
        calendar_action = QWidgetAction(self.menu)
        self.calendar = QCalendarWidget(self.menu)
        self.calendar.setMinimumDate(QDate(1, 1, 1))
        self.calendar.setMaximumDate(QDate(9999, 12, 31))
        self.calendar.clicked.connect(self.choose_date)
        self.calendar.activated.connect(self.choose_date)
        calendar_action.setDefaultWidget(self.calendar)
        self.menu.addAction(calendar_action)
        self.setDate(QDate(value.year, value.month, value.day))

    def date(self):
        try:
            parsed = form_date(self.input.text(), "Dátum")
        except ValueError:
            parsed = EMPTY_DATE
        return QDate(parsed.year, parsed.month, parsed.day)

    def setDate(self, day):
        self.input.setText("" if day.toPython() == EMPTY_DATE else day.toString("yyyy.MM.dd."))

    def show_calendar(self):
        day = self.date()
        self.calendar.setSelectedDate(QDate.currentDate() if day.toPython() == EMPTY_DATE else day)
        self.menu.popup(self.mapToGlobal(QPoint(0, self.height())))
        self.calendar.setFocus()

    def choose_date(self, day):
        self.setDate(day)
        self.menu.close()


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
    def __init__(self, appearance, settings, save, parent=None, record=None):
        super().__init__(parent)
        self.appearance = appearance
        self.save_record = save
        self.editing = record is not None
        self.saved_path = None
        if record is None:
            record = Record("", settings.clerk, settings.signer, settings.position, date.today(),
                            EMPTY_DATE, (blank_invoice(),))
        self.setWindowTitle("Kísérőlevél szerkesztése" if self.editing else "Új kísérőlevél létrehozása")
        self.setWindowModality(Qt.WindowModal)
        self.resize(1320, 775)
        self.setMinimumSize(900, 700)
        self.invoices = list(record.invoices)
        self.current = -1
        self.loading = False
        self.invalid_costs = set()
        self.invoice_inputs = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(panel("Kísérőlevél közös adatai", self.build_common(record)))
        layout.addWidget(panel("Postaszámlák", self.build_invoices(appearance)), 3)
        self.summary = cost_table()
        layout.addWidget(panel("Kísérőlevél összesítése", self.summary), 2)

        self.period_preview = QLabel()
        layout.addWidget(self.period_preview)
        self.file_preview = QLabel()
        self.file_preview.setObjectName("file-preview")
        self.file_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.file_preview.setWordWrap(True)
        self.file_preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.file_preview)
        row = QHBoxLayout()
        self.feedback = QLabel()
        self.feedback.setTextFormat(Qt.PlainText)
        row.addWidget(self.feedback, 1)
        buttons = QDialogButtonBox()
        appearance.icons.bind(buttons.addButton("Mentés", QDialogButtonBox.AcceptRole), "save")
        buttons.accepted.connect(self.submit)
        appearance.icons.bind(buttons.addButton("Mégse", QDialogButtonBox.RejectRole), "cancel")
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
        icons = self.appearance.icons
        self.common = {
            "reference": IconLineEdit(icons, record.reference),
            "clerk": IconLineEdit(icons, record.clerk),
            "dated": DateBox(record.dated, icons),
            "sent": DateBox(record.sent, icons),
            "signer": IconLineEdit(icons, record.signer),
            "position": IconLineEdit(icons, record.position),
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
        add = appearance.icons.bind(QPushButton("Számla hozzáadása"), "invoice-add")
        add.clicked.connect(self.add_invoice)
        top.addWidget(add)
        self.remove_button = appearance.icons.bind(QPushButton("Számla eltávolítása"), "invoice-delete")
        self.remove_button.clicked.connect(self.remove_invoice)
        top.addWidget(self.remove_button)
        layout.addLayout(top)
        row = QHBoxLayout()
        fields = QFormLayout()
        self.number = IconLineEdit(appearance.icons)
        self.start = DateBox(EMPTY_DATE, appearance.icons)
        self.end = DateBox(EMPTY_DATE, appearance.icons)
        fields.addRow("Számlaszám", self.number)
        fields.addRow("Időszak kezdete", self.start)
        fields.addRow("Időszak vége", self.end)
        row.addLayout(fields, 1)
        self.costs = cost_table()
        self.editors = []
        for index in range(4):
            pair = []
            for column in (1, 2):
                field = IconLineEdit(appearance.icons)
                field.setAlignment(Qt.AlignRight)
                field.textChanged.connect(self.update_invoice)
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
                operating.setText(str(cost.operating))
                benefits.setText(str(cost.benefits))
            if index in self.invoice_inputs:
                for field, text in zip(self.input_fields(), self.invoice_inputs[index], strict=True):
                    field.setText(text)
        finally:
            self.loading = False
        self.remove_button.setEnabled(len(self.invoices) > 1)
        self.show_invoice_amounts()
        self.refresh_summary()

    def add_invoice(self):
        self.invoices.append(blank_invoice())
        self.tabs.setCurrentIndex(self.tabs.addTab(f"{len(self.invoices)}. számla"))
        self.number.setFocus()

    def remove_invoice(self):
        if len(self.invoices) < 2 or self.appearance.message(
            QMessageBox.Question, self, "Számla eltávolítása", "Eltávolítja a kijelölt számlát?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        index = self.current
        self.invoices.pop(index)
        self.invoice_inputs = {
            key - (key > index): value for key, value in self.invoice_inputs.items() if key != index
        }
        self.invalid_costs = {
            key - (key > index) for key in self.invalid_costs if key != index
        }
        self.tabs.blockSignals(True)
        try:
            self.tabs.removeTab(index)
            for position in range(self.tabs.count()):
                self.tabs.setTabText(position, f"{position + 1}. számla")
            self.tabs.setCurrentIndex(min(index, len(self.invoices) - 1))
        finally:
            self.tabs.blockSignals(False)
        self.select_invoice(self.tabs.currentIndex())

    def show_invoice_amounts(self):
        show_amounts(self.costs, self.invoices[self.current].costs)
        if self.current in self.invalid_costs:
            for row in range(self.costs.rowCount()):
                for column in (1, 2, 3):
                    self.costs.item(row, column).setText("—")

    def update_invoice(self, *_):
        if self.loading or self.current < 0:
            return
        texts = tuple(field.text() for pair in self.editors for field in pair)
        self.invoice_inputs[self.current] = tuple(field.text() for field in self.input_fields())
        costs = self.invoices[self.current].costs
        try:
            values = tuple(map(amount, texts))
        except ValueError:
            self.invalid_costs.add(self.current)
        else:
            costs = Costs(*(Cost(values[i], values[i + 1]) for i in range(0, len(values), 2)))
            self.invalid_costs.discard(self.current)
        self.invoices[self.current] = replace(self.invoices[self.current], number=self.number.text().strip(),
                                             start=self.start.date().toPython(), end=self.end.date().toPython(),
                                             costs=costs)
        self.show_invoice_amounts()
        self.refresh_summary()

    def input_fields(self):
        return (self.start.input, self.end.input, *(field for pair in self.editors for field in pair))

    def draft(self):
        if self.invalid_costs:
            raise ValueError(f"A(z) {min(self.invalid_costs) + 1}. számla költségei hibásak.")
        if any(self.common[key].date().toPython() == EMPTY_DATE for key in ("sent", "dated")):
            raise ValueError("Adja meg a keltezést és a megküldés dátumát.")
        invoices = tuple(self.invoices)
        self.invoice_period()
        return Record(self.common["reference"].text().strip(), self.common["clerk"].text().strip(),
                      self.common["signer"].text().strip(), self.common["position"].text().strip(),
                      self.common["dated"].date().toPython(), self.common["sent"].date().toPython(),
                      invoices)

    def invoice_period(self):
        for index, invoice in enumerate(self.invoices, 1):
            if EMPTY_DATE in (invoice.start, invoice.end):
                raise ValueError(f"Adja meg a(z) {index}. számla időszakát.")
        return period(tuple(self.invoices))

    def refresh_summary(self, *_):
        costs = total_costs(tuple(invoice.costs for invoice in self.invoices))
        show_amounts(self.summary, costs)
        if self.invalid_costs:
            for row in range(self.summary.rowCount()):
                for column in (1, 2, 3):
                    self.summary.item(row, column).setText("—")
        try:
            start, end = self.invoice_period()
        except ValueError:
            self.period_preview.setText("Összesített időszak: —")
            name = "—"
        else:
            self.period_preview.setText(f"Összesített időszak: {start:%Y.%m.%d.} – {end:%Y.%m.%d.}")
            try:
                name = make_filename(start, end, costs) if not self.invalid_costs else "—"
            except ValueError:
                name = "—"
        self.file_preview.setText(f"Fájlnév előnézete: {name}")
        self.feedback.clear()

    def submit(self):
        try:
            record = self.draft()
            record.to_letter()
            if self.editing and self.appearance.message(
                QMessageBox.Question, self, "Mentés megerősítése", "Menti a kijelölt kísérőlevél módosításait?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            ) != QMessageBox.Yes:
                return
            self.saved_path = self.save_record(record)
        except (OSError, ValueError) as error:
            self.feedback.setText(str(error))
            return
        self.accept()
