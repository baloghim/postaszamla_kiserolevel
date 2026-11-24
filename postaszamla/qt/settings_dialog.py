from dataclasses import replace

from PySide2.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from postaszamla.settings import DEFAULT_UI_STYLE, Settings

from .appearance import style_choices


class SettingsDialog(QDialog):
    def __init__(self, settings, base, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Beállítások")
        self.resize(690, 280)
        self.settings = settings
        self.base = base
        self.reset_requested = False
        layout = QVBoxLayout(self)
        form = QGridLayout()
        layout.addLayout(form)
        self.fields = {}
        for row, (key, label) in enumerate((
            ("archive", "Dokumentumtár"), ("template", "Word-sablon"),
            ("clerk", "Ügyintéző"), ("signer", "Aláíró"), ("position", "Aláíró beosztása"),
        )):
            form.addWidget(QLabel(label), row, 0)
            field = QLineEdit(getattr(settings, key))
            self.fields[key] = field
            form.addWidget(field, row, 1)
            if key in ("archive", "template"):
                button = QPushButton("Tallózás…")
                button.clicked.connect(lambda checked=False, name=key: self.browse(name))
                form.addWidget(button, row, 2)
        hint = QLabel("Az üres Word-sablon mező a mellékelt fiktív sablont használja.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        appearance = QGroupBox("Megjelenés")
        appearance_form = QFormLayout(appearance)
        self.style_choice = QComboBox()
        for key, label in style_choices():
            self.style_choice.addItem(label, key)
        index = self.style_choice.findData(settings.ui_style)
        self.style_choice.setCurrentIndex(max(0, index))
        appearance_form.addRow("Felületi stílus", self.style_choice)
        layout.addWidget(appearance)
        buttons = QDialogButtonBox()
        buttons.addButton("Mentés", QDialogButtonBox.AcceptRole)
        buttons.addButton("Mégse", QDialogButtonBox.RejectRole)
        reset = buttons.addButton("Alaphelyzet", QDialogButtonBox.ResetRole)
        reset.clicked.connect(self.reset)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self, key):
        initial = str(self.settings.resolve(self.base, self.fields[key].text().strip()))
        if key == "archive":
            path = QFileDialog.getExistingDirectory(self, "Dokumentumtár kiválasztása", initial)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Sablon kiválasztása", initial, "Word-sablon (*.docx)")
        if path:
            self.fields[key].setText(path)

    def reset(self):
        if QMessageBox.question(self, "Alaphelyzet", "Visszaállítja a beállítások alapértékeit?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.reset_requested = True
        defaults = Settings()
        for name, field in self.fields.items():
            field.setText(getattr(defaults, name))
        self.style_choice.setCurrentIndex(self.style_choice.findData(DEFAULT_UI_STYLE))

    def save(self):
        values = {key: field.text().strip() for key, field in self.fields.items()
                  if self.reset_requested or field.text() != getattr(self.settings, key)}
        values["ui_style"] = self.style_choice.currentData()
        updated = replace(Settings() if self.reset_requested else self.settings, **values)
        try:
            if self.reset_requested or values.keys() & {"archive", "template"}:
                self.validate_paths(updated)
            updated.save(self.base)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Beállítások", str(error))
            return
        self.settings = updated
        self.accept()

    def validate_paths(self, settings):
        if not settings.archive:
            raise ValueError("Adja meg a dokumentumtár gyökérmappáját.")
        archive = settings.archive_path(self.base)
        if archive == Settings().archive_path(self.base):
            archive.mkdir(exist_ok=True)
        if not archive.is_dir():
            raise ValueError("A dokumentumtár nem érhető el.")
        next(archive.iterdir(), None)
        template = settings.template_path(self.base)
        if template.suffix.casefold() != ".docx" or not template.is_file():
            raise ValueError("A megadott DOCX-sablon nem érhető el.")
        with template.open("rb"):
            pass
