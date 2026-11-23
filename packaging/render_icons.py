from pathlib import Path
from subprocess import DEVNULL, run
from tempfile import TemporaryDirectory
from PIL import Image

icons = Path(__file__).resolve().parent.parent / "postaszamla" / "icons"
sources = sorted((icons / "svg").glob("*.svg"))
with TemporaryDirectory() as directory:
    for size in (16, 20, 24, 28, 30, 32, 36, 42, 48):
        sprite = Image.new("RGBA", (size * len(sources), size))
        for index, source in enumerate(sources):
            output = Path(directory) / "icon.png"
            run(["inkscape", str(source), f"--export-filename={output}",
                 f"--export-width={size}", f"--export-height={size}"],
                check=True, stdout=DEVNULL, stderr=DEVNULL)
            with Image.open(output) as icon:
                sprite.paste(icon.convert("RGBA"), (index * size, 0))
        sprite.save(icons / "png" / f"{size}.png", optimize=True)
