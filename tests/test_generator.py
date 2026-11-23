import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zipfile import ZipFile

from docx import Document
from lxml import etree

from postaszamla.config import load_letter
from postaszamla.finance import calculate, forints
from postaszamla.generator import generate
from postaszamla.models import Cost, Costs
from postaszamla.template import DEFAULT_TEMPLATE

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "minta.json"


class LetterTests(TestCase):
    def test_sums_and_formatting(self):
        costs = Costs(Cost(15, 100), Cost(20, 200), Cost(30, 0), Cost(0, 45))
        self.assertEqual(calculate(costs), (
            (15, 100, 115), (20, 200, 220), (30, 0, 30), (0, 45, 45), (65, 345, 410),
        ))
        self.assertEqual(forints(106605), "106 605 Ft")
        self.assertEqual(forints(0), "0 Ft")

    def test_invalid_calendar_date_and_reversed_period(self):
        data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data.json"
            for start, expected in (("2026-02-30", "érvényes dátum"), ("2026-11-01", "korábbi")):
                with self.subTest(start=start):
                    path.write_text(json.dumps(dict(data, start=start)), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, expected):
                        load_letter(path)

    def test_docx_structure_and_no_overwrite(self):
        original = DEFAULT_TEMPLATE.read_bytes()
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            letter = load_letter(EXAMPLE)
            target = generate(letter, directory)
            self.assertEqual(target.name, "postaszámla_2026.10.24-10.31_ellátási_ki_be_szallitas.docx")
            first = target.read_bytes()
            with self.assertRaisesRegex(FileExistsError, "Már létezik"):
                generate(letter, directory)
            self.assertEqual(target.read_bytes(), first)
            self.assertEqual(DEFAULT_TEMPLATE.read_bytes(), original)
            doc = Document(target)
            self.assertEqual(len(doc.tables), 1)
            table = doc.tables[0]
            self.assertEqual((len(table.rows), len(table.columns)), (7, 4))
            self.assertEqual([cell.text for cell in table.rows[-1].cells],
                             ["Mindösszesen", "0 Ft", "247 225 Ft", "247 225 Ft"])
            self.assertEqual([cell.text for cell in table.rows[2].cells[1:]],
                             ["0 Ft", "71 110 Ft", "71 110 Ft"])
            body = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("Iktatószám: MINTA-001/2026", body)
            self.assertIn("Mellékletek száma: 2 db", body)
            self.assertIn("postai számlákat: MINTA-SZ-001 és MINTA-SZ-002", body)
            self.assertIn("2026. október 24. – 2026. október 31.", body)
            self.assertIn("2026. november 2.", body)
            self.assertIn("2026. november 4.", body)
            with ZipFile(target) as archive:
                self.assertFalse(any("/embeddings/" in name for name in archive.namelist()))
                for name in archive.namelist():
                    if name.endswith((".xml", ".rels")):
                        content = archive.read(name)
                        xml = etree.fromstring(content)
                        self.assertFalse(xml.xpath("//*[local-name()='OLEObject' or local-name()='object']"))
                        self.assertNotIn(b"{{", content)
                        self.assertNotIn(b"/relationships/oleObject", content)

    def test_custom_template_and_singular_invoice(self):
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            custom = directory / "custom.docx"
            template = Document(DEFAULT_TEMPLATE)
            paragraph = next(p for p in template.paragraphs if "{{REFERENCE}}" in p.text)
            paragraph.runs[-1].text = "{{REF"
            paragraph.add_run("ERENCE}}")
            template.sections[0].header.paragraphs[0].add_run(" – Próba")
            template.save(custom)
            letter = replace(load_letter(EXAMPLE), end=date(2026, 11, 1),
                             invoices=("MINTA-1",), attachments=0)
            doc = Document(generate(letter, directory, custom))
            self.assertIn("Próba", doc.sections[0].header.paragraphs[0].text)
            body = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("a postai számlát (számlaszám: MINTA-1)", body)
            self.assertIn("Mellékletek száma: nincs", body)
