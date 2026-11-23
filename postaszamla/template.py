import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from .models import SERVICES

DEFAULT_TEMPLATE = Path(__file__).with_name("templates") / "minta.docx"
TOKEN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
TABLE_TOKENS = tuple(
    tuple(f"{column}{row}" for column in "BCD") for row in range(1, 6)
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


def expense_table(document) -> Table:
    tables = [
        table for table in document.tables
        if any(TOKEN.search(cell.text) and "{{B1}}" in cell.text
               for row in table.rows for cell in row.cells)
    ]
    if len(tables) != 1:
        raise ValueError("A sablonban pontosan egy költségtáblázat szükséges.")
    table = tables[0]
    if len(table.columns) != 4 or len(table.rows) != 7:
        raise ValueError("A költségtáblázat négyoszlopos, két fejléc- és öt adatsoros legyen.")
    labels = [name for name, _ in SERVICES] + ["Mindösszesen"]
    for row, label, tokens in zip(table.rows[2:], labels, TABLE_TOKENS, strict=True):
        if [cell.text.strip() for cell in row.cells] != [
            label, *(f"{{{{{token}}}}}" for token in tokens)
        ]:
            raise ValueError(f"Hibás költségtáblázat-sor a sablonban: {label}.")
    return table


def replace_tokens(document, values: dict[str, str]) -> None:
    paragraphs = [
        Paragraph(element, part)
        for part in document.part.package.parts
        if part.content_type.endswith((".document.main+xml", ".header+xml", ".footer+xml"))
        for element in part.element.iter(qn("w:p"))
    ]
    seen = Counter(
        match.group(1) for paragraph in paragraphs for match in TOKEN.finditer(paragraph.text)
    )
    if seen != Counter(values.keys()):
        raise ValueError("A sablon helyőrzői eltérnek az előírt készlettől. "
                         "Minden helyőrző pontosan egyszer szerepeljen.")
    for paragraph in paragraphs:
        runs = paragraph.runs
        source = "".join(run.text for run in runs)
        offset = 0
        spans = []
        for run in runs:
            spans.append((offset, offset + len(run.text), run))
            offset += len(run.text)
        matches = list(TOKEN.finditer(source))
        if [match.group(1) for match in matches] != TOKEN.findall(paragraph.text):
            raise ValueError("A sablon helyőrzői közvetlenül a bekezdés szövegében legyenek.")
        for match in reversed(matches):
            for start, end, run in spans:
                if start == end or end <= match.start() or start >= match.end():
                    continue
                left = max(0, match.start() - start)
                right = min(end - start, match.end() - start)
                replacement = values[match.group(1)] if start <= match.start() else ""
                run.text = run.text[:left] + replacement + run.text[right:]
