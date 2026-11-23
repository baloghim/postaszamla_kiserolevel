import importlib
import os
import unittest
from pathlib import Path

from PySide2.QtCore import QDate, Qt, qVersion
from PySide2.QtGui import QPalette
from PySide2.QtWidgets import QApplication

from prototype.qt5.appearance import Appearance, THEME
from prototype.qt5.demo import DEMO, filename
from prototype.qt5.window import MainWindow


class PrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        cls.app = QApplication.instance() or QApplication([])
        source = os.getenv("POSTASZAMLA_EDPD_SOURCE")
        cls.appearance = Appearance(cls.app, Path(source) if source else None)

    def setUp(self):
        self.window = MainWindow(self.appearance)
        self.window.resize(1920, 1080)
        self.window.show()
        self.app.processEvents()
        self.window.splitter.setSizes((960, 960))
        self.window.table.selectRow(0)
        self.app.processEvents()

    def tearDown(self):
        self.window.preview.clear()
        if self.window.dialog:
            self.window.dialog.close()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_shared_luna_and_full_hd_split(self):
        self.assertEqual(qVersion(), "5.15.2")
        self.assertEqual(self.app.property("surfaceTheme"), THEME)
        self.assertEqual((self.window.width(), self.window.height()), (1920, 1080))
        left, right = self.window.splitter.sizes()
        self.assertLessEqual(abs(left - right), 1)
        dialog = self.window.open_editor()
        self.app.processEvents()
        self.assertTrue(dialog.isVisible())
        self.assertLess(dialog.width(), self.window.width())
        self.assertLess(dialog.height(), self.window.height())
        self.assertEqual(dialog.palette().color(QPalette.Highlight), self.window.palette().color(QPalette.Highlight))
        self.assertEqual(dialog.style().objectName(), self.window.style().objectName())
        if self.appearance.source:
            styles = importlib.import_module("edpd.ui.themes.styles")
            self.assertEqual(self.app.styleSheet(), styles.stylesheet(THEME))
            self.assertEqual(type(self.window.table).__module__, "edpd.ui.proportional_table")
            self.assertEqual(type(self.window.preview.viewer).__module__, "edpd.ui.pdf_viewer")
            self.assertFalse(self.window.preview.viewer.print_action.isVisible())
            self.assertFalse(self.window.preview.viewer.save_action.isVisible())

    def test_pdf_navigation_and_archive_filtering(self):
        viewer = self.window.preview.viewer
        self.assertIsNotNone(viewer.label.pixmap())
        self.assertIn("1 / 2", viewer.page_label.text())
        viewer.move(1)
        self.assertIn("2 / 2", viewer.page_label.text())
        for mode in ("page", "width"):
            viewer.fit(mode)
            self.app.processEvents()
            self.assertFalse(viewer.scroll.horizontalScrollBar().isVisible())
        self.window.search.setText("nincs ilyen fájl")
        self.assertEqual(self.window.table.rowCount(), 0)
        self.assertIsNone(self.window.current)
        self.assertIsNone(viewer.pdf)
        self.window.search.clear()
        self.window.year.setCurrentText("2025")
        self.assertEqual(self.window.table.rowCount(), 1)

    def test_invoice_inputs_summary_and_filename(self):
        dialog = self.window.open_editor()
        self.assertEqual(dialog.invoices[0], DEMO.invoices[0])
        self.assertEqual(dialog.summary.item(4, 3).text(), "87 090 Ft")
        self.assertIn(filename(DEMO), dialog.file_preview.text())
        dialog.tabs.setCurrentIndex(1)
        self.assertEqual(dialog.number.text(), DEMO.invoices[1].number)
        dialog.add_invoice()
        self.assertEqual(dialog.tabs.count(), 3)
        self.assertIn("kötelező", dialog.file_preview.text())
        dialog.number.setText("MINTA-103")
        dialog.start.setDate(QDate(2026, 11, 16))
        dialog.end.setDate(QDate(2026, 11, 17))
        dialog.editors[0][0].setValue(900)
        self.assertEqual(dialog.summary.item(4, 3).text(), "87 990 Ft")
        self.assertIn(filename(dialog.draft()), dialog.file_preview.text())
        dialog.tabs.setCurrentIndex(0)
        self.assertEqual(dialog.number.text(), DEMO.invoices[0].number)
