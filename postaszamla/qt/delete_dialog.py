from secrets import randbelow

from PySide2.QtCore import Qt
from PySide2.QtGui import QIntValidator
from PySide2.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from .icon_widgets import IconLineEdit


class DeleteDialog(QDialog):
    def __init__(self, appearance, plan, available, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kísérőlevél törlése")
        self.setModal(True)
        self.plan = plan
        self.available = available
        layout = QVBoxLayout(self)
        title = QLabel(plan.document.path.name)
        title.setTextFormat(Qt.PlainText)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setWordWrap(True)
        layout.addWidget(title)
        warning = QLabel("A törlés adatvesztést okozhat. Ellenőrizze a felsorolt fájlokat.")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.files_label = QLabel()
        self.files_label.setTextFormat(Qt.PlainText)
        self.files_label.setWordWrap(True)
        layout.addWidget(self.files_label)
        self.include_pdf = QCheckBox("A kapcsolódó PDF törlése is")
        if plan.pdf:
            layout.addWidget(self.include_pdf)
        else:
            self.include_pdf.hide()
        left, right = randbelow(8) + 2, randbelow(8) + 2
        self.result_text = str(left + right)
        question = QLabel(f"{left} + {right} = ?")
        self.answer = IconLineEdit(appearance.icons)
        self.answer.setValidator(QIntValidator(0, 18, self))
        self.answer.setMaxLength(2)
        question.setBuddy(self.answer)
        layout.addWidget(question)
        layout.addWidget(self.answer)
        buttons = QDialogButtonBox()
        self.execute = appearance.icons.bind(
            buttons.addButton("Törlés végrehajtása", QDialogButtonBox.DestructiveRole), "delete")
        cancel = appearance.icons.bind(buttons.addButton("Mégse", QDialogButtonBox.RejectRole), "cancel")
        cancel.setDefault(True)
        self.execute.clicked.connect(self.confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.answer.textChanged.connect(self.update_confirmation)
        self.include_pdf.toggled.connect(self.update_confirmation)
        self.update_confirmation()
        self.answer.setFocus()

    def update_confirmation(self, *_):
        self.files_label.setText("Törlendő fájlok\n" + "\n".join(
            item.path.name for item in self.plan.files(self.include_pdf.isChecked())))
        self.execute.setEnabled(self.answer.text() == self.result_text and self.available())

    def confirm(self):
        self.update_confirmation()
        if self.execute.isEnabled():
            self.accept()
