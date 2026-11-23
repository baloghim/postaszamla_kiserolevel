import time
import tkinter as tk
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from postaszamla.archive import read_record, save_record, sidecar
from postaszamla.editor import LetterEditor
from postaszamla.gui import Application
from postaszamla.preview import text_preview
from postaszamla.template import DEFAULT_TEMPLATE

from test_desktop import LETTER


class TkTests(TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"A Tk grafikus kijelző nem érhető el: {error}")
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.addCleanup(self.cleanup_root)
        self.base = Path(directory.name)
        preview = patch("postaszamla.gui.prepare_preview", side_effect=lambda path: ("text", text_preview(path)))
        preview.start()
        self.addCleanup(preview.stop)
        self.app = Application(self.root, self.base)
        self.root.update()

    def cleanup_root(self):
        if self.root.winfo_exists():
            self.root.update_idletasks()
            self.root.destroy()

    def test_document_selection_readonly_and_rejected_edit(self):
        self.app.archive.mkdir()
        path = save_record(self.app.archive, DEFAULT_TEMPLATE, LETTER)
        self.app.year.set(path.parent.name)
        self.app.refresh(preferred=path)
        with patch("postaszamla.gui.confirm_dialog", return_value=False) as confirm, patch(
            "postaszamla.gui.LetterEditor"
        ) as editor:
            self.app.edit()
            confirm.assert_called_once()
            editor.assert_not_called()
        self.assertEqual(self.app.info["reference"].get(), LETTER.reference)
        deadline = time.monotonic() + 5
        while "Előnézet készítése" in self.app.preview.status.get() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.035)
        self.assertNotIn("Előnézet készítése", self.app.preview.status.get())
        self.assertEqual(str(self.app.preview.text.cget("state")), "disabled")
        sidecar(path).unlink()
        self.app.refresh(preferred=path)
        self.assertEqual(str(self.app.edit_button.cget("state")), "disabled")

    def test_editor_add_remove_live_summary_and_rejected_save(self):
        save = Mock()
        editor = LetterEditor(self.root, self.app.settings, save, LETTER)
        try:
            self.assertIn("2026.12.30.", editor.period_text.get())
            editor.add_invoice()
            values = editor.invoices[1]
            for var, value in zip(values[:5], ("0009", "2026.12.23.", "2027.01.10.", "133", "50")):
                var.set(value)
            self.assertIn("2026.12.23.", editor.period_text.get())
            self.assertIn("2026.12.23-2027.01.10_ellátási_mukodesi", editor.preview_name.get())
            self.assertEqual(editor.summary[-1][2].get(), "883 Ft")
            with patch("postaszamla.editor.confirm_dialog", return_value=True):
                editor.remove_invoice()
            self.assertEqual(len(editor.invoices), 1)
            self.assertIn("2026.12.30.", editor.period_text.get())
            with patch("postaszamla.editor.confirm_dialog", return_value=False) as confirm:
                editor.submit()
                confirm.assert_called_once()
            save.assert_not_called()
            self.assertTrue(editor.winfo_exists())
        finally:
            editor.destroy()

    def test_new_letter_form_saves_docx_and_record(self):
        self.app.archive.mkdir()
        editor = LetterEditor(
            self.root, self.app.settings,
            lambda record: save_record(self.app.archive, DEFAULT_TEMPLATE, record),
        )
        for key in ("reference", "clerk", "signer", "position"):
            editor.common[key].set(getattr(LETTER, key))
        editor.common["dated"].set(LETTER.dated.isoformat())
        editor.common["sent"].set(LETTER.sent.isoformat())
        for variable, value in zip(
            editor.invoices[0][:5], ("0001", "2026.12.30.", "2027.01.02.", "200", "500"), strict=True
        ):
            variable.set(value)
        editor.submit()
        self.assertFalse(editor.winfo_exists())
        self.assertEqual(read_record(editor.saved_path).record, LETTER)
        self.assertEqual(editor.saved_path.parent.name, "2026")

    def test_pdf_preview_pages_and_zoom(self):
        try:
            import pymupdf
        except ImportError:
            self.skipTest("A PyMuPDF asztali kiegészítő nincs telepítve.")
        with pymupdf.open() as document:
            document.new_page().insert_text((30, 30), "Minta 1")
            document.new_page().insert_text((30, 30), "Minta 2")
            self.app.preview.data = document.tobytes()
        self.app.preview.draw_page()
        self.assertEqual(self.app.preview.page_text.get(), "1 / 2")
        self.app.preview.turn(1)
        self.assertEqual(self.app.preview.page_text.get(), "2 / 2")
        self.app.preview.zoom.set("50%")
        self.app.preview.draw_page()
        self.assertIsNotNone(self.app.preview.image)
