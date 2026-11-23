from datetime import date

MONTHS = (
    "január", "február", "március", "április", "május", "június",
    "július", "augusztus", "szeptember", "október", "november", "december",
)

# The suffix follows the spoken ordinal (másodikán, tizenkettedikén, ...).
DAY_SUFFIXES = (
    "jén", "án", "án", "én", "én", "án", "én", "án", "én", "én",
    "én", "én", "án", "én", "én", "án", "én", "án", "én", "án",
    "én", "én", "án", "én", "én", "án", "én", "án", "én", "án", "én",
)


def hungarian_date(value: date, *, suffixed: bool = False) -> str:
    ending = f"-{DAY_SUFFIXES[value.day - 1]}" if suffixed else "."
    return f"{value.year}. {MONTHS[value.month - 1]} {value.day}{ending}"
