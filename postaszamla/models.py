from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Cost:
    operating: int
    benefits: int


@dataclass(frozen=True)
class Costs:
    postal: Cost
    transport: Cost
    forwarding: Cost
    mailbox: Cost

    def rows(self) -> tuple[Cost, ...]:
        return self.postal, self.transport, self.forwarding, self.mailbox


SERVICES = (
    ("Postai szolgáltatások", ""),
    ("Ki-, beszállítás", "ki_be_szallitas"),
    ("Belföldi utánküldés", "belfoldi_utankuldes"),
    ("Fiókbérlet szolgáltatás", "fiokberlet"),
)


@dataclass(frozen=True)
class Letter:
    start: date
    end: date
    reference: str
    sent: date
    invoices: tuple[str, ...]
    attachments: int
    dated: date
    costs: Costs
