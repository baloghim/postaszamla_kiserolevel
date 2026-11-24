"""Capture the running Windows Qt application's release screenshots."""
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide2.QtGui import QFont, QPainter, QPdfWriter

from postaszamla.archive import save_record
from postaszamla.models import Cost, Costs
from postaszamla.qt.app import create_application
from postaszamla.qt.appearance import Appearance, style_choices
from postaszamla.qt.settings_dialog import SettingsDialog
from postaszamla.qt.window import MainWindow
from postaszamla.records import Invoice, Record
from postaszamla.settings import Settings
from postaszamla.template import DEFAULT_TEMPLATE


def capture(output):
    app = create_application()
    appearance = Appearance(app)
    output.mkdir(parents=True, exist_ok=True)
    zero = Cost(0, 0)
    costs = Costs(Cost(5000, 62090), Cost(0, 14000), zero, Cost(0, 6000))
    invoice = Invoice("MINTA-101", date(2026, 11, 1), date(2026, 11, 15), costs)
    record = Record("MINTA/026", "Minta Dóra", "Példa Áron", "pénzügyi vezető",
                    date(2026, 11, 23), date(2026, 11, 16), (invoice,))
    with TemporaryDirectory() as location:
        base = Path(location)
        Settings(clerk=record.clerk, signer=record.signer, position=record.position,
                 window_state="normal", zoom="Teljes oldal").save(base)
        archive = base / "dokumentumok"
        archive.mkdir()
        document = save_record(archive, DEFAULT_TEMPLATE, record)
        for month, number in ((10, "MINTA-092"), (9, "MINTA-081"), (8, "MINTA-074")):
            previous = replace(invoice, number=number, start=date(2026, month, 8), end=date(2026, month, 15))
            save_record(archive, DEFAULT_TEMPLATE, replace(record, invoices=(previous,)))
        pdf = document.with_suffix(".pdf")
        writer = QPdfWriter(str(pdf))
        writer.setResolution(72)
        painter = QPainter(writer)
        try:
            painter.setFont(QFont("Arial", 19, QFont.Bold))
            painter.drawText(42, 62, "MINTA PÉNZÜGYI IRODA")
            painter.setFont(QFont("Arial", 12))
            for y, line in enumerate(("Fiktív postaszámla-kísérőlevél", "Iktatószám: MINTA/026",
                                      "Időszak: 2026.11.01. – 2026.11.15.", "Számlaszám: MINTA-101",
                                      "Működési költség: 5 000 Ft", "Ellátási költség: 82 090 Ft",
                                      "Mindösszesen: 87 090 Ft"), 1):
                painter.drawText(42, 78 + y * 30, line)
        finally:
            painter.end()
        del writer

        window = MainWindow(appearance, base)
        window.resize(1200, 760)
        window.show()
        app.processEvents()
        window.restore_panels()
        window.reload(preferred=document)
        window.preview.select(None)
        window.preview.viewer.open_data(pdf.read_bytes())
        assert window.preview.viewer.pdf is not None
        choices = style_choices()
        assert [key for key, _ in choices] == ["xp-luna-blue", "fusion", "windows", "windowsvista"]
        for key, _ in choices:
            appearance.apply(key)
            app.processEvents()
            shot = window.grab()
            assert shot.width() == 1200 and shot.height() == 760
            assert shot.save(str(output / f"{key}.png"))

        appearance.apply("xp-luna-blue")
        dialog = SettingsDialog(window.settings, base, window)
        dialog.show()
        app.processEvents()
        assert dialog.grab().save(str(output / "beallitasok.png"))
        dialog.reject()
        window.close()


if __name__ == "__main__":
    capture(Path(sys.argv[1]))
