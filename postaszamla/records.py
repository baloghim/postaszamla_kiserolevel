from dataclasses import asdict, dataclass
from datetime import date

from .config import parse_date
from .models import Cost, Costs, Letter
from .validation import validate_costs, validate_letter, validate_period

SERVICES_KEYS = ("postal", "transport", "forwarding", "mailbox")


@dataclass(frozen=True)
class Invoice:
    number: str
    start: date
    end: date
    costs: Costs


@dataclass(frozen=True)
class Record:
    reference: str
    clerk: str
    signer: str
    position: str
    dated: date
    sent: date
    invoices: tuple[Invoice, ...]

    def to_letter(self) -> Letter:
        for label, value in (("Ügyintéző", self.clerk), ("Aláíró", self.signer),
                             ("Beosztás", self.position)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label}: kötelező mező.")
        start, end = period(self.invoices)
        letter = Letter(
            start, end, self.reference, self.sent, tuple(item.number for item in self.invoices),
            None, self.dated, total_costs(tuple(item.costs for item in self.invoices)),
            self.clerk, self.signer, self.position,
        )
        validate_letter(letter)
        return letter

    def to_data(self) -> dict:
        result = asdict(self)
        for field in ("dated", "sent"):
            result[field] = result[field].isoformat()
        for invoice in result["invoices"]:
            for field in ("start", "end"):
                invoice[field] = invoice[field].isoformat()
        result["invoices"] = list(result["invoices"])
        return result

    @classmethod
    def from_data(cls, data: dict):
        try:
            invoices = tuple(
                Invoice(
                    item["number"], parse_date(item["start"], "Időszak kezdete"),
                    parse_date(item["end"], "Időszak vége"),
                    Costs(*(Cost(**item["costs"][key]) for key in SERVICES_KEYS)),
                )
                for item in data["invoices"]
            )
            record = cls(
                data["reference"], data["clerk"], data["signer"], data["position"],
                parse_date(data["dated"], "Keltezés"), parse_date(data["sent"], "Megküldés"), invoices,
            )
        except (TypeError, KeyError) as error:
            raise ValueError("A kísérőlevél adatfájljának szerkezete hibás.") from error
        record.to_letter()
        return record


def period(invoices: tuple[Invoice, ...]) -> tuple[date, date]:
    if not invoices:
        raise ValueError("Legalább egy számlát kell megadni.")
    for item in invoices:
        validate_period(item.start, item.end)
    return min(item.start for item in invoices), max(item.end for item in invoices)


def total_costs(costs: tuple[Costs, ...]) -> Costs:
    if not costs:
        raise ValueError("Legalább egy számlát kell megadni.")
    for item in costs:
        validate_costs(item, allow_zero=True)
    return Costs(*(
        Cost(sum(item.operating for item in column), sum(item.benefits for item in column))
        for column in zip(*(item.rows() for item in costs), strict=True)
    ))
