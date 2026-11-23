from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from postaszamla.config import load_letter
from postaszamla.generator import generate
from postaszamla.models import Cost, Costs

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "minta.json"


def make_template():
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Fiktív fejléc"
    ref = doc.add_paragraph("Iktatószám: ")
    opening = ref.add_run("{{ik")
    opening.bold = True
    # Keep unrelated run content directly before the placeholder.
    opening._r.insert(1, OxmlElement("w:softHyphen"))
    ref.add_run("tatoszam}}").italic = True
    ref.add_run(" • Minta").underline = True
    doc.add_paragraph("Ügyintéző: {{ugyintezo}}")
    doc.add_paragraph("Melléklet: {{darabszam}} db")
    doc.add_paragraph("{{erkezett_datum}} a {{postaszamla_szamok}} számú száml{{tobbes}} megküldésével")
    doc.add_paragraph("Mintaváros, {{dátum}}")
    doc.add_paragraph("{{alairo}}")
    doc.add_paragraph("{{beosztas}}")
    table = doc.add_table(rows=7, cols=4)
    table.rows[1].cells[3].text = "D. (B.+C.)"
    for index, label in enumerate((
        "Postai szolgáltatások", "Ki-, beszállítás", "Belföldi utánküldés",
        "Fiókbérlet szolgáltatás", "Mindösszesen",
    ), 1):
        cells = table.rows[index + 1].cells
        cells[0].text = f"{index}. {label}"
        for cell, token in zip(cells[1:], ("mukodesi", "ellatas", "osszesen"), strict=True):
            paragraph = cell.paragraphs[0]
            paragraph.add_run("{{" + token)
            paragraph.add_run(str(index) + "}}")
    return doc


class OfficeTemplateTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.template = self.root / "minta.docx"
        self.letter = replace(load_letter(EXAMPLE), start=date(2026, 12, 27),
                              end=date(2027, 1, 2), sent=date(2027, 1, 4),
                              dated=date(2027, 1, 16))

    def test_office_generation_and_all_amounts(self):
        make_template().save(self.template)
        original = self.template.read_bytes()
        letter = replace(self.letter, costs=Costs(
            Cost(100, 200), Cost(1000, 22090), Cost(0, 4), Cost(8, 0)
        ))
        output = generate(letter, self.root, self.template)
        self.assertEqual(output.parent, self.root / "2026")
        self.assertEqual(
            output.name,
            "postaszámla_2026.12.27-2027.01.02_ellátási_mukodesi_ki_be_szallitas_belfoldi_utankuldes_fiokberlet.docx",
        )
        self.assertEqual(self.template.read_bytes(), original)
        generated = Document(output)
        self.assertEqual(generated.sections[0].header.paragraphs[0].text, "Fiktív fejléc")
        ref = generated.paragraphs[0]
        self.assertEqual(ref.text, "Iktatószám: MINTA-001/2026 • Minta")
        self.assertTrue(ref.runs[1].bold)
        self.assertTrue(ref.runs[3].underline)
        self.assertIsNotNone(ref.runs[1]._r.find(qn("w:softHyphen")))
        body = "\n".join(p.text for p in generated.paragraphs)
        self.assertIn("2027. január 4-én a MINTA-SZ-001 és MINTA-SZ-002 számú számlák", body)
        self.assertIn("Mintaváros, 2027. január 16.", body)
        self.assertIn("Melléklet: 2 db", body)
        self.assertIn("Ügyintéző: Minta Anna", body)
        self.assertIn("Minta Klára\npénzügyi vezető", body)
        self.assertNotIn("{{", body)
        table = generated.tables[0]
        self.assertEqual([tuple(cell.text for cell in row.cells[1:]) for row in table.rows[2:]], [
            ("100 Ft", "200 Ft", "300 Ft"),
            ("1 000 Ft", "22 090 Ft", "23 090 Ft"),
            ("0 Ft", "4 Ft", "4 Ft"),
            ("8 Ft", "0 Ft", "8 Ft"),
            ("1 108 Ft", "22 294 Ft", "23 402 Ft"),
        ])
        with self.assertRaises(FileExistsError):
            generate(letter, self.root, self.template)

    def test_singular_invoice_with_leading_zero(self):
        make_template().save(self.template)
        letter = replace(self.letter, invoices=("00001",), attachments=9)
        output = generate(letter, self.root, self.template, year_subfolder=False)
        self.assertEqual(output.parent, self.root)
        body = "\n".join(p.text for p in Document(output).paragraphs)
        self.assertIn("a 00001 számú számla megküldésével", body)
        self.assertIn("Melléklet: 1 db", body)
        self.assertEqual(replace(letter, attachments=None).attachment_count, 1)

    def test_reports_missing_and_unknown_tokens_before_creating_output(self):
        template = make_template()
        template.paragraphs[4].runs[0].text = "Mintaváros, {{datum}}"
        template.save(self.template)
        with self.assertRaisesRegex(ValueError, r"Hiányzó.*\{\{dátum\}\}.*Ismeretlen.*\{\{datum\}\}"):
            generate(self.letter, self.root, self.template)
        self.assertFalse((self.root / "2026").exists())

    def test_rejects_missing_invoices_and_office_fields(self):
        make_template().save(self.template)
        with self.assertRaisesRegex(ValueError, "számlaszám"):
            generate(replace(self.letter, invoices=()), self.root, self.template)
        with self.assertRaisesRegex(ValueError, "Ügyintéző"):
            generate(replace(self.letter, clerk=None), self.root, self.template)
