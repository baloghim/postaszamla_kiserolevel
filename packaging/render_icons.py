from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

icons = Path(__file__).resolve().parent.parent / "postaszamla" / "icons"
images = {}
for source in (icons / "original").glob("*.png"):
    with Image.open(source) as icon:
        images[source.stem] = icon.convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS)

add = images.pop("add").resize((52, 52), Image.Resampling.LANCZOS)
images["new"].alpha_composite(add, (73, 73))

pdf = images.pop("pdf")
for name, color in (("pdf-present", "#187846"), ("pdf-missing", "#a12825")):
    badge = pdf.copy()
    draw = ImageDraw.Draw(badge)
    draw.rounded_rectangle((8, 75, 118, 118), radius=9, fill=color, outline="#ffffff", width=3)
    draw.text((63, 96), "PDF", fill="#ffffff", font=ImageFont.load_default(size=34), anchor="mm",
              stroke_width=1)
    images[name] = badge

width = images["fit-page"].copy()
draw = ImageDraw.Draw(width)
draw.rounded_rectangle((9, 72, 88, 113), radius=7, fill="#245aa2", outline="#ffffff", width=3)
draw.line((23, 93, 75, 93), fill="#ffffff", width=6)
draw.polygon(((16, 93), (31, 83), (31, 103)), fill="#ffffff")
draw.polygon(((82, 93), (67, 83), (67, 103)), fill="#ffffff")
images["fit-width"] = width

for size in (16, 20, 24, 28, 30, 32, 36, 42, 48, 56, 64):
    sprite = Image.new("RGBA", (size * len(images), size))
    for index, name in enumerate(sorted(images)):
        sprite.paste(images[name].resize((size, size), Image.Resampling.LANCZOS), (index * size, 0))
    sprite.save(icons / "png" / f"{size}.png", optimize=True)
