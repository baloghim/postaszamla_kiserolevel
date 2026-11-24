"""EDPD combo box arrow for decorated surfaces."""
from PySide2.QtCore import QPoint, Qt
from PySide2.QtGui import QPalette, QPolygon
from PySide2.QtWidgets import QComboBox, QStyle, QStyleOptionComboBox, QStylePainter

from . import manager


class SurfaceComboBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        if not manager().active:
            return
        # A styled drop-down panel suppresses the native arrow. Draw a small
        # high-contrast indicator without changing the standard model or popup.
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        area = self.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxArrow, self)
        painter = QStylePainter(self)
        group = QPalette.Active if self.isEnabled() else QPalette.Disabled
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.palette().color(group, QPalette.Text))
        x, y = area.center().x(), area.center().y()
        painter.drawPolygon(QPolygon([QPoint(x-4,y-2), QPoint(x+4,y-2), QPoint(x,y+3)]))
