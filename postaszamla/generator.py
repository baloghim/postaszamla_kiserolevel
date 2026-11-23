from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile

from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError

from .dates import hungarian_date
from .filename import make_filename
from .finance import calculate, forints
from .invoices import format_invoice_numbers, invoice_suffix
from .models import Letter
from .template import DEFAULT_TEMPLATE, expense_table, open_template, replace_tokens, validate_tokens
from .validation import validate_letter


def invoice_text(invoices: tuple[str, ...]) -> str:
    if len(invoices) == 1:
        return f"a postai számlát (számlaszám: {invoices[0]})"
    return f"a következő számú postai számlákat: {format_invoice_numbers(invoices)}"


def letter_values(letter: Letter, legacy: bool) -> dict[str, str]:
    if legacy:
        count = letter.attachment_count
        return {
            "REFERENCE": letter.reference,
            "PERIOD": f"{hungarian_date(letter.start)} – {hungarian_date(letter.end)}",
            "SENT": hungarian_date(letter.sent),
            "INVOICES": invoice_text(letter.invoices),
            "ATTACHMENTS": f"{count} db" if count else "nincs",
            "DATED": hungarian_date(letter.dated),
        }

    required = (
        ("ugyintezo", "Ügyintéző (clerk)", letter.clerk),
        ("alairo", "Aláíró (signer)", letter.signer),
        ("beosztas", "Beosztás (position)", letter.position),
    )
    missing = [label for _, label, value in required if value is None]
    if missing:
        raise ValueError("A hivatali sablonhoz hiányzó adatok: " + ", ".join(missing) + ".")
    return {
        "iktatoszam": letter.reference,
        **{token: value for token, _, value in required},
        "darabszam": str(letter.invoice_count),
        "erkezett_datum": hungarian_date(letter.sent, suffixed=True),
        "postaszamla_szamok": format_invoice_numbers(letter.invoices),
        "tobbes": invoice_suffix(letter.invoice_count),
        "dátum": hungarian_date(letter.dated),
    }


def generate(
    letter: Letter,
    output_dir: Path,
    template: Path = DEFAULT_TEMPLATE,
    *,
    year_subfolder: bool = True,
) -> Path:
    validate_letter(letter)
    if year_subfolder:
        output_dir = output_dir / f"{letter.start.year:04d}"
    target = output_dir / make_filename(letter.start, letter.end, letter.costs)

    try:
        document = open_template(template)
    except (BadZipFile, PackageNotFoundError, XMLSyntaxError, KeyError, ValueError) as error:
        raise ValueError(f"Hibás DOCX-sablon ({template.name}): {error}") from error

    legacy, table_tokens = validate_tokens(document)
    table = expense_table(document, table_tokens)
    values = letter_values(letter, legacy)
    for tokens, amounts in zip(table_tokens, calculate(letter.costs), strict=True):
        values.update(zip(tokens, map(forints, amounts), strict=True))

    replace_tokens(document, values)
    for row, tokens in zip(table.rows[2:], table_tokens, strict=True):
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
