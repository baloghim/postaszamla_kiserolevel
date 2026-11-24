"""Apply application icons to existing Qt editing actions."""
from PySide2.QtCore import QCoreApplication
from PySide2.QtWidgets import QAction, QLineEdit, QPlainTextEdit
from .edpd_graphics.icons import ICON_ROLE

LINE_ACTIONS = {
    "&Undo": "undo", "&Redo": "redo", "Cu&t": "cut", "&Copy": "copy",
    "&Paste": "paste", "Delete": "delete", "Select All": "select-all",
}
TEXT_ACTIONS = {
    "edit-undo": "undo", "edit-redo": "redo", "edit-cut": "cut", "edit-copy": "copy",
    "edit-paste": "paste", "edit-delete": "delete", "select-all": "select-all",
}


def bind_menu(icons, menu, roles, key):
    for action in menu.actions():
        if role := roles.get(key(action)):
            icons.bind(action, role)
    return menu


class IconLineEdit(QLineEdit):
    def __init__(self, icons, *args):
        super().__init__(*args)
        self.icons = icons

    def setClearButtonEnabled(self, enabled):
        super().setClearButtonEnabled(enabled)
        if enabled:
            action = self.findChild(QAction, "_q_qlineeditclearaction")
            if action and not action.property(ICON_ROLE):
                self.icons.bind(action, "clear-input")

    def createStandardContextMenu(self):
        labels = {QCoreApplication.translate("QLineEdit", label): role for label, role in LINE_ACTIONS.items()}
        return bind_menu(self.icons, super().createStandardContextMenu(), labels,
                         lambda action: action.text().partition("\t")[0])

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.exec_(event.globalPos())
        menu.deleteLater()


class IconPlainTextEdit(QPlainTextEdit):
    def __init__(self, icons, *args):
        super().__init__(*args)
        self.icons = icons

    def createStandardContextMenu(self, *args):
        return bind_menu(self.icons, super().createStandardContextMenu(*args), TEXT_ACTIONS, QAction.objectName)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu(event.pos())
        menu.exec_(event.globalPos())
        menu.deleteLater()
