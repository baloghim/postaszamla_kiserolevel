from datetime import date
from dataclasses import replace

import fitz
from PySide2.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide2.QtGui import QColor, QFont, QPagedPaintDevice, QPainter, QPdfWriter

from postaszamla.finance import calculate, forints
from postaszamla.filename import make_filename
from postaszamla.models import Cost, Costs, SERVICES
from postaszamla.records import Invoice, Record

ZERO = Cost(0, 0)
EMPTY_COSTS = Costs(ZERO, ZERO, ZERO, ZERO)
SERVICE_NAMES = tuple(name for name, _ in SERVICES) + ("Mindösszesen",)

DEMO = Record(
    "MINTA-028/2026", "Minta Dóra", "Példa Áron", "pénzügyi vezető",
    date(2026, 11, 23), date(2026, 11, 16),
    (
        Invoice("MINTA-101", date(2026, 11, 1), date(2026, 11, 7),
                Costs(Cost(5000, 40090), ZERO, ZERO, ZERO)),
        Invoice("MINTA-102", date(2026, 11, 8), date(2026, 11, 15),
                Costs(Cost(0, 22000), Cost(0, 14000), ZERO, Cost(0, 6000))),
    ),
)


def archive_rows():
    yield DEMO, True
    for index, (year, month, last_day) in enumerate(
        ((2026, 10, 31), (2026, 10, 17), (2026, 9, 30), (2026, 9, 12),
         (2026, 8, 29), (2026, 8, 15), (2025, 12, 20)), start=1
    ):
        first = date(year, month, last_day - 6)
        end = date(year, month, last_day)
        invoice = Invoice(f"MINTA-{120 + index}", first, end,
                          Costs(Cost(0, 35000 + 1000 * index), ZERO, ZERO, ZERO))
        yield replace(DEMO, reference=f"MINTA-{28 - index:03d}/{year}", dated=end, sent=end,
                      invoices=(invoice,)), index % 2 == 0


def filename(record):
    letter = record.to_letter()
    return make_filename(letter.start, letter.end, letter.costs)


def demo_pdf(record):
    """Paint a fictional specimen directly to PDF, independently of DOCX handling."""
    letter = record.to_letter()
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QIODevice.WriteOnly):
        raise RuntimeError("Az előnézet puffere nem nyitható meg.")
    writer = QPdfWriter(buffer)
    writer.setPageSize(QPagedPaintDevice.A4)
    writer.setResolution(72)
    painter = QPainter(writer)
    try:
        painter.setPen(QColor("#142441"))
        painter.setFont(QFont("Sans Serif", 18, QFont.Bold))
        painter.drawText(35, 58, "MINTA PÉNZÜGYI IRODA")
        painter.setFont(QFont("Sans Serif", 10))
        painter.drawText(35, 81, "Fiktív kísérőlevél")
        painter.setPen(QColor("#325985"))
        painter.drawLine(35, 97, 515, 97)
        painter.setPen(QColor("#1b283a"))
        lines = (
            f"Iktatószám: {record.reference}",
            "Tárgy: Postai számlák megküldése",
            f"Ügyintéző: {record.clerk}",
            f"Mellékletek száma: {len(record.invoices)} db",
            "",
            "Minta Osztályvezető részére",
            "Minta Pénzügyi Osztály",
            "",
            "Tisztelt Osztályvezető!",
            "A következő postai számlák költségösszesítőjét küldjük meg:",
            ", ".join(letter.invoices),
        )
        for index, content in enumerate(lines):
            painter.drawText(35, 122 + index * 19, content)
        values = [("Szolgáltatás", "Működési", "Ellátás", "Összesen")]
        values.extend((name, *(forints(value) for value in amounts))
                      for name, amounts in zip(SERVICE_NAMES, calculate(letter.costs)))
        for row, items in enumerate(values):
            y = 351 + row * 26
            if row in (0, len(values) - 1):
                painter.fillRect(35, y, 480, 26, QColor("#e3edf8"))
            for x in (35, 250, 338, 426, 515):
                painter.drawLine(x, y, x, y + 26)
            painter.drawLine(35, y, 515, y)
            for x, text in zip((41, 256, 344, 432), items, strict=True):
                painter.drawText(x, y + 17, text)
        painter.drawLine(35, 351 + len(values) * 26, 515, 351 + len(values) * 26)
        painter.drawText(35, 566, f"Mintaváros, {record.dated:%Y.%m.%d.}")
        painter.drawText(350, 595, record.signer)
        painter.drawText(350, 614, record.position)
    finally:
        painter.end()
        buffer.close()
    pdf = bytes(data)
    if len(record.invoices) > 1:
        with fitz.open(stream=pdf, filetype="pdf") as document:
            document.fullcopy_page(0)
            pdf = document.tobytes()
    return pdf
