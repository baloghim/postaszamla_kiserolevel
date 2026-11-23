"""Classic main-window surfaces drawn with Tk's built-in image elements."""

import sys
import tkinter as tk
from tkinter import ttk

ROW_BACKGROUND = "#ffffff"
ALTERNATE_BACKGROUND = "#eff4fc"
SELECTED_BACKGROUND = "#285dab"
WORKSPACE_BACKGROUND = "#78889e"
FONT_FAMILY = "Tahoma" if sys.platform == "win32" else "DejaVu Sans"

CREAM_BAR = ((0, "#fffdf3"), (0.58, "#f2efdf"), (1, "#dedac6"))
CREAM_BUTTON = ((0, "#fffef6"), (0.49, "#f9f6e8"), (0.52, "#eee8d4"), (1, "#dbd5bc"))
CREAM_HOVER = ((0, "#ffffff"), (0.52, "#fffae6"), (1, "#efe1ad"))
CREAM_PRESSED = ((0, "#d8d1b6"), (1, "#f2eddc"))
BLUE_TITLE = ((0, "#275aac"), (0.12, "#67a4ef"), (0.52, "#3572ce"), (1, "#17468f"))
BLUE_BUTTON = ((0, "#f3faff"), (0.53, "#dceaff"), (0.56, "#c5dcff"), (1, "#aac8f0"))
BLUE_HOVER = ((0, "#ffffff"), (0.56, "#e1f1ff"), (1, "#afcdf4"))
BLUE_PRESSED = ((0, "#97bcea"), (1, "#d2e3fa"))


def gradient(root, height, stops, light, dark):
    """Create a DPI-sized gradient with a light top and a darker bottom bevel."""
    height = max(4, round(height * root.winfo_fpixels("1i") / 96))
    result = tk.PhotoImage(master=root, width=9, height=height)
    colors = [(position, tuple(bytes.fromhex(color[1:]))) for position, color in stops]
    for row in range(height):
        fraction = row / (height - 1)
        for (start, first), (end, second) in zip(colors, colors[1:]):
            if fraction <= end:
                part = (fraction - start) / (end - start)
                rgb = (round(a + (b - a) * part) for a, b in zip(first, second, strict=True))
                result.put("#" + "".join(f"{channel:02x}" for channel in rgb), to=(0, row, 9, row + 1))
                break
    result.put(light, to=(0, 0, 9, 1))
    result.put(light, to=(0, 1, 1, height - 1))
    result.put(dark, to=(0, height - 1, 9, height))
    result.put(dark, to=(8, 1, 9, height - 1))
    return result


def apply_theme(root):
    style = ttk.Style(root)
    if "classic-desktop" not in style.theme_names():
        style.theme_create("classic-desktop", parent="clam")
    style.theme_use("classic-desktop")
    style.configure(".", font=(FONT_FAMILY, 10), background="#e9edf4", foreground="#142335",
                    bordercolor="#a7afba", lightcolor="#ffffff", darkcolor="#a8acb2",
                    fieldbackground=ROW_BACKGROUND, selectbackground=SELECTED_BACKGROUND,
                    selectforeground="#ffffff")
    style.configure("TButton", padding=(10, 7), relief="raised", background="#f5f1e4")
    style.configure("Accent.TButton", background="#d1e2fa", font=(FONT_FAMILY, 10, "bold"))
    style.configure("Title.TLabel", font=(FONT_FAMILY, 17, "bold"), foreground="#123846")
    style.configure("Muted.TLabel", foreground="#43556b")
    style.configure("Panel.TFrame", relief="groove", borderwidth=2, background="#f8faff")
    style.configure("PanelContent.TFrame", background="#f8faff")
    style.configure("PanelContent.TLabel", background="#f8faff")
    style.configure("PanelTitle.TLabel", foreground="#ffffff", padding=(8, 4),
                    font=(FONT_FAMILY, 10, "bold"))
    style.configure("Bar.TLabel", background="#f2efdf")
    style.configure("StatusField.TLabel", padding=(7, 3), relief="sunken", borderwidth=1,
                    background="#f8f5e8")
    style.configure("Tooltip.TLabel", background="#fffdea", relief="solid", borderwidth=1)
    style.configure("TableHead.TLabel", background="#d9e6ee", font=(FONT_FAMILY, 10, "bold"))
    style.configure("Cell.TLabel", background="#f9fcfd")
    style.configure("Total.TLabel", background="#dcefe5", foreground="#075651", font=(FONT_FAMILY, 10, "bold"))
    style.configure("Treeview", rowheight=max(27, round(root.winfo_fpixels("0.32i"))), borderwidth=1,
                    background=ROW_BACKGROUND, fieldbackground=ROW_BACKGROUND)
    style.configure("Treeview.Heading", padding=(6, 5), font=(FONT_FAMILY, 10, "bold"))
    style.map("Treeview", background=[("selected", SELECTED_BACKGROUND)], foreground=[("selected", "#ffffff")])
    style.configure("TScrollbar", background="#e8e6d9", troughcolor="#f3f2e9", borderwidth=1)
    style.map("TScrollbar", background=[("active", "#d4e2f5"), ("pressed", "#b3c8e2")])

    if hasattr(root, "_classic_images"):
        return
    root._classic_images = []

    def element(name, height, stops, bevel, states=()):
        default = gradient(root, height, stops, *bevel)
        variants = [(state, gradient(root, height, colors, *edges)) for state, colors, edges in states]
        root._classic_images.extend([default, *(image for _, image in variants)])
        style.element_create(name, "image", default, *variants, border=(2, 2, 2, 2), sticky="nsew")
        return name

    cream_edges = "#fffdf6", "#a7a28b"
    blue_edges = "#f5fbff", "#6486bc"
    bar = element("Classic.bar", 38, CREAM_BAR, cream_edges)
    title = element("Classic.title", 26, BLUE_TITLE, ("#9bc5ff", "#143975"))
    button = element("Classic.button", 36, CREAM_BUTTON, cream_edges, (
        ("disabled", CREAM_BAR, ("#fbf9ef", "#c6c1ae")),
        ("pressed", CREAM_PRESSED, ("#a7a28b", "#fffdf6")),
        ("active", CREAM_HOVER, cream_edges),
    ))
    accent = element("Classic.accent", 36, BLUE_BUTTON, blue_edges, (
        ("disabled", CREAM_BAR, cream_edges),
        ("pressed", BLUE_PRESSED, ("#5678a9", "#eef6ff")),
        ("active", BLUE_HOVER, blue_edges),
    ))
    heading = element("Classic.column", 28, CREAM_BAR, cream_edges,
                      (("active", CREAM_HOVER, cream_edges),))

    style.layout("ClassicBar.TFrame", [(bar, {"sticky": "nsew"})])
    label_layout = style.layout("TLabel")[0][1]
    label_layout.pop("border", None)
    style.layout("PanelTitle.TLabel", [(title, label_layout)])
    button_layout = style.layout("TButton")[0][1]
    button_layout.pop("border", None)
    for name, surface, padding in (
        ("Toolbar.TButton", button, (10, 4)),
        ("Accent.Toolbar.TButton", accent, (10, 4)),
        ("Preview.TButton", button, (5, 3)),
        ("Fit.Preview.TButton", accent, (5, 3)),
    ):
        style.layout(name, [(surface, button_layout)])
        style.configure(name, padding=padding)
    style.configure("Accent.Toolbar.TButton", font=(FONT_FAMILY, 10, "bold"))
    original = style.layout("Treeview.Heading")
    style.layout("Treeview.Heading", [original[0], (heading, original[1][1])])


class Panel(ttk.Frame):
    def __init__(self, parent, title, **options):
        super().__init__(parent, style="Panel.TFrame", padding=4, **options)
        self.title_label = ttk.Label(self, text=title, style="PanelTitle.TLabel")
        self.title_label.pack(fill="x", pady=(0, 4))
        self.content = ttk.Frame(self, style="PanelContent.TFrame")
        self.content.pack(fill="both", expand=True)
