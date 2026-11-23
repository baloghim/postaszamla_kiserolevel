from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from postaszamla import archive
from postaszamla.archive import documents, initial_year, read_record, save_record, sidecar, year_folders
from postaszamla.filename import make_filename
from postaszamla.finance import calculate
from postaszamla.models import Cost, Costs
from postaszamla.preview import text_preview
from postaszamla.records import Invoice, Record
from postaszamla.settings import InvalidSettings, Settings, backup_settings, load_settings
from postaszamla.template import DEFAULT_TEMPLATE

ZERO = Cost(0, 0)
INVOICE = Invoice("0001", date(2026, 12, 30), date(2027, 1, 2),
                  Costs(Cost(200, 500), ZERO, ZERO, ZERO))
SECOND = Invoice("0002", date(2026, 12, 25), date(2027, 1, 5),
                 Costs(Cost(0, 100), Cost(400, 0), ZERO, ZERO))
LETTER = Record("MINTA/3", "Minta Anna", "Minta Klára", "vezető", date(2027, 1, 8),
                date(2027, 1, 6), (INVOICE,))


class SettingsTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_first_start_and_recreation(self):
        path = self.root / "beallitasok.json"
        self.assertEqual(load_settings(self.root), Settings())
        self.assertTrue(path.exists())
        path.unlink()
        self.assertEqual(load_settings(self.root), Settings())
        self.assertTrue(path.exists())

    def test_invalid_json_can_be_preserved(self):
        path = self.root / "beallitasok.json"
        path.write_bytes(b"broken settings")
        with self.assertRaises(InvalidSettings):
            load_settings(self.root)
        self.assertEqual(backup_settings(self.root).read_bytes(), path.read_bytes())
        self.assertEqual(path.read_bytes(), b"broken settings")

    def test_update_roundtrip_and_relative_absolute_paths(self):
        value = Settings(clerk="Árvíztűrő Tükörfúrógép", template="sablonok/minta.docx",
                         archive=str(self.root / "iratok"), main_sash=420, zoom="Teljes oldal")
        value.save(self.root)
        self.assertEqual(load_settings(self.root), value)
        self.assertEqual(value.archive_path(self.root), self.root / "iratok")
        self.assertEqual(value.template_path(self.root), self.root / "sablonok" / "minta.docx")
        self.assertIn(value.clerk, (self.root / "beallitasok.json").read_text(encoding="utf-8"))

    def test_unwritable_program_directory_surfaces_original_error(self):
        with patch("postaszamla.settings.NamedTemporaryFile", side_effect=PermissionError("read only")):
            with self.assertRaises(PermissionError):
                load_settings(self.root)
        self.assertFalse((self.root / "beallitasok.json").exists())


class ArchiveTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_documents_year_query_pdf_and_legacy(self):
        self.assertEqual(initial_year(), str(date.today().year))
        first = save_record(self.root, DEFAULT_TEMPLATE, LETTER)
        legacy = first.parent / "postaszámla_2026.01.01-01.08_ellátási.docx"
        legacy.write_bytes(DEFAULT_TEMPLATE.read_bytes())
        pdf = first.with_suffix(".PDF")
        pdf.write_bytes(b"fixture")
        (first.parent / "~$z.docx").touch()
        (self.root / "2025").mkdir()
        (self.root / "misc").mkdir()
        self.assertEqual(year_folders(self.root), ["2026", "2025"])
        modern, old = documents(self.root, "2026")
        self.assertEqual(modern.path, first)
        self.assertEqual(modern.pdf, pdf)
        self.assertEqual(modern.count, 1)
        self.assertIsNone(old.pdf)
        self.assertIsNone(old.count)
        self.assertEqual(old.period, (date(2026, 1, 1), date(2026, 1, 8)))
        self.assertEqual(documents(self.root, "2026", "01.08"), [old])
        self.assertIsNone(read_record(legacy))
        before = first.read_bytes()
        self.assertIn(LETTER.reference, text_preview(first))
        self.assertEqual(first.read_bytes(), before)

    def test_invoice_aggregation_and_roundtrip(self):
        both = replace(LETTER, invoices=(INVOICE, SECOND))
        self.assertEqual(Record.from_data(both.to_data()), both)
        self.assertEqual(calculate(INVOICE.costs)[-1], (200, 500, 700))
        result = both.to_letter()
        self.assertEqual((result.start, result.end), (SECOND.start, SECOND.end))
        self.assertEqual(result.invoices, ("0001", "0002"))
        self.assertEqual(calculate(result.costs)[-1], (600, 600, 1200))
        self.assertEqual(make_filename(result.start, result.end, result.costs),
                         "postaszámla_2026.12.25-2027.01.05_ellátási_mukodesi_ki_be_szallitas.docx")
        self.assertEqual(replace(both, invoices=both.invoices[:1]).to_letter(), LETTER.to_letter())
        with self.assertRaisesRegex(ValueError, "Legalább"):
            replace(LETTER, invoices=()).to_letter()

    def test_backup_and_rename_preserve_pdf(self):
        old = save_record(self.root, DEFAULT_TEMPLATE, LETTER)
        snapshot = read_record(old)
        pdf = old.with_suffix(".pdf")
        pdf.write_bytes(b"unchanged")
        edited = replace(LETTER, invoices=(*LETTER.invoices, SECOND))
        target = save_record(self.root, DEFAULT_TEMPLATE, edited, previous=old, expected=snapshot)
        self.assertNotEqual(old, target)
        self.assertFalse(old.exists())
        self.assertFalse(sidecar(old).exists())
        self.assertEqual(pdf.read_bytes(), b"unchanged")
        self.assertEqual(read_record(target).record, edited)
        backup = next((self.root / ".postaszamla-backups").glob("*"))
        self.assertEqual(read_record(backup / old.parent.name / old.name), snapshot)

    def test_failed_same_name_edit_restores_both_files(self):
        old = save_record(self.root, DEFAULT_TEMPLATE, LETTER)
        snapshot = read_record(old)
        before = old.read_bytes(), sidecar(old).read_bytes()
        real_replace = archive.os.replace

        def fail_docx_once(source, target):
            if ".postaszamla-stage-" in str(source) and target == old:
                raise PermissionError("Wordban nyitva")
            return real_replace(source, target)

        with patch("postaszamla.archive.os.replace", side_effect=fail_docx_once):
            with self.assertRaises(PermissionError):
                save_record(self.root, DEFAULT_TEMPLATE, replace(LETTER, reference="MINTA/4"),
                            previous=old, expected=snapshot)
        self.assertEqual((old.read_bytes(), sidecar(old).read_bytes()), before)
        self.assertEqual(read_record(old), snapshot)

    def test_failed_new_save_removes_own_sidecar(self):
        real_publish = archive.publish_new

        def fail_docx(source, target):
            if target.suffix == ".docx":
                raise PermissionError("Írási hiba")
            real_publish(source, target)

        with patch("postaszamla.archive.publish_new", side_effect=fail_docx):
            with self.assertRaises(PermissionError):
                save_record(self.root, DEFAULT_TEMPLATE, LETTER)
        self.assertEqual(list((self.root / "2026").iterdir()), [])

    def test_collision_and_external_changes_do_not_overwrite(self):
        target = save_record(self.root, DEFAULT_TEMPLATE, LETTER)
        snapshot = read_record(target)
        with self.assertRaises(FileExistsError):
            save_record(self.root, DEFAULT_TEMPLATE, LETTER)
        target.write_bytes(target.read_bytes() + b"external data")
        with self.assertRaisesRegex(ValueError, "időközben"):
            save_record(self.root, DEFAULT_TEMPLATE, LETTER, previous=target, expected=snapshot)
        self.assertTrue(target.read_bytes().endswith(b"external data"))
