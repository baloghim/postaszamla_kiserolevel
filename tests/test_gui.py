from dataclasses import replace
from datetime import timedelta
from io import BytesIO
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from postaszamla.archive import read_record, save_record, sidecar
from postaszamla.editor import LetterEditor
from postaszamla.gui import Application
from postaszamla.settings import load_settings
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

    def test_initial_split_and_saved_drag(self):
        app = self.app
        panes = app.main_panes
        self.assertLessEqual(abs(app.left_panes.winfo_width() - app.preview.winfo_width()), 1)
        original = panes.sashpos(0)
        panes.event_generate("<ButtonPress-1>", x=original + 1, y=50)
        panes.sashpos(0, original + 70)
        panes.event_generate("<ButtonRelease-1>", x=original + 71, y=50)
        app.settings.save(self.base)
        stored = load_settings(self.base)
        self.assertEqual(stored.main_sash, original + 70)
        panes.sashpos(0, original - 30)
        app.restore_sashes()
        self.assertEqual(panes.sashpos(0), stored.main_sash)

    def test_toolbar_order_groups_and_bundled_icons(self):
        self.assertEqual(ttk.Style(self.root).theme_use(), "fusion-light")
        buttons = self.app.toolbar_buttons
        self.assertEqual([button.cget("text") for button in buttons], [
            "Új kísérőlevél", "Szerkesztés", "Megnyitás Wordben", "Nyomtatás",
            "Frissítés", "Beállítások", "Névjegy", "Súgó",
        ])
        for button in buttons:
            self.assertTrue(button.cget("image"))
            self.assertEqual(str(button.cget("compound")), "left")
        self.assertEqual(len({button.winfo_reqheight() for button in buttons}), 1)
        self.assertTrue(all(button.master == buttons[0].master for button in buttons[:5]))
        self.assertTrue(all(button.master == buttons[5].master for button in buttons[5:]))
        self.assertGreater(buttons[5].winfo_rootx(), buttons[0].winfo_rootx())

    def test_pdf_indicators_and_selection(self):
        self.app.archive.mkdir()
        with_pdf = save_record(self.app.archive, DEFAULT_TEMPLATE, LETTER)
        invoice = LETTER.invoices[0]
        next_invoice = replace(invoice, end=invoice.end + timedelta(days=1))
        save_record(self.app.archive, DEFAULT_TEMPLATE, replace(LETTER, invoices=(next_invoice,)))
        with_pdf.with_suffix(".pdf").touch()
        self.app.year.set(with_pdf.parent.name)
        self.app.refresh()
        self.root.update()
        self.app.tree.xview_moveto(1.0)
        self.root.update()
        badges = [label for label in self.app.pdf_badges.labels if label.winfo_ismapped()]
        self.assertEqual(len(badges), 2)
        for label in badges:
            expected = self.app.pdf_badges.icons[self.app.tree.set(label.item, "pdf")]
            self.assertEqual(label.cget("image"), str(expected))
        self.app.pdf_badges.select(badges[-1].item)
        self.root.update()
        self.assertEqual(self.app.current.path, with_pdf)
        self.assertEqual(self.app.info["reference"].get(), LETTER.reference)

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
            import pypdfium2
        except ImportError:
            self.skipTest("A PDFium asztali kiegészítő nincs telepítve.")
        contents = BytesIO()
        with pypdfium2.PdfDocument.new() as document:
            document.new_page(595, 1600).close()
            document.new_page(842, 595).close()
            document.save(contents)
        self.app.preview.data = contents.getvalue()
        self.app.preview.draw_page()
        self.assertEqual(self.app.preview.page_text.get(), "1 / 2")
        self.app.preview.turn(1)
        self.assertEqual(self.app.preview.page_text.get(), "2 / 2")
        self.app.preview.zoom.set("50%")
        self.app.preview.draw_page()
        self.assertIsNotNone(self.app.preview.image)
        preview = self.app.preview
        preview.zoom.set("200%")
        preview.draw_page()
        self.root.update()
        self.assertTrue(preview.xscroll.winfo_ismapped())
        self.assertLess(preview.canvas.xview()[1], 1.0)
        preview.zoom.set("Szélesség")
        preview.draw_page()
        self.root.update()
        self.assertFalse(preview.xscroll.winfo_ismapped())
        self.assertEqual(preview.canvas.xview(), (0.0, 1.0))

        original = preview.image.width()
        panes = self.app.main_panes
        panes.sashpos(0, panes.sashpos(0) + 100)
        deadline = time.monotonic() + 3
        while preview.image.width() == original and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.025)
        self.assertLess(preview.image.width(), original)
        self.assertFalse(preview.xscroll.winfo_ismapped())
        preview.turn(-1)
        self.root.update()
        self.assertEqual(preview.page_text.get(), "1 / 2")
        self.assertLess(preview.canvas.yview()[1], 1.0)
        self.assertFalse(preview.xscroll.winfo_ismapped())
