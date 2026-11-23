import re
from datetime import date

from .config import parse_date


def form_date(value: str, label: str) -> date:
    text = value.strip()
    if re.fullmatch(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.?", text):
        text = text.rstrip(".").replace(".", "-")
    return parse_date(text, label)


def amount(value: str) -> int:
    if not value.strip():
        return 0
    if not re.fullmatch(r"[0-9]+|[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+", value.strip()):
        raise ValueError("A költség mezőbe nemnegatív egész forintösszeget írjon.")
    return int("".join(value.split()))
