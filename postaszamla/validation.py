from datetime import date

from .models import Costs, Letter, SERVICES


def validate_period(start: date, end: date) -> None:
    if type(start) is not date or type(end) is not date:
        raise ValueError("Az elszámolási időszak dátumai érvénytelenek.")
    if end < start:
        raise ValueError("Az elszámolási időszak vége korábbi a kezdeténél.")


def validate_costs(costs: Costs, *, allow_zero: bool = False) -> None:
    any_amount = False
    for (name, _), cost in zip(SERVICES, costs.rows(), strict=True):
        for column, amount in (("Működési", cost.operating), ("Ellátás", cost.benefits)):
            if type(amount) is not int or amount < 0:
                raise ValueError(f"{name}, {column}: nemnegatív egész forintösszeg szükséges.")
            any_amount |= amount > 0
    if not any_amount and not allow_zero:
        raise ValueError("Legalább egy költségtételnek nullánál nagyobbnak kell lennie.")


def validate_letter(letter: Letter) -> None:
    validate_period(letter.start, letter.end)
    validate_costs(letter.costs)
    if type(letter.sent) is not date or type(letter.dated) is not date:
        raise ValueError("A megküldés dátuma vagy a keltezés érvénytelen.")
    if not isinstance(letter.reference, str) or not letter.reference.strip():
        raise ValueError("Az iktatószám megadása kötelező.")
    if not isinstance(letter.invoices, (tuple, list)) or not letter.invoices or any(
        not isinstance(invoice, str) or not invoice.strip() for invoice in letter.invoices
    ):
        raise ValueError("Legalább egy nem üres számlaszámot kell megadni.")
    if letter.attachments is not None and (
        type(letter.attachments) is not int or letter.attachments < 0
    ):
        raise ValueError("A mellékletek száma nemnegatív egész szám legyen.")

    for label, value in (
        ("Iktatószám", letter.reference),
        *(("Számlaszám", invoice) for invoice in letter.invoices),
        ("Ügyintéző", letter.clerk),
        ("Aláíró", letter.signer),
        ("Beosztás", letter.position),
    ):
        if value is not None and (not isinstance(value, str) or not value.strip() or any(
            not (0x20 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD
                 or 0x10000 <= ord(char) <= 0x10FFFF)
            for char in value
        )):
            raise ValueError(f"{label}: nem üres, nyomtatható szöveg szükséges.")
