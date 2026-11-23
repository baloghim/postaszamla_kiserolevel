from .models import Costs
from .validation import validate_costs


def calculate(costs: Costs) -> tuple[tuple[int, int, int], ...]:
    validate_costs(costs)
    rows = tuple(
        (cost.operating, cost.benefits, cost.operating + cost.benefits)
        for cost in costs.rows()
    )
    operating, benefits, total = (sum(column) for column in zip(*rows, strict=True))
    if operating + benefits != total:
        raise ValueError("A költségtáblázat sor- és oszlopösszege eltér.")
    return (*rows, (operating, benefits, total))


def forints(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " Ft"
