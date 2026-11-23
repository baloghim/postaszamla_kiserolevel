from datetime import date

from .finance import calculate
from .models import Costs, SERVICES
from .validation import validate_period


def make_filename(start: date, end: date, costs: Costs) -> str:
    validate_period(start, end)
    *rows, (operating, benefits, _) = calculate(costs)
    start_label = f"{start.year:04d}.{start.month:02d}.{start.day:02d}"
    end_label = f"{end.month:02d}.{end.day:02d}"
    if start.year != end.year:
        end_label = f"{end.year:04d}.{end_label}"

    parts = [f"postaszámla_{start_label}-{end_label}"]
    if benefits:
        parts.append("ellátási")
    if operating:
        parts.append("mukodesi")
    parts.extend(
        tag for (_, tag), (operating, benefits, _) in zip(SERVICES, rows, strict=True)
        if tag and (operating or benefits)
    )
    return "_".join(parts) + ".docx"
