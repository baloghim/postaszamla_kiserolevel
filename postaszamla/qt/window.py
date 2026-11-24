import re
from datetime import date
from pathlib import Path

from PySide2.QtCore import QSize, Qt, QTimer
from PySide2.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QSizePolicy,
    QSplitter, QTableWidgetItem, QToolBar, QVBoxLayout, QWidget,
)

from postaszamla.archive import documents, initial_year, read_record, save_record, year_folders
from postaszamla.preview import word_action
from postaszamla.settings import InvalidSettings, Settings, backup_settings, load_settings

from .appearance import panel, style_choices
from .editor import LetterDialog
from .settings_dialog import SettingsDialog
from .viewer import Preview

VERSION = "0.7.0"


def period_label(dates):
    return " – ".join(f"{day:%Y.%m.%d.}" for day in dates) if dates else "—"


class MainWindow(QMainWindow):
    def __init__(self, appearance, base):
        super().__init__()
        self.setObjectName("edpd-window")
        self.setWindowTitle("Postaszámla – Kísérőlevelek")
        self.setMinimumSize(720, 500)
        self.appearance, self.base = appearance, Path(base)
        self.settings_writable = True
        self.settings = self.start_settings()
        appearance.apply(self.settings.ui_style, self.settings.icon_theme)
        appearance.icons.bind(self, "docx", "setWindowIcon")
        self.visible_rows = []
        self.current = None
        self.metadata = None
        self.dialog = None
        self.sort_column = 1
        self.reverse_sort = True
        self.sash_moved = False
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.reload)
        self.build_toolbar()
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.splitterMoved.connect(self.mark_sash_moved)
        self.left = QSplitter(Qt.Vertical)
        self.left.setChildrenCollapsible(False)
        self.left.addWidget(self.build_archive())
        self.left.addWidget(self.build_details())
        self.left.setStretchFactor(0, 5)
        self.left.setStretchFactor(1, 1)
        self.preview = Preview(appearance, self.settings.zoom)
        self.splitter.addWidget(self.left)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)
        bar = self.statusBar()
        bar.setObjectName("edpd-status")
        self.count = QLabel()
        bar.addPermanentWidget(self.count)
        bar.addPermanentWidget(QLabel(f"v{VERSION}"))
        self.restore_geometry()
        self.reload()

    @property
    def archive(self):
        return self.settings.archive_path(self.base)

    def start_settings(self):
        try:
            return load_settings(self.base)
        except InvalidSettings as error:
            try:
                backup = backup_settings(self.base)
                prompt = f"{error}\n\nBiztonsági másolat: {backup.name}\n\nVisszaállítja az alapbeállításokat?"
                self.settings_writable = self.appearance.message(
                    QMessageBox.Question, self, "Hibás beállítások", prompt,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                ) == QMessageBox.Yes
                if self.settings_writable:
                    Settings().save(self.base)
            except OSError as failure:
                self.settings_writable = False
                self.appearance.message(QMessageBox.Critical, self, "Beállítások", str(failure))
        except OSError as error:
            self.settings_writable = False
            self.appearance.message(QMessageBox.Critical, self, "Beállítások", str(error))
        return Settings()

    def restore_geometry(self):
        geometry = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", self.settings.geometry)
        screen = QApplication.primaryScreen().availableGeometry()
        if geometry:
            width, height, left, top = map(int, geometry.groups())
            width, height = min(width, screen.width()), min(height, screen.height())
            self.resize(width, height)
            self.move(max(screen.left(), min(left, screen.right() - width)),
                      max(screen.top(), min(top, screen.bottom() - height)))
        else:
            self.resize(min(1400, screen.width()), min(900, screen.height()))

    def restore_panels(self):
        width = self.splitter.width()
        left = self.settings.main_sash or width // 2
        self.splitter.setSizes((left, max(1, width - left)))
        height = self.left.height()
        top = self.settings.list_sash or height * 4 // 5
        self.left.setSizes((top, max(1, height - top)))

    def mark_sash_moved(self, *_):
        self.sash_moved = True

    def build_toolbar(self):
        toolbar = QToolBar(self)
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        self.actions = {}
        for icon, text, action in (
            ("new", "Új kísérőlevél", self.open_editor),
            ("edit", "Szerkesztés", lambda: self.open_editor(use_selection=True)),
            ("open", "Megnyitás Wordben", self.open_in_word),
            ("print", "Nyomtatás", lambda: self.open_in_word(printing=True)),
            ("refresh", "Frissítés", self.reload),
        ):
            button = self.appearance.action(toolbar, icon, text, action)
            self.actions[icon] = button
            if icon == "new":
                button.setShortcut("Ctrl+N")
            elif icon == "refresh":
                button.setShortcut("F5")
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        for icon, text, callback in (
            ("settings", "Beállítások", self.configure),
            ("about", "Névjegy", self.about),
            ("help", "Súgó", lambda: self.appearance.message(
                QMessageBox.Information, self, "Súgó", "A Beállításokban adja meg a dokumentumtárat és a Word-sablont. "
                "A leveleket év és fájlnév szerint keresheti.")),
        ):
            self.appearance.action(toolbar, icon, text, callback)

    def about(self):
        style = dict(style_choices())[self.appearance.current_style]
        self.appearance.message(QMessageBox.Information, self, "Névjegy",
                                f"Postaszámla – Kísérőlevelek v{VERSION}\nPySide2 · {style}\n{self.appearance.icons.name}")

    def build_archive(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Év"))
        self.year = self.appearance.combo()
        filter_row.addWidget(self.year)
        filter_row.addWidget(QLabel("Fájlnév keresése"))
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        filter_row.addWidget(self.search, 1)
        layout.addLayout(filter_row)
        total = sum(self.settings.columns)
        self.table = self.appearance.table(("Fájlnév", "Időszak", "Számlák", "PDF"),
                                           tuple(width / total for width in self.settings.columns))
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self.sort_column, Qt.DescendingOrder)
        header.sectionClicked.connect(self.sort_by)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setIconSize(QSize(20, 20))
        self.table.cellDoubleClicked.connect(lambda *_: self.open_editor(use_selection=True))
        self.table.itemSelectionChanged.connect(self.select)
        self.appearance.icons.subscribe(self.table, self.refresh_archive_icons)
        layout.addWidget(self.table, 1)
        self.year.currentTextChanged.connect(self.reload)
        self.search.textChanged.connect(lambda _: self.search_timer.start(230))
        return panel("Kísérőlevelek", content)

    def refresh_archive_icons(self, table):
        docx = self.appearance.icon("docx")
        present = self.appearance.icon("pdf-present")
        missing = self.appearance.icon("pdf-missing")
        for row, entry in enumerate(self.visible_rows):
            table.item(row, 0).setIcon(docx)
            table.item(row, 3).setIcon(present if entry.pdf else missing)

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
            value.setTextFormat(Qt.PlainText)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.details[label] = value
            grid.addWidget(value, row, column * 2 + 1)
            grid.setColumnStretch(column * 2 + 1, 1)
        return panel("A kijelölt kísérőlevél adatai", content)

    def sort_by(self, column):
        self.reverse_sort = not self.reverse_sort if column == self.sort_column else False
        self.sort_column = column
        self.table.horizontalHeader().setSortIndicator(
            column, Qt.DescendingOrder if self.reverse_sort else Qt.AscendingOrder)
        self.reload()

    def reload(self, *_, preferred=None):
        self.search_timer.stop()
        current = preferred or (self.current.path if self.current else None)
        year = preferred.parent.name if preferred else self.year.currentText() or initial_year()
        failure = ""
        try:
            years = sorted(set(year_folders(self.archive) + [year]), reverse=True)
            self.visible_rows = documents(self.archive, year, self.search.text())
        except OSError:
            years = [year]
            self.visible_rows = []
            failure = "A dokumentumtár nem olvasható. Ellenőrizze a beállított elérési utat."
        self.year.blockSignals(True)
        try:
            self.year.clear()
            self.year.addItems(years)
            self.year.setCurrentText(year)
        finally:
            self.year.blockSignals(False)
        keys = (
            lambda entry: entry.path.name.casefold(),
            lambda entry: (entry.period or (date.min, date.min), entry.path.name.casefold()),
            lambda entry: -1 if entry.count is None else entry.count,
            lambda entry: entry.pdf is not None,
        )
        self.visible_rows.sort(key=keys[self.sort_column], reverse=self.reverse_sort)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.visible_rows))
            self.table.clearSelection()
            for row, entry in enumerate(self.visible_rows):
                count = f"{entry.count} db" if entry.count is not None else "—"
                for column, text in enumerate((entry.path.name, period_label(entry.period), count, "")):
                    item = QTableWidgetItem(text)
                    if column == 0:
                        item.setIcon(self.appearance.icon("docx"))
                        item.setToolTip(text)
                    else:
                        item.setTextAlignment(Qt.AlignCenter)
                    if column == 3:
                        item.setIcon(self.appearance.icon("pdf-present" if entry.pdf else "pdf-missing"))
                        item.setToolTip("Van kapcsolódó PDF" if entry.pdf else "Nincs kapcsolódó PDF")
                    self.table.setItem(row, column, item)
                if entry.path == current:
                    self.table.selectRow(row)
                    self.table.scrollToItem(self.table.item(row, 0))
        finally:
            self.table.blockSignals(False)
        self.count.setText(f"{year}  |  {len(self.visible_rows)} kísérőlevél")
        self.select()
        if failure:
            self.statusBar().showMessage(failure)
        elif not self.archive.is_dir():
            self.statusBar().showMessage("A dokumentumtár a Beállítások ablakban adható meg.")

    def select(self):
        selected = self.table.selectionModel().selectedRows()
        self.current = self.visible_rows[selected[0].row()] if selected else None
        try:
            self.metadata = read_record(self.current.path) if self.current else None
        except OSError:
            self.metadata = None
        self.actions["edit"].setEnabled(self.metadata is not None)
        self.actions["open"].setEnabled(self.current is not None)
        self.actions["print"].setEnabled(self.current is not None)
        if not self.current:
            values = ("—",) * len(self.details)
            status = "Válasszon egy kísérőlevelet a listából."
        else:
            record = self.metadata.record if self.metadata else None
            values = (
                record.reference if record else "Nem érhető el",
                record.clerk if record else "Nem érhető el",
                record.signer if record else "Nem érhető el",
                record.position if record else "Nem érhető el",
                f"{record.dated:%Y.%m.%d.}" if record else "Nem érhető el",
                f"{record.sent:%Y.%m.%d.}" if record else "Nem érhető el",
                f"{self.current.count} db" if self.current.count is not None else "Nem érhető el",
                period_label(self.current.period),
            )
            status = ("Kapcsolódó PDF található. A naprakészség nincs ellenőrizve."
                      if self.current.pdf else "Nincs kapcsolódó PDF.")
            if not record:
                status += " A levél megtekinthető vagy Wordben szerkeszthető."
        for label, value in zip(self.details.values(), values, strict=True):
            label.setText(value)
        self.preview.select(self.current.path if self.current else None)
        self.statusBar().showMessage(status)

    def open_editor(self, checked=False, *, use_selection=False):
        if self.dialog and self.dialog.isVisible():
            self.dialog.raise_()
            return self.dialog
        previous = self.current.path if use_selection and self.current else None
        snapshot = self.metadata if use_selection else None
        if use_selection and (not previous or not snapshot or self.appearance.message(
            QMessageBox.Question, self, "Szerkesztés megerősítése",
            "Biztosan szeretné szerkeszteni a kijelölt kísérőlevelet?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes):
            return None
        archive, template = self.archive, self.settings.template_path(self.base)

        def save(record):
            if archive == Settings().archive_path(self.base):
                archive.mkdir(exist_ok=True)
            return save_record(archive, template, record, previous=previous, expected=snapshot)

        dialog = LetterDialog(self.appearance, self.settings, save, self, snapshot.record if snapshot else None)
        self.dialog = dialog

        def finished(result):
            self.dialog = None
            if result == QDialog.Accepted and dialog.saved_path:
                self.search.clear()
                self.reload(preferred=dialog.saved_path)
            dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.open()
        return dialog

    def open_in_word(self, checked=False, *, printing=False):
        if self.current:
            try:
                if not printing or self.appearance.message(
                    QMessageBox.Question, self, "Nyomtatás", "Kinyomtatja a kijelölt kísérőlevelet?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                ) == QMessageBox.Yes:
                    word_action(self.current.path, printing=printing)
            except OSError as error:
                self.appearance.message(QMessageBox.Critical, self, "Word-művelet", str(error))

    def configure(self):
        dialog = SettingsDialog(self.settings, self.base, self.appearance, self)
        accepted = dialog.exec_() == QDialog.Accepted
        if accepted:
            previous_archive = self.archive
            self.settings = dialog.settings
            self.settings_writable = True
            self.appearance.apply(self.settings.ui_style, self.settings.icon_theme)
            if dialog.reset_requested:
                self.sash_moved = False
                self.preview.viewer.set_zoom(self.settings.zoom)
                for column, width in enumerate(self.settings.columns):
                    self.table.setColumnWidth(column, width)
                self.showMaximized()
                QTimer.singleShot(0, self.restore_panels)
            if self.archive != previous_archive:
                self.reload()
        dialog.deleteLater()

    def closeEvent(self, event):
        self.search_timer.stop()
        self.preview.stop()
        self.settings.window_state = "zoomed" if self.isMaximized() else "normal"
        if not self.isMaximized():
            geometry = self.geometry()
            self.settings.geometry = (f"{geometry.width()}x{geometry.height()}"
                                      f"{geometry.x():+d}{geometry.y():+d}")
        if self.sash_moved:
            self.settings.main_sash = self.splitter.sizes()[0]
        self.settings.list_sash = self.left.sizes()[0]
        self.settings.columns = tuple(self.table.columnWidth(column) for column in range(self.table.columnCount()))
        self.settings.zoom = self.preview.viewer.zoom.currentText()
        self.settings.last_year = self.year.currentText()
        try:
            if self.settings_writable:
                self.settings.save(self.base)
        except OSError as error:
            self.appearance.message(QMessageBox.Critical, self, "Beállítások", f"A beállítások nem menthetők: {error}")
        super().closeEvent(event)
