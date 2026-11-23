import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

try:
    from PySide2.QtCore import QDate, Qt, qVersion
    from PySide2.QtGui import QColor, QPainter, QPalette, QPdfWriter
    from PySide2.QtWidgets import QApplication, QMessageBox
except ImportError:
    QApplication = None

from postaszamla.archive import read_record, save_record
from postaszamla.settings import Settings, load_settings
from postaszamla.template import DEFAULT_TEMPLATE

from test_desktop import INVOICE, LETTER, SECOND


@skipUnless(QApplication and (sys.platform != "linux" or os.environ.get("DISPLAY")
                            or os.environ.get("QT_QPA_PLATFORM")),
            "A Qt tesztekhez a desktop függőségek és grafikus kijelző szükséges.")
class QtDesktopTests(TestCase):
    @classmethod
    def setUpClass(cls):
        from postaszamla.qt.app import create_application

        cls.app = QApplication.instance() or create_application()

    def setUp(self):
        from postaszamla.qt.appearance import Appearance
        from postaszamla.qt.window import MainWindow

        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        Settings(clerk=LETTER.clerk, signer=LETTER.signer, position=LETTER.position,
                 archive="dokumentumok", zoom="Teljes oldal", window_state="normal").save(self.base)
        self.window = MainWindow(Appearance(self.app), self.base)
        self.window.show()
        self.app.processEvents()
        self.window.restore_panels()

    def tearDown(self):
        if self.window.dialog:
            self.window.dialog.reject()
        self.window.close()
        self.app.processEvents()

    def set_invoice(self, dialog, invoice):
        dialog.number.setText(invoice.number)
        for field, day in ((dialog.start, invoice.start), (dialog.end, invoice.end)):
            field.setDate(QDate(day.year, day.month, day.day))
        for values, cost in zip(dialog.editors, invoice.costs.rows(), strict=True):
            values[0].setText(str(cost.operating))
            values[1].setText(str(cost.benefits))

    def test_default_qt_entrypoint_and_luna(self):
        from postaszamla import gui
        from postaszamla.qt.app import main
        from postaszamla.qt.appearance import THEME

        self.assertIs(gui.main, main)
        from postaszamla.__main__ import main as launch
        with patch("sys.argv", ["postaszamla"]), patch("postaszamla.gui.main", return_value=0) as run:
            self.assertEqual(launch(), 0)
            run.assert_called_once()
        self.assertEqual(qVersion(), "5.15.2")
        self.assertEqual(self.app.property("surfaceTheme"), THEME)
        self.assertLessEqual(abs(self.window.splitter.sizes()[0] - self.window.splitter.sizes()[1]), 1)
        dialog = self.window.open_editor()
        self.assertEqual(dialog.palette().color(QPalette.Highlight),
                         self.window.palette().color(QPalette.Highlight))

    def test_new_letter_saves_docx_and_portable_json_with_two_invoices(self):
        dialog = self.window.open_editor()
        self.assertEqual(dialog.common["clerk"].text(), LETTER.clerk)
        dialog.common["reference"].setText(LETTER.reference)
        dialog.common["dated"].input.setText(LETTER.dated.isoformat())
        dialog.common["sent"].input.setText(f"{LETTER.sent:%Y.%m.%d.}")
        self.set_invoice(dialog, INVOICE)
        dialog.add_invoice()
        self.set_invoice(dialog, SECOND)
        self.assertEqual(dialog.summary.item(4, 3).text(), "1 200 Ft")
        expected_name = "postaszámla_2026.12.25-2027.01.05_ellátási_mukodesi_ki_be_szallitas.docx"
        self.assertIn(expected_name, dialog.file_preview.text())
        dialog.submit()
        expected = self.base / "dokumentumok" / "2026" / expected_name
        self.assertTrue(expected.is_file())
        self.assertEqual(read_record(expected).record.invoices, (INVOICE, SECOND))
        self.assertEqual(self.window.current.path, expected)
        self.assertEqual(self.window.details["Iktatószám"].text(), LETTER.reference)

    def test_invalid_costs_survive_tab_change_and_can_be_removed(self):
        dialog = self.window.open_editor()
        self.set_invoice(dialog, INVOICE)
        dialog.add_invoice()
        self.set_invoice(dialog, SECOND)
        dialog.editors[0][0].setText("-23")
        dialog.tabs.setCurrentIndex(0)
        self.assertIn("—", dialog.file_preview.text())
        dialog.tabs.setCurrentIndex(1)
        self.assertEqual(dialog.editors[0][0].text(), "-23")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            dialog.remove_invoice()
        self.assertEqual(dialog.summary.item(4, 3).text(), "700 Ft")
        self.assertEqual(dialog.number.text(), INVOICE.number)

    def test_edit_confirmation_backup_and_archived_pdf(self):
        self.window.archive.mkdir()
        path = save_record(self.window.archive, DEFAULT_TEMPLATE, LETTER)
        path.with_suffix(".pdf").write_bytes(b"fiktiv")
        self.window.reload(preferred=path)
        before = self.window.metadata
        self.assertTrue(self.window.current.pdf)
        self.assertTrue(self.window.actions["edit"].isEnabled())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            self.assertIsNone(self.window.open_editor(use_selection=True))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            editor = self.window.open_editor(use_selection=True)
            editor.common["reference"].setText("MINTA/5")
            editor.submit()
        self.assertEqual(read_record(path).record.reference, "MINTA/5")
        backup = next(self.window.archive.glob(".postaszamla-backups/*/2026/" + path.name))
        self.assertEqual(read_record(backup), before)
        self.assertEqual(path.with_suffix(".pdf").read_bytes(), b"fiktiv")

    def test_settings_dialog_and_pdf_view(self):
        from postaszamla.qt.settings_dialog import SettingsDialog

        settings = SettingsDialog(self.window.settings, self.base)
        (self.base / "levelek").mkdir()
        settings.fields["archive"].setText("levelek")
        settings.fields["position"].setText("új beosztás")
        settings.save()
        self.assertEqual(load_settings(self.base).archive, "levelek")
        self.assertEqual(load_settings(self.base).position, "új beosztás")

        source = self.base / "minta.pdf"
        writer = QPdfWriter(str(source))
        writer.setResolution(72)
        painter = QPainter(writer)
        try:
            painter.fillRect(painter.viewport(), Qt.red)
            self.assertTrue(writer.newPage())
            painter.fillRect(painter.viewport(), Qt.blue)
        finally:
            painter.end()
        del writer
        viewer = self.window.preview.viewer
        viewer.open_data(source.read_bytes())
        self.app.processEvents()
        first = viewer.label.pixmap().toImage()
        self.assertEqual(first.pixelColor(first.width() // 2, first.height() // 2), QColor(Qt.red))
        self.assertEqual(viewer.page_label.text(), "1 / 2")
        self.assertEqual(viewer.zoom.currentText(), "Teljes oldal")
        viewer.move(1)
        self.app.processEvents()
        self.assertEqual(viewer.page_label.text(), "2 / 2")
        second = viewer.label.pixmap().toImage()
        self.assertEqual(second.pixelColor(second.width() // 2, second.height() // 2), QColor(Qt.blue))
        self.assertFalse(viewer.scroll.horizontalScrollBar().isVisible())
