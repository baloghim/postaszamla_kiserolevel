import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table

from .models import SERVICES

DEFAULT_TEMPLATE = Path(__file__).with_name("templates") / "minta.docx"
TOKEN = re.compile(r"\{\{([^{}]*)\}\}")
LEGACY_TABLE_TOKENS = tuple(tuple(f"{column}{row}" for column in "BCD") for row in range(1, 6))
TABLE_TOKENS = tuple(
    tuple(f"{column}{row}" for column in ("mukodesi", "ellatas", "osszesen"))
    for row in range(1, 6)
)
LEGACY_FIELDS = ("REFERENCE", "PERIOD", "SENT", "INVOICES", "ATTACHMENTS", "DATED")
OFFICE_FIELDS = (
    "iktatoszam", "ugyintezo", "darabszam", "erkezett_datum", "postaszamla_szamok",
    "tobbes", "dátum", "alairo", "beosztas",
)


def open_template(path: Path):
    with ZipFile(path) as package:
        if any("/embeddings/" in name.lower() for name in package.namelist()):
            raise ValueError("A sablon beágyazott objektumot tartalmaz.")
    document = Document(path)
    for part in document.part.package.parts:
        if any(rel.reltype.endswith(("/oleObject", "/package")) for rel in part.rels.values()):
            raise ValueError("A sablon OLE- vagy csomaghivatkozást tartalmaz.")
    return document


def expense_table(document, table_tokens: tuple[tuple[str, ...], ...]) -> Table:
    markers = set().union(*table_tokens)
    tables = [
        table for table in document.tables
        if any(markers.intersection(TOKEN.findall(cell.text))
               for row in table.rows for cell in row.cells)
    ]
    if len(tables) != 1:
        raise ValueError("A sablonban pontosan egy költségtáblázat szükséges.")
    table = tables[0]
    if len(table.columns) != 4 or len(table.rows) != 7:
        raise ValueError("A költségtáblázat négyoszlopos, két fejléc- és öt adatsoros legyen.")

    labels = [name for name, _ in SERVICES] + ["Mindösszesen"]
    for index, (row, label, tokens) in enumerate(
        zip(table.rows[2:], labels, table_tokens, strict=True), start=1
    ):
        expected = [f"{{{{{token}}}}}" for token in tokens]
        cells = [cell.text.strip() for cell in row.cells]
        if not cells or cells[0] not in (label, f"{index}. {label}") or cells[1:] != expected:
            raise ValueError(f"Hibás költségtáblázat-sor: {label}. Várt helyőrzők: {', '.join(expected)}.")
    return table


def paragraphs(document):
    for part in document.part.package.parts:
        if part.content_type.endswith((".document.main+xml", ".header+xml", ".footer+xml")):
            yield from part.element.iter(qn("w:p"))


def text_spans(paragraph):
    """Collect text nodes with offsets without rewriting any Word runs."""
    spans = []
    chunks = []
    offset = 0
    for node in paragraph.xpath("./w:r/* | ./w:hyperlink/w:r/*"):
        if node.tag == qn("w:rPr"):
            continue
        if node.tag == qn("w:t"):
            chunk = node.text or ""
            if chunk:
                spans.append((offset, offset + len(chunk), node))
        else:
            chunk = "\n"
        chunks.append(chunk)
        offset += len(chunk)
    return "".join(chunks), spans


def paragraph_text(paragraph):
    # Nested text boxes have their own paragraphs.
    return "".join(node.text or "" for node in paragraph.iter(qn("w:t"))
                   if next(node.iterancestors(qn("w:p")), None) is paragraph)


def validate_tokens(document):
    seen = Counter()
    for paragraph in paragraphs(document):
        seen.update(TOKEN.findall(paragraph_text(paragraph)))
    legacy = bool(seen.keys() & set(LEGACY_FIELDS)) and not bool(seen.keys() & set(OFFICE_FIELDS))
    fields = LEGACY_FIELDS if legacy else OFFICE_FIELDS
    table_tokens = LEGACY_TABLE_TOKENS if legacy else TABLE_TOKENS
    expected = set(fields).union(*table_tokens)
    problems = []
    for label, names in (
        ("Hiányzó helyőrzők", expected - seen.keys()),
        ("Ismeretlen helyőrzők", seen.keys() - expected),
        ("Ismétlődő helyőrzők", {name for name in expected if seen[name] > 1}),
    ):
        if names:
            problems.append(f"{label}: " + ", ".join(f"{{{{{name}}}}}" for name in sorted(names)))
    if problems:
        raise ValueError(". ".join(problems) + ".")
    return legacy, table_tokens


def replace_tokens(document, values: dict[str, str]) -> None:
    for paragraph in paragraphs(document):
        source, spans = text_spans(paragraph)
        for match in reversed(list(TOKEN.finditer(source))):
            for start, end, node in spans:
                if end <= match.start() or start >= match.end():
                    continue
                left = max(0, match.start() - start)
                right = min(end - start, match.end() - start)
                replacement = values[match.group(1)] if start <= match.start() else ""
                node.text = node.text[:left] + replacement + node.text[right:]
                if node.text and node.text != node.text.strip():
                    node.set(qn("xml:space"), "preserve")

    for paragraph in paragraphs(document):
        match = TOKEN.search(paragraph_text(paragraph))
        if match:
            raise ValueError(f"Kitöltetlen helyőrző maradt a dokumentumban: {match.group(0)}.")
