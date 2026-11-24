from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

try:
    import pypdfium2
except ImportError:
    pypdfium2 = None

from postaszamla.archive import archive_lock, sidecar
from postaszamla.document_actions import DeletionPlan, delete_document, generate_pdf


class DocumentActionsTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.folder = self.root / "2026"
        self.folder.mkdir()
        self.docx = self.folder / "Minta levél.docx"
        self.docx.write_bytes(b"fiktiv docx")
        self.data = sidecar(self.docx)
        self.data.write_bytes(b'{"fiktiv": true}')
        self.pdf = self.docx.with_suffix(".pdf")
        self.settings = self.root / "beallitasok.json"
        self.settings.write_bytes(b"{}")

    @skipUnless(pypdfium2, "A PDF ellenőrzéséhez a desktop csomag szükséges.")
    def test_verified_pdf_is_saved_and_source_untouched(self):
        with patch("postaszamla.document_actions.word_pdf", return_value=pdf_fixture()) as word:
            self.assertEqual(generate_pdf(self.root, self.docx), self.pdf)
        word.assert_called_once_with(self.docx)
        with pypdfium2.PdfDocument(self.pdf) as document:
            self.assertEqual(len(document), 1)
        self.assertEqual(self.docx.read_bytes(), b"fiktiv docx")
        self.assertFalse(list(self.folder.glob(".postaszamla-pdf-*")))

    @skipUnless(pypdfium2, "A PDF ellenőrzéséhez a desktop csomag szükséges.")
    def test_corrupt_and_failed_conversion_leave_no_pdf(self):
        for effect in (None, RuntimeError("fiktív COM-hiba")):
            with self.subTest(effect=effect):
                with patch("postaszamla.document_actions.word_pdf", return_value=b"nem PDF", side_effect=effect):
                    with self.assertRaises((OSError, ValueError)):
                        generate_pdf(self.root, self.docx)
                self.assertFalse(self.pdf.exists())
                self.assertFalse(list(self.folder.glob(".postaszamla-pdf-*")))

    @skipUnless(pypdfium2, "A PDF ellenőrzéséhez a desktop csomag szükséges.")
    def test_existing_and_concurrently_created_pdfs_are_preserved(self):
        uppercase = self.pdf.with_suffix(".PDF")
        uppercase.write_bytes(b"meglevo")
        with patch("postaszamla.document_actions.word_pdf") as word:
            with self.assertRaises(FileExistsError):
                generate_pdf(self.root, self.docx)
        word.assert_not_called()
        self.assertEqual(uppercase.read_bytes(), b"meglevo")
        uppercase.unlink()

        def convert(_):
            self.pdf.write_bytes(b"masik folyamat")
            return pdf_fixture()

        with patch("postaszamla.document_actions.word_pdf", side_effect=convert):
            with self.assertRaises(FileExistsError):
                generate_pdf(self.root, self.docx)
        self.assertEqual(self.pdf.read_bytes(), b"masik folyamat")
        self.assertFalse(list(self.folder.glob(".postaszamla-pdf-*")))

    def test_delete_moves_data_and_leaves_pdf_by_default(self):
        self.pdf.write_bytes(b"fiktiv pdf")
        unrelated = self.folder / "Másik.docx"
        unrelated.write_bytes(b"masik")
        plan = DeletionPlan.read(self.root, self.docx)
        with patch("postaszamla.document_actions.move_to_windows_trash", return_value=False):
            saved = delete_document(plan)
        self.assertFalse(self.docx.exists())
        self.assertFalse(self.data.exists())
        self.assertEqual(self.pdf.read_bytes(), b"fiktiv pdf")
        self.assertEqual(self.settings.read_bytes(), b"{}")
        self.assertEqual(unrelated.read_bytes(), b"masik")
        self.assertEqual({path.name for path in saved.iterdir()}, {self.docx.name, self.data.name})

    def test_optional_pdf_and_partial_recycle_failure(self):
        self.pdf.write_bytes(b"fiktiv pdf")
        plan = DeletionPlan.read(self.root, self.docx)

        def recycle(path):
            if path.suffix == ".docx":
                path.unlink()
                return True
            raise OSError("fiktív lomtárhiba")

        with patch("postaszamla.document_actions.move_to_windows_trash", side_effect=recycle):
            with self.assertRaisesRegex(OSError, "részben"):
                delete_document(plan, include_pdf=True)
        self.assertFalse(any(path.exists() for path in (self.docx, self.data, self.pdf)))
        trash = next((self.root / ".postaszamla-trash").iterdir())
        self.assertEqual({path.name for path in trash.iterdir()}, {self.data.name, self.pdf.name})

    def test_stale_plan_and_archive_lock_abort_before_removal(self):
        plan = DeletionPlan.read(self.root, self.docx)
        with archive_lock(self.root), self.assertRaises(ValueError):
            delete_document(plan)
        self.data.write_bytes(b"friss adat")
        with self.assertRaisesRegex(ValueError, "megváltozott"):
            delete_document(plan)
        self.assertTrue(self.docx.exists())
        self.assertEqual(self.data.read_bytes(), b"friss adat")

    def test_staging_failure_restores_the_already_moved_docx(self):
        plan = DeletionPlan.read(self.root, self.docx)
        rename = Path.rename

        def move(path, target):
            if path == self.data:
                raise PermissionError("fiktív hozzáférési hiba")
            return rename(path, target)

        with patch.object(Path, "rename", move), self.assertRaisesRegex(OSError, "visszakerültek"):
            delete_document(plan)
        self.assertEqual(self.docx.read_bytes(), b"fiktiv docx")
        self.assertTrue(self.data.exists())


def pdf_fixture():
    target = BytesIO()
    with pypdfium2.PdfDocument.new() as document:
        document.new_page(100, 100).close()
        document.save(target)
    return target.getvalue()
