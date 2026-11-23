import json
import re
from datetime import date
from pathlib import Path

from .models import Cost, Costs, Letter
from .validation import validate_letter


def parse_date(value: object, label: str) -> date:
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError(f"{label}: érvényes dátumot adj meg ÉÉÉÉ-HH-NN formában.")


def load_letter(path: Path) -> Letter:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Az adatfájl érvényes UTF-8 kódolású JSON legyen.") from error

    try:
        costs = Costs(**{
            service: Cost(**data["costs"][service])
            for service in ("postal", "transport", "forwarding", "mailbox")
        })
        invoices = data["invoices"]
        if not isinstance(invoices, list):
            raise ValueError("A számlaszámokat JSON-listában kell megadni.")
        letter = Letter(
            start=parse_date(data["start"], "Időszak kezdete"),
            end=parse_date(data["end"], "Időszak vége"),
            reference=data["reference"],
            sent=parse_date(data["sent"], "Megküldés dátuma"),
            invoices=tuple(invoices),
            attachments=data["attachments"],
            dated=parse_date(data["dated"], "Keltezés"),
            costs=costs,
        )
    except KeyError as error:
        raise ValueError(f"Hiányzó adatmező: {error.args[0]}.") from error
    except TypeError as error:
        raise ValueError("Az adatfájl szerkezete eltér a mintától.") from error
    validate_letter(letter)
    return letter
