from collections.abc import Sequence


def format_invoice_numbers(invoices: Sequence[str]) -> str:
    if len(invoices) == 1:
        return invoices[0]
    return ", ".join(invoices[:-1]) + " és " + invoices[-1]


def invoice_suffix(count: int) -> str:
    return "a" if count == 1 else "ák"
