from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile

from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError

from .filename import make_filename
from .finance import calculate, forints
from .models import Letter
from .template import DEFAULT_TEMPLATE, TABLE_TOKENS, expense_table, open_template, replace_tokens
from .validation import validate_letter

MONTHS = ("január", "február", "március", "április", "május", "június",
          "július", "augusztus", "szeptember", "október", "november", "december")


def hungarian_date(value: date) -> str:
    return f"{value.year}. {MONTHS[value.month - 1]} {value.day}."


def invoice_text(invoices: tuple[str, ...]) -> str:
    if len(invoices) == 1:
        return f"a postai számlát (számlaszám: {invoices[0]})"
    joined = ", ".join(invoices[:-1]) + " és " + invoices[-1]
    return f"a következő számú postai számlákat: {joined}"


def generate(letter: Letter, output_dir: Path, template: Path = DEFAULT_TEMPLATE) -> Path:
    validate_letter(letter)
    target = output_dir / make_filename(letter.start, letter.end, letter.costs)
    values = {
        "REFERENCE": letter.reference,
        "PERIOD": f"{hungarian_date(letter.start)} – {hungarian_date(letter.end)}",
        "SENT": hungarian_date(letter.sent),
        "INVOICES": invoice_text(letter.invoices),
        "ATTACHMENTS": f"{letter.attachments} db" if letter.attachments else "nincs",
        "DATED": hungarian_date(letter.dated),
    }
    for tokens, amounts in zip(TABLE_TOKENS, calculate(letter.costs), strict=True):
        values.update(zip(tokens, map(forints, amounts), strict=True))

    try:
        document = open_template(template)
    except (BadZipFile, PackageNotFoundError, XMLSyntaxError, KeyError, ValueError) as error:
        raise ValueError(f"Hibás DOCX-sablon ({template.name}): {error}") from error
    table = expense_table(document)
    replace_tokens(document, values)
    for row, tokens in zip(table.rows[2:], TABLE_TOKENS, strict=True):
        if [cell.text.strip() for cell in row.cells[1:]] != [values[token] for token in tokens]:
            raise ValueError("A mentendő táblázat összegei eltérnek a számított értékektől.")

    buffer = BytesIO()
    document.save(buffer)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        stream = target.open("xb")
    except FileExistsError as error:
        raise FileExistsError(f"Már létezik ilyen nevű dokumentum: {target}") from error
    try:
        with stream:
            stream.write(buffer.getbuffer())
    except OSError:
        target.unlink(missing_ok=True)
        raise
    return target
