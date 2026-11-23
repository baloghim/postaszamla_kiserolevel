from pathlib import Path
import tkinter as tk
from tkinter import ttk

ICON_DIR = Path(__file__).with_name("icons")
ICON_NAMES = ("about", "docx", "edit", "help", "new", "next", "open",
              "pdf-missing", "pdf-present", "previous", "print", "refresh", "settings")
ICON_SIZES = (16, 20, 24, 28, 30, 32, 36, 42, 48)
ROW_BACKGROUND = "#ffffff"
ALTERNATE_BACKGROUND = "#f5f8fb"
SELECTED_BACKGROUND = "#c8e8f7"


class Icons:
    def __init__(self, root):
        self.root = root
        self.images = {}
        self.sheets = {}

    def get(self, name, logical_size):
        pixels = logical_size * self.root.winfo_fpixels("1i") / 96
        size = min(ICON_SIZES, key=lambda option: abs(option - pixels))
        key = name, size
        if key not in self.images:
            if size not in self.sheets:
                self.sheets[size] = tk.PhotoImage(master=self.root, file=ICON_DIR / "png" / f"{size}.png")
            start = ICON_NAMES.index(name) * size
            icon = tk.PhotoImage(master=self.root, width=size, height=size)
            icon.tk.call(icon, "copy", self.sheets[size], "-from", start, 0, start + size, size)
            self.images[key] = icon
        return self.images[key]


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.timer = self.window = None
        for event in ("<Enter>", "<FocusIn>"):
            widget.bind(event, self.schedule, add=True)
        for event in ("<Leave>", "<FocusOut>", "<ButtonPress>", "<Destroy>"):
            widget.bind(event, self.hide, add=True)

    def schedule(self, event):
        self.hide()
        self.timer = self.widget.after(550, self.show)

    def show(self):
        self.timer = None
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        label = ttk.Label(self.window, text=self.text, padding=(8, 5), style="Tooltip.TLabel")
        label.pack()
        x = min(self.widget.winfo_rootx(), self.widget.winfo_screenwidth() - label.winfo_reqwidth())
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.window.wm_geometry(f"+{max(0, x)}+{y}")

    def hide(self, event=None):
        if self.timer:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.window:
            self.window.destroy()
            self.window = None


class PdfBadges:
    """Place images in the PDF cells on Tk versions with images only in the tree column."""

    def __init__(self, tree, icons):
        self.tree = tree
        self.icons = {text: icons.get(name, 20) for text, name in
                      (("Van", "pdf-present"), ("Nincs", "pdf-missing"))}
        self.labels = []
        self.pending = None
        for event in ("<Configure>", "<ButtonRelease-1>", "<<TreeviewSelect>>"):
            tree.bind(event, self.schedule, add=True)
        tree.bind("<Destroy>", self.stop, add=True)

    def schedule(self, event=None):
        if not self.pending:
            self.pending = self.tree.after_idle(self.draw)

    def stop(self, event):
        if event.widget == self.tree and self.pending:
            self.tree.after_cancel(self.pending)
            self.pending = None

    def draw(self):
        self.pending = None
        selection = set(self.tree.selection())
        width, height = self.tree.winfo_width(), self.tree.winfo_height()
        used = 0
        for index, item in enumerate(self.tree.get_children()):
            box = self.tree.bbox(item, "pdf")
            if not box:
                continue
            x, y, cell_width, row_height = box
            if x < 0 or x + cell_width > width or y + row_height > height:
                continue
            image = self.icons[self.tree.set(item, "pdf")]
            if used == len(self.labels):
                label = tk.Label(self.tree, bd=0, highlightthickness=0, padx=0, pady=0)
                label.bind("<Button-1>", lambda event: self.select(event.widget.item))
                label.bind("<MouseWheel>", lambda event: self.tree.event_generate("<MouseWheel>", delta=event.delta))
                label.bind("<Button-4>", lambda event: self.tree.event_generate("<Button-4>"))
                label.bind("<Button-5>", lambda event: self.tree.event_generate("<Button-5>"))
                self.labels.append(label)
            label = self.labels[used]
            label.item = item
            background = SELECTED_BACKGROUND if item in selection else (
                ALTERNATE_BACKGROUND if index % 2 else ROW_BACKGROUND
            )
            label.configure(image=image, background=background)
            label.place(x=x + 1, y=y, width=cell_width - 2, height=row_height)
            used += 1
        for label in self.labels[used:]:
            label.place_forget()

    def select(self, item):
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.focus_set()
