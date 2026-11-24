"""Generate or check the machine-readable Qt icon source audit."""
import argparse
import json
import os
from pathlib import Path

from postaszamla.qt.edpd_graphics.icons import APP_ROLES, IconThemeManager
from postaszamla.qt.app import create_application


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = create_application()
    manager = IconThemeManager()
    themes = {}
    for theme in manager.choices():
        manager.set_theme(theme)
        themes[theme] = {role: manager.describe(role) for role in APP_ROLES}
    report = {"schema": 1, "application": manager.describe("application"), "themes": themes}
    document = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    output = Path(__file__).resolve().parents[1] / "docs/icon-sources.json"
    if args.check:
        if output.read_text(encoding="utf-8") != document:
            raise SystemExit("Outdated icon source report")
    else:
        output.write_text(document, encoding="utf-8")
    app.quit()


if __name__ == "__main__":
    main()
