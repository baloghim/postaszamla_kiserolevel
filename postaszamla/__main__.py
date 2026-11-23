import argparse
import sys
from pathlib import Path

from .config import load_letter
from .generator import generate
from .template import DEFAULT_TEMPLATE


class HungarianParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, "Hiba: Hibás parancssori argumentumok. A súgóhoz használd a --help kapcsolót.\n")


def main() -> int:
    if len(sys.argv) == 1:
        from .gui import main as desktop

        return desktop()
    parser = HungarianParser(
        prog="python -m postaszamla",
        description="Postaszámla-kísérőlevél készítése JSON-adatokból.",
        add_help=False,
        usage="%(prog)s ADATFÁJL --output MAPPA [--template SABLON] [--flat-output]",
    )
    parser._positionals.title = "Kötelező adatfájl"
    parser._optionals.title = "Kapcsolók"
    parser.add_argument("-h", "--help", action="help", help="Súgó megjelenítése.")
    parser.add_argument("input", type=Path, metavar="ADATFÁJL", help="UTF-8 JSON-adatfájl.")
    parser.add_argument("--output", type=Path, required=True, metavar="MAPPA", help="A dokumentumtár gyökérmappája.")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, metavar="SABLON",
                        help="Saját DOCX-sablon útvonala.")
    parser.add_argument("--flat-output", action="store_true",
                        help="Mentés közvetlenül a megadott mappába, év szerinti almappa nélkül.")
    options = parser.parse_args()
    try:
        target = generate(
            load_letter(options.input), options.output, options.template,
            year_subfolder=not options.flat_output,
        )
    except FileExistsError as error:
        print(f"Hiba: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Hiba: A fájlművelet sikertelen ({error.filename or options.output}).", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Hiba: {error}", file=sys.stderr)
        return 1
    print(f"Elkészült: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
