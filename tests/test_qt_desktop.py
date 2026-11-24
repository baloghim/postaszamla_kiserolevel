import json
import os
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

try:
    from PySide2.QtCore import QDate, QTimer, Qt, qVersion
    from PySide2.QtGui import QColor, QPainter, QPalette, QPdfWriter
    from PySide2.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QStyleFactory
except ImportError:
    QApplication = None

from postaszamla.archive import read_record, save_record
from postaszamla.settings import DEFAULT_ICON_THEME, DEFAULT_UI_STYLE, Settings, load_settings
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
        from postaszamla.qt.appearance import SURFACES, THEME

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
        with patch.object(self.window.appearance, "message", return_value=QMessageBox.Yes):
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
        with patch.object(self.window.appearance, "message", return_value=QMessageBox.No):
            self.assertIsNone(self.window.open_editor(use_selection=True))
        with patch.object(self.window.appearance, "message", return_value=QMessageBox.Yes):
            editor = self.window.open_editor(use_selection=True)
            editor.common["reference"].setText("MINTA/5")
            editor.submit()
        self.assertEqual(read_record(path).record.reference, "MINTA/5")
        backup = next(self.window.archive.glob(".postaszamla-backups/*/2026/" + path.name))
        self.assertEqual(read_record(backup), before)
        self.assertEqual(path.with_suffix(".pdf").read_bytes(), b"fiktiv")

    def test_settings_dialog_and_pdf_view(self):
        from postaszamla.qt.settings_dialog import SettingsDialog

        settings = SettingsDialog(self.window.settings, self.base, self.window.appearance)
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

        self.window.appearance.apply("windows")
        self.app.processEvents()
        self.assertEqual(viewer.page_label.text(), "2 / 2")
        page = viewer.label.pixmap().toImage()
        self.assertEqual(page.pixelColor(page.width() // 2, page.height() // 2), QColor(Qt.blue))

    def test_live_style_selection_keeps_archive_and_settings(self):
        from postaszamla.qt.appearance import SURFACES, THEME
        from postaszamla.qt.settings_dialog import SettingsDialog

        keys = {key.casefold() for key in QStyleFactory.keys() if QStyleFactory.create(key) is not None}
        styles = ["fusion", "windows"]
        if "windowsvista" in keys:
            styles.append("windowsvista")
        before = load_settings(self.base)
        self.assertFalse(self.window.archive.exists())
        luna_palette = self.app.palette()
        luna_stylesheet = self.app.styleSheet()
        editor = self.window.open_editor()
        confirmation = QMessageBox(self.window)

        from postaszamla.qt.edpd_graphics.themes.styles import stylesheet

        for style in (*styles, *SURFACES, *reversed(styles), DEFAULT_UI_STYLE):
            with self.subTest(style=style):
                def choose(dialog):
                    self.assertEqual([dialog.style_choice.itemData(i) for i in range(dialog.style_choice.count())],
                                     [*SURFACES, *styles])
                    dialog.style_choice.setCurrentIndex(dialog.style_choice.findData(style))
                    dialog.findChild(QDialogButtonBox).accepted.emit()
                    return dialog.result()

                with patch.object(SettingsDialog, "exec_", choose), patch.object(self.window, "reload") as reload:
                    self.window.configure()
                    self.app.processEvents()
                    reload.assert_not_called()
                self.assertFalse(self.window.archive.exists())
                before.ui_style = style
                self.assertEqual(load_settings(self.base), before)
                self.assertEqual(self.window.appearance.current_style, style)
                for widget in (self.window, self.window.table, self.window.preview.viewer, editor, confirmation):
                    self.assertEqual(widget.style().objectName(), self.app.style().objectName())
                opened = SettingsDialog(self.window.settings, self.base, self.window.appearance)
                self.assertEqual(opened.style().objectName(), self.app.style().objectName())
                self.assertEqual(opened.style_choice.currentData(), style)
                if style in SURFACES:
                    self.assertEqual(self.app.property("surfaceTheme"), SURFACES[style])
                    self.assertEqual(self.app.styleSheet(), stylesheet(SURFACES[style]))
                    if style == DEFAULT_UI_STYLE:
                        self.assertEqual(self.app.styleSheet(), luna_stylesheet)
                        self.assertEqual(self.app.palette(), luna_palette)
                else:
                    self.assertEqual(self.app.style().objectName().casefold(), style)
                    self.assertEqual(self.app.styleSheet(), "")
                    active_palette = self.app.palette()
                    self.app.setPalette(self.app.style().standardPalette())
                    self.assertEqual(active_palette, self.app.palette())

    def test_style_cancel_saved_startup_and_missing_json(self):
        from postaszamla.qt.appearance import Appearance, THEME
        from postaszamla.qt.settings_dialog import SettingsDialog
        from postaszamla.qt.window import MainWindow

        config = self.base / "beallitasok.json"
        before = config.read_bytes()

        def cancel(dialog):
            dialog.style_choice.setCurrentIndex(dialog.style_choice.findData("windows"))
            dialog.icon_choice.setCurrentText("Oxygen")
            dialog.findChild(QDialogButtonBox).rejected.emit()
            return dialog.result()

        with patch.object(SettingsDialog, "exec_", cancel):
            self.window.configure()
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(self.window.appearance.current_style, DEFAULT_UI_STYLE)
        self.assertEqual(self.window.appearance.icons.name, DEFAULT_ICON_THEME)

        self.window.settings.ui_style = "windows"
        self.window.settings.icon_theme = "Oxygen"
        self.window.close()
        self.window = MainWindow(Appearance(self.app), self.base)
        self.assertEqual(self.window.appearance.current_style, "windows")
        self.assertEqual(self.window.appearance.icons.name, "Oxygen")
        self.assertEqual(self.app.style().objectName().casefold(), "windows")
        self.window.close()
        config.unlink()
        self.window = MainWindow(Appearance(self.app), self.base)
        self.assertEqual(self.app.property("surfaceTheme"), THEME)
        self.assertEqual(load_settings(self.base).ui_style, DEFAULT_UI_STYLE)
        self.assertEqual(load_settings(self.base).icon_theme, DEFAULT_ICON_THEME)

        legacy = json.loads(before)
        del legacy["ui_style"]
        del legacy["icon_theme"]
        config.write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(load_settings(self.base).ui_style, DEFAULT_UI_STYLE)
        self.assertEqual(load_settings(self.base).icon_theme, DEFAULT_ICON_THEME)

    def test_edpd_sources_and_all_icon_themes(self):
        from postaszamla.qt.edpd_graphics.icons import ASSETS

        icons = self.window.appearance.icons
        names = ("Crystal SVG", "Nuvola", "KDE Modern Classic", "Papirus", "We10X", "Oxygen", "Win10Sur",
                 "Oxylite", "WhiteSur", "Diagonal", "Modern Office Day", "SE98")
        self.assertEqual(icons.choices(), names)
        crystal = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
        for role in crystal["icons"]:
            self.assertTrue((ASSETS / "icons" / "22" / f"{role}.png").is_file())
            self.assertTrue((ASSETS / "original" / "22" / f"{role}.png").is_file())
        for name, theme in icons.themes.items():
            with self.subTest(theme=name):
                notice = "crystal-remix" if name == DEFAULT_ICON_THEME else theme["id"]
                self.assertTrue(any((ASSETS / "notices" / notice).iterdir()))
                self.assertTrue(theme["license"] and theme["source"])
                self.assertEqual(icons.set_theme(name), name)
                for role, metadata in theme["icons"].items():
                    for source in (metadata, metadata.get("badge"), metadata.get("editable_source")):
                        if source:
                            original = ASSETS / "themes" / theme["id"] / "original" / source["original"]
                            self.assertEqual(sha256(original.read_bytes()).hexdigest(), source["sha256"])
                    for size in (22, 40):
                        self.assertTrue((ASSETS / "themes" / theme["id"] / str(size) / f"{role}.png").is_file())
                    self.assertFalse(icons.icon(role).pixmap(22, 22).isNull())
                    self.assertEqual(icons.sources[role], name)
                for role in theme["fallback_roles"]:
                    self.assertFalse(icons.icon(role).pixmap(22, 22).isNull())
                    self.assertEqual(icons.sources[role], DEFAULT_ICON_THEME)
                self.assertFalse(icons.icon("open").isNull())
                self.assertEqual(icons.sources["open"], "Qt standard")
                self.assertFalse(icons.icon("pdf-present").isNull())
        self.assertEqual(icons.set_theme("nem létező téma"), DEFAULT_ICON_THEME)

    def test_icons_update_without_refreshing_documents(self):
        from postaszamla.qt.settings_dialog import SettingsDialog

        window = self.window
        window.archive.mkdir()
        path = save_record(window.archive, DEFAULT_TEMPLATE, LETTER)
        path.with_suffix(".pdf").write_bytes(b"fiktiv")
        window.reload(preferred=path)
        initial_token = window.preview.token
        editor = window.open_editor()
        active_settings = SettingsDialog(window.settings, self.base, window.appearance)
        save = next(button for button in active_settings.findChild(QDialogButtonBox).buttons() if button.text() == "Mentés")
        for widget, role in ((window.actions["refresh"], "refresh"), (window.preview.viewer.navigation[0], "first"),
                             (editor.remove_button, "invoice-delete"), (save, "save")):
            self.assertEqual(widget.icon().cacheKey(), window.appearance.icon(role).cacheKey())
        original_preview = window.table.item(0, 3).icon().cacheKey()

        def choose(dialog):
            dialog.style_choice.setCurrentIndex(dialog.style_choice.findData("longhorn-blue"))
            dialog.icon_choice.setCurrentText("Papirus")
            dialog.save()
            return dialog.result()

        with patch.object(SettingsDialog, "exec_", choose), patch.object(window, "reload") as reload:
            window.configure()
            reload.assert_not_called()
        self.assertIs(initial_token, window.preview.token)
        self.assertIs(editor, window.dialog)
        self.assertEqual(window.current.path, path)
        self.assertEqual(load_settings(self.base).icon_theme, "Papirus")
        self.assertEqual(self.app.property("surfaceTheme"), "Longhorn Blue")
        for widget, role in ((window.actions["refresh"], "refresh"), (window.preview.viewer.navigation[0], "first"),
                             (editor.remove_button, "invoice-delete"), (save, "save")):
            self.assertEqual(widget.icon().cacheKey(), window.appearance.icon(role).cacheKey())
        self.assertNotEqual(original_preview, window.table.item(0, 3).icon().cacheKey())

        def confirm():
            box = self.app.activeModalWidget()
            box.done(QMessageBox.Yes)

        QTimer.singleShot(0, confirm)
        self.assertEqual(window.appearance.message(QMessageBox.Question, window, "Minta", "Folytatja?",
                                                   QMessageBox.Yes | QMessageBox.No), QMessageBox.Yes)
