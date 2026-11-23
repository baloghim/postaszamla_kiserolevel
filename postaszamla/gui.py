import sys
import tkinter as tk
from contextlib import closing
from dataclasses import replace
from datetime import date
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, font, messagebox, ttk

from .archive import documents, initial_year, read_record, save_record, year_folders
from .editor import LetterEditor, center_dialog, confirm_dialog, display_date
from .gui_classic import ALTERNATE_BACKGROUND, FONT_FAMILY, WORKSPACE_BACKGROUND, Panel, apply_theme
from .gui_icons import Icons, PdfBadges, Tooltip
from .preview import prepare_preview, render_pdf, word_action
from .settings import InvalidSettings, Settings, backup_settings, load_settings, program_directory

TITLE = "Postaszámla – Kísérőlevelek"
VERSION = "0.4.0"
ZOOM_STEPS = (50, 75, 100, 125, 150, 200)
COLUMNS = ("filename", "period", "count", "pdf")
UNAVAILABLE = "Nem érhető el"


def display_period(period, *, compact=False):
    if not period:
        return "—"
    start, end = period
    end_label = f"{end:%m.%d.}" if compact and start.year == end.year else display_date(end)
    return f"{display_date(start)} – {end_label}"


class PreviewPanel(Panel):
    def __init__(self, parent, zoom, icons):
        super().__init__(parent, "Dokumentum-előnézet")
        self.zoom = tk.StringVar(value=zoom)
        self.path = self.data = self.image = None
        self.page = 0
        self.page_count = 0
        self.results = Queue()
        self.requests = Queue()
        self.resize_job = None
        self.status = tk.StringVar()
        self.page_text = tk.StringVar(value="—")
        self.zoom_text = tk.StringVar()
        self.build_controls(icons)
        self.status_hint = ttk.Label(self.content, textvariable=self.status, style="PanelContent.TLabel",
                                     padding=(5, 4), wraplength=480)
        self.body = body = ttk.Frame(self.content, relief="sunken", borderwidth=1)
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(body, background=WORKSPACE_BACKGROUND, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.text = tk.Text(body, wrap="word", padx=20, pady=20, font=(FONT_FAMILY, 11),
                            background="white", foreground="#172b39", state="disabled")
        self.yscroll = ttk.Scrollbar(body, command=self.canvas.yview)
        self.yscroll.grid(row=0, column=1, sticky="ns")
        self.xscroll = ttk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.yscroll.set, xscrollcommand=self.xscroll.set)
        self.canvas.bind("<Configure>", self.size_changed)
        self.canvas.bind("<MouseWheel>", lambda event: self.canvas.yview_scroll(-event.delta // 120, "units"))
        self.canvas.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda event: self.canvas.yview_scroll(1, "units"))
        self.status.trace_add("write", self.display_status)
        Thread(target=self.worker, args=(self.requests, self.results), daemon=True).start()
        self.poll_job = self.after(100, self.poll)
        self.bind("<Destroy>", self.stop)
        self.controls()

    def build_controls(self, icons):
        bar = ttk.Frame(self.content, style="ClassicBar.TFrame", padding=(4, 3))
        bar.pack(fill="x", pady=(0, 3))
        navigation = ttk.Frame(bar, style="ClassicBar.TFrame", padding=1)
        scaling = ttk.Frame(bar, style="ClassicBar.TFrame", padding=1)
        fitting = ttk.Frame(bar, style="ClassicBar.TFrame", padding=1)
        definitions = (
            (navigation, "first", "Első oldal", lambda: self.go_to_page(0)),
            (navigation, "previous", "Előző oldal", lambda: self.turn(-1)),
            (navigation, "next", "Következő oldal", lambda: self.turn(1)),
            (navigation, "last", "Utolsó oldal", lambda: self.go_to_page(self.page_count - 1)),
            (scaling, "zoom-in", "Nagyítás", lambda: self.step_zoom(1)),
            (scaling, "zoom-out", "Kicsinyítés", lambda: self.step_zoom(-1)),
            (fitting, "fit-width", "Szélesség", lambda: self.set_zoom("Szélesség")),
            (fitting, "fit-page", "Teljes oldal", lambda: self.set_zoom("Teljes oldal")),
        )
        self.view_buttons = {}
        for group, key, label, action in definitions:
            button = ttk.Button(group, image=icons.get(key, 20), command=action, style="Preview.TButton",
                                text=label, compound="left" if group is fitting else "image")
            button.pack(side="left", padx=1)
            Tooltip(button, label)
            self.view_buttons[key] = button
        self.prev_button = self.view_buttons["previous"]
        self.next_button = self.view_buttons["next"]
        ttk.Label(navigation, width=8, anchor="center", textvariable=self.page_text,
                  style="Bar.TLabel").pack(side="left", padx=(4, 1))
        ttk.Label(scaling, width=5, anchor="center", textvariable=self.zoom_text,
                  style="Bar.TLabel").pack(side="left", padx=1)

        def arrange(event):
            row = column = occupied = 0
            for group in (navigation, scaling, fitting):
                needed = group.winfo_reqwidth() + 6
                if occupied and occupied + needed > event.width - 8:
                    row, column, occupied = row + 1, 0, 0
                group.grid(row=row, column=column, sticky="w", padx=(0, 3))
                occupied += needed
                column += 1

        for index, group in enumerate((navigation, scaling, fitting)):
            group.grid(row=0, column=index, sticky="w", padx=(0, 3))
        bar.bind("<Configure>", arrange)

    def display_status(self, *_):
        self.canvas.delete("preview-status")
        message = self.status.get()
        if self.text.winfo_manager() and message:
            self.status_hint.pack(fill="x", before=self.body)
        else:
            self.status_hint.pack_forget()
            if message and not self.data:
                width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
                self.canvas.create_text(width / 2, height / 2, text=message, fill="#ffffff", justify="center",
                                        width=max(1, width - 36), font=(FONT_FAMILY, 11),
                                        tags="preview-status")

    @staticmethod
    def worker(requests, results):
        while True:
            request = requests.get()
            while request is not None:
                try:
                    request = requests.get_nowait()
                except Empty:
                    break
            if request is None:
                return
            token, path = request
            try:
                result = prepare_preview(path)
            except Exception:
                result = ("error", "")
            results.put((token, result))

    def stop(self, event):
        if event.widget == self:
            self.after_cancel(self.poll_job)
            if self.resize_job:
                self.after_cancel(self.resize_job)
            self.requests.put(None)

    def select(self, path):
        self.token = object()
        self.path, self.data, self.image = path, None, None
        self.page = self.page_count = 0
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0, 0, 0, 0))
        self.xscroll.grid_remove()
        self.text.grid_remove()
        self.canvas.yview_moveto(0)
        self.canvas.xview_moveto(0)
        self.yscroll.configure(command=self.canvas.yview)
        self.status.set("Előnézet készítése…" if path else "Válasszon egy kísérőlevelet a listából.")
        self.controls()
        if path:
            self.requests.put((self.token, path))

    def poll(self):
        while True:
            try:
                token, (kind, data) = self.results.get_nowait()
            except Empty:
                break
            if token is not self.token:
                continue
            if kind == "pdf":
                self.data = data
                self.status.set("")
                self.draw_page()
            elif kind == "error":
                self.status.set("Az előnézet nem készíthető el. Nyissa meg a dokumentumot Wordben.")
            else:
                hint = "A Word-alapú előnézet nem érhető el. " if kind == "fallback" else ""
                self.status.set(hint + "Szöveges előnézet. A nyomtatási elrendezéshez nyissa meg Wordben.")
                self.text.configure(state="normal")
                self.text.delete("1.0", "end")
                self.text.insert("1.0", data)
                self.text.configure(state="disabled", yscrollcommand=self.yscroll.set)
                self.text.grid(row=0, column=0, sticky="nsew")
                self.text.tkraise()
                self.yscroll.configure(command=self.text.yview)
                self.display_status()
        self.poll_job = self.after(100, self.poll)

    def size_changed(self, event):
        self.display_status()
        if self.resize_job:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(140, self.draw_page)

    def turn(self, delta):
        self.go_to_page(self.page + delta)

    def go_to_page(self, index):
        if 0 <= index < self.page_count and index != self.page:
            self.page = index
            self.draw_page()
            self.canvas.yview_moveto(0)

    def set_zoom(self, value):
        if self.data and value != self.zoom.get():
            self.zoom.set(value)
            self.draw_page()

    def step_zoom(self, direction):
        if not self.data or not self.image:
            return
        zoom = self.zoom.get()
        if zoom.endswith("%"):
            current = int(zoom[:-1])
        else:
            # A fitted view starts from its actual displayed scale on the current page.
            import pypdfium2

            with pypdfium2.PdfDocument(self.data) as document, closing(document[self.page]) as page:
                current = self.image.width() * 75 / page.get_width()
        stops = ZOOM_STEPS if direction > 0 else reversed(ZOOM_STEPS)
        for percentage in stops:
            if (percentage - current) * direction > 0.5:
                self.set_zoom(f"{percentage}%")
                break

    def controls(self):
        zoom = self.zoom.get()
        enabled = (self.page > 0, self.page > 0, self.page + 1 < self.page_count,
                   self.page + 1 < self.page_count, bool(self.data) and zoom != "200%",
                   bool(self.data) and zoom != "50%", bool(self.data), bool(self.data))
        for control, allowed in zip(self.view_buttons.values(), enabled, strict=True):
            control.configure(state="normal" if allowed else "disabled")
        for name, mode in (("fit-width", "Szélesség"), ("fit-page", "Teljes oldal")):
            self.view_buttons[name].configure(style="Fit.Preview.TButton" if zoom == mode else "Preview.TButton")
        self.page_text.set(f"{self.page + 1} / {self.page_count}" if self.page_count else "—")
        self.zoom_text.set(zoom if zoom.endswith("%") and self.data else "")

    def draw_page(self):
        if self.resize_job:
            self.after_cancel(self.resize_job)
            self.resize_job = None
        viewport = self.canvas.winfo_width()
        if not self.data:
            return
        margin = min(12, (viewport - 1) // 2)
        width = viewport - 2 * margin
        height = max(1, self.canvas.winfo_height() - 24)
        try:
            self.page_count, pixels = render_pdf(self.data, self.page, self.zoom.get(), width, height)
            self.image = tk.PhotoImage(data=pixels, format="ppm")
        except Exception:
            self.data = None
            self.page_count = 0
            self.canvas.delete("all")
            self.xscroll.grid_remove()
            self.controls()
            self.status.set("A PDF-oldal nem jeleníthető meg. Nyissa meg a dokumentumot Wordben.")
            return
        self.canvas.delete("all")
        content_width = self.image.width() + 2 * margin if self.image.width() > viewport else viewport
        left = (content_width - self.image.width()) // 2
        self.canvas.create_rectangle(left + 3, 15, left + self.image.width() + 3, self.image.height() + 15,
                                     fill="#52647d", outline="")
        self.canvas.create_image(left, 12, anchor="nw", image=self.image)
        self.canvas.configure(scrollregion=(0, 0, content_width, self.image.height() + 24))
        if content_width > viewport:
            self.xscroll.grid(row=1, column=0, sticky="ew")
        else:
            self.xscroll.grid_remove()
            self.canvas.xview_moveto(0)
        self.controls()


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings, base, save):
        super().__init__(parent)
        self.title("Beállítások")
        self.transient(parent)
        self.minsize(580, 300)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        self.fields = {}
        for index, (key, label) in enumerate((
            ("archive", "Dokumentumtár"), ("template", "Word-sablon"),
            ("clerk", "Ügyintéző"), ("signer", "Aláíró"), ("position", "Aláíró beosztása"),
        )):
            variable = self.fields[key] = tk.StringVar(value=getattr(settings, key))
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky="w", padx=(0, 8), pady=5)
            ttk.Entry(frame, textvariable=variable).grid(row=index, column=1, sticky="ew", pady=5)
            if index < 2:
                ttk.Button(frame, text="Tallózás…", command=lambda k=key: self.browse(k)).grid(
                    row=index, column=2, padx=(8, 0))
        self.absolute_hint = ttk.Label(frame, text="Az üres Word-sablon mező a mellékelt fiktív sablont használja.",
                                       wraplength=500, style="Muted.TLabel")
        self.absolute_hint.grid(row=5, column=0, columnspan=3, sticky="w", pady=8)
        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=3, sticky="ew")
        self.reset_requested = False

        def reset():
            if confirm_dialog(self, "Alaphelyzet", "Visszaállítja a beállítások alapértékeit?"):
                self.reset_requested = True
                for name, variable in self.fields.items():
                    variable.set(getattr(Settings(), name))

        def submit():
            values = {key: var.get().strip() for key, var in self.fields.items()}
            updated = replace(Settings() if self.reset_requested else settings, **values)
            try:
                archive = updated.archive_path(base)
                template = updated.template_path(base)
                if not values["archive"]:
                    raise ValueError("Adja meg a dokumentumtár gyökérmappáját.")
                if not archive.is_dir() and archive == Settings().archive_path(base):
                    archive.mkdir(exist_ok=True)
                if not archive.is_dir():
                    raise ValueError("A dokumentumtár nem érhető el.")
                next(archive.iterdir(), None)
                if template.suffix.casefold() != ".docx" or not template.is_file():
                    raise ValueError("A megadott DOCX-sablon nem érhető el.")
                with template.open("rb"):
                    pass
                save(updated, self.reset_requested)
            except (OSError, ValueError) as error:
                messagebox.showerror("Beállítások", str(error), parent=self)
                return
            self.destroy()

        ttk.Button(buttons, text="Alaphelyzet", command=reset).pack(side="left")
        ttk.Button(buttons, text="Elvetés", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Mentés", style="Accent.TButton", command=submit).pack(side="right")
        self.bind("<Escape>", lambda event: self.destroy())
        center_dialog(self, parent, width=620, height=320)
        if not self.winfo_viewable():
            self.wait_visibility()
        self.grab_set()

    def browse(self, key):
        path = (filedialog.askdirectory(parent=self) if key == "archive" else
                filedialog.askopenfilename(parent=self, filetypes=[("Word-dokumentum", "*.docx")]))
        if path:
            self.fields[key].set(path)


class Application:
    def __init__(self, root, base):
        self.root, self.base = root, base
        self.root.title(TITLE)
        self.root.minsize(680, 480)
        self.settings_writable = True
        self.settings = self.start_settings()
        self.sort_by, self.descending = "period", True
        self.entries = {}
        self.current = None
        self.metadata = None
        self.year = tk.StringVar(value=initial_year())
        self.search = tk.StringVar()
        self.footer = tk.StringVar()
        self.result_count = tk.StringVar()
        self.info = {}
        self.last_query_job = None
        apply_theme(root)
        self.icons = Icons(root)
        self.root.iconphoto(True, self.icons.get("docx", 24))
        self.sash_start = None
        root.geometry(self.settings.geometry or "1200x760")
        self.build()
        self.maximize()
        self.refresh()
        self.preview.select(None)
        self.initial_pane_binding = self.main_panes.bind("<Map>", self.initial_panes_mapped, add=True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-n>", lambda event: self.edit(new=True))
        self.root.bind("<Control-f>", lambda event: self.search_entry.focus_set())
        self.root.bind("<F5>", lambda event: self.refresh())
        self.root.bind("<F1>", lambda event: self.help())

    @property
    def archive(self):
        return self.settings.archive_path(self.base)

    def start_settings(self):
        try:
            return load_settings(self.base)
        except InvalidSettings as error:
            try:
                copy = backup_settings(self.base)
                prompt = f"{error}\n\nBiztonsági másolat: {copy.name}\n\nVisszaállítja az alapbeállításokat?"
                if messagebox.askyesno("Hibás beállítások", prompt, parent=self.root):
                    Settings().save(self.base)
                else:
                    self.settings_writable = False
            except OSError as failure:
                self.settings_writable = False
                messagebox.showerror("Beállítások", f"A beállítások nem menthetők: {failure}", parent=self.root)
            return Settings()
        except OSError as error:
            messagebox.showerror("Beállítások", f"A beállítások nem olvashatók vagy nem menthetők: {error}",
                                 parent=self.root)
            return Settings()

    def maximize(self):
        try:
            self.root.state("zoomed")
        except tk.TclError:
            try:
                self.root.attributes("-zoomed", True)
            except tk.TclError:
                pass

    def initial_panes_mapped(self, event):
        self.main_panes.unbind("<Map>", self.initial_pane_binding)
        self.root.after_idle(self.restore_sashes)

    def restore_sashes(self):
        available = self.left_panes.winfo_width() + self.preview.winfo_width()
        self.main_panes.sashpos(0, self.settings.main_sash or available // 2)
        height = self.left_panes.winfo_height()
        details_height = self.details_panel.winfo_reqheight()
        preferred = self.settings.list_sash or height - details_height - 20
        self.left_panes.sashpos(0, max(0, min(preferred, height - details_height - 5)))

    def start_sash_drag(self, event):
        if str(self.main_panes.identify(event.x, event.y)) == "0":
            self.sash_start = self.main_panes.sashpos(0)

    def end_sash_drag(self, event):
        position = self.main_panes.sashpos(0)
        if self.sash_start is not None and position != self.sash_start:
            self.settings.main_sash = position
        self.sash_start = None

    def build_toolbar(self):
        bar = ttk.Frame(self.root, style="ClassicBar.TFrame", padding=(6, 4))
        bar.pack(fill="x")
        left = ttk.Frame(bar, style="ClassicBar.TFrame")
        right = ttk.Frame(bar, style="ClassicBar.TFrame")
        bar.columnconfigure(1, weight=1)
        controls = (
            ("new", "Új kísérőlevél", lambda: self.edit(new=True), "Új kísérőlevél létrehozása (Ctrl+N)"),
            ("edit", "Szerkesztés", self.edit, "A kijelölt kísérőlevél szerkesztése"),
            ("open", "Megnyitás Wordben", self.open_in_word, "A kijelölt DOCX megnyitása Wordben"),
            ("print", "Nyomtatás", lambda: self.open_in_word(printing=True), "A kijelölt dokumentum nyomtatása"),
            ("refresh", "Frissítés", self.refresh, "A dokumentumlista frissítése (F5)"),
            ("settings", "Beállítások", self.configure, "A dokumentumtár és az alkalmazás beállításai"),
            ("about", "Névjegy", self.about, "A program verziószáma és adatai"),
            ("help", "Súgó", self.help, "Használati útmutató és gyorsbillentyűk (F1)"),
        )
        self.toolbar_buttons = []
        for index, (icon, text, action, tooltip) in enumerate(controls):
            button = ttk.Button(left if index < 5 else right, text=text, command=action,
                                image=self.icons.get(icon, 30), compound="left",
                                style="Accent.Toolbar.TButton" if index == 0 else "Toolbar.TButton")
            self.toolbar_buttons.append(button)
            Tooltip(button, tooltip)
        self.edit_button, self.open_button, self.print_button = self.toolbar_buttons[1:4]

        def arrange(event=None):
            available = (event.width if event else self.root.winfo_width()) - 24
            total = sum(button.winfo_reqwidth() + 8 for button in self.toolbar_buttons)
            narrow = available < total
            left.grid(row=0, column=0, columnspan=3 if narrow else 1, sticky="w")
            right.grid(row=1 if narrow else 0, column=2, sticky="e")
            for group in (self.toolbar_buttons[:5], self.toolbar_buttons[5:]):
                row = column = occupied = 0
                for button in group:
                    required = button.winfo_reqwidth() + 8
                    if narrow and occupied and occupied + required > available:
                        row, column, occupied = row + 1, 0, 0
                    button.grid(row=row, column=column, padx=4, pady=2, sticky="ew")
                    column += 1
                    occupied += required

        bar.bind("<Configure>", arrange)
        self.root.after_idle(arrange)

    def build(self):
        self.build_toolbar()
        status = ttk.Frame(self.root, style="ClassicBar.TFrame", padding=(3, 2))
        status.pack(side="bottom", fill="x")
        ttk.Label(status, text=f"v{VERSION}", style="StatusField.TLabel").pack(side="left", padx=(0, 3))
        for value in (self.year, self.result_count, self.footer):
            field = ttk.Label(status, textvariable=value, style="StatusField.TLabel")
            field.pack(side="left", padx=(0, 3), fill="x", expand=value is self.footer)
        self.main_panes = ttk.Panedwindow(self.root, orient="horizontal")
        self.main_panes.pack(fill="both", expand=True, padx=3, pady=3)
        self.left_panes = ttk.Panedwindow(self.main_panes, orient="vertical")
        self.preview = PreviewPanel(self.main_panes, self.settings.zoom, self.icons)
        self.main_panes.add(self.left_panes, weight=1)
        self.main_panes.add(self.preview, weight=1)
        self.main_panes.bind("<ButtonPress-1>", self.start_sash_drag, add=True)
        self.main_panes.bind("<ButtonRelease-1>", self.end_sash_drag, add=True)
        self.list_panel = Panel(self.left_panes, "Kísérőlevelek")
        self.details_panel = Panel(self.left_panes, "A kijelölt kísérőlevél adatai")
        listing, details = self.list_panel.content, self.details_panel.content
        self.left_panes.add(self.list_panel, weight=1)
        self.left_panes.add(self.details_panel, weight=0)
        filterbar = ttk.Frame(listing, style="PanelContent.TFrame")
        filterbar.pack(fill="x", pady=(0, 4))
        ttk.Label(filterbar, text="Év", style="PanelContent.TLabel").pack(side="left")
        self.year_picker = ttk.Combobox(filterbar, state="readonly", textvariable=self.year, width=6)
        self.year_picker.pack(side="left", padx=(5, 12))
        self.year_picker.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        ttk.Label(filterbar, text="Fájlnév keresése", style="PanelContent.TLabel").pack(side="left")
        self.search_entry = ttk.Entry(filterbar, textvariable=self.search, width=10)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.search.trace_add("write", self.schedule_refresh)
        holder = ttk.Frame(listing)
        holder.pack(fill="both", expand=True)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(holder, columns=COLUMNS[1:], selectmode="browse")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(holder, command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.pdf_badges = PdfBadges(self.tree, self.icons)

        def scroll_updated(scrollbar, first, last):
            scrollbar.set(first, last)
            self.pdf_badges.schedule()

        self.tree.configure(yscrollcommand=lambda *fractions: scroll_updated(scroll, *fractions),
                            xscrollcommand=lambda *fractions: scroll_updated(xscroll, *fractions))
        self.tree.bind("<<TreeviewSelect>>", self.select, add=True)
        self.tree.bind("<Return>", lambda event: self.open_in_word())
        self.doc_icon = self.icons.get("docx", 20)
        self.tree.tag_configure("alternate", background=ALTERNATE_BACKGROUND)
        heading_font = font.Font(root=self.root, font=ttk.Style(self.root).lookup("Treeview.Heading", "font"))
        heading_margin = round(self.root.winfo_fpixels("0.26i"))
        for index, (key, label) in enumerate(zip(COLUMNS, ("Fájlnév", "Időszak", "Számlák", "PDF"), strict=True)):
            minimum = max(45, heading_font.measure(label) + heading_margin)
            col = "#0" if index == 0 else key
            self.tree.heading(col, text=label, anchor="w" if index == 0 else "center",
                              command=lambda k=key: self.sort(k))
            self.tree.column(col, width=max(minimum, self.settings.columns[index]),
                             minwidth=minimum, stretch=(index == 0),
                             anchor="w" if index < 2 else "center")
        legend = ttk.Frame(listing, style="PanelContent.TFrame")
        legend.pack(anchor="w", pady=(4, 0))
        for key, label in (("pdf-present", "Van PDF"), ("pdf-missing", "Nincs PDF")):
            ttk.Label(legend, text=label, image=self.icons.get(key, 16), compound="left",
                      style="PanelContent.TLabel").pack(side="left", padx=(0, 12))
        for index, (key, label) in enumerate((
            ("reference", "Iktatószám"), ("clerk", "Ügyintéző"), ("signer", "Aláíró"),
            ("position", "Beosztás"), ("dated", "Keltezés"), ("sent", "Megküldés dátuma"),
            ("count", "Számlák száma"), ("period", "Összesített időszak"),
        )):
            row, col = index % 4, (index // 4) * 2
            details.columnconfigure(col + 1, weight=1)
            self.info[key] = tk.StringVar(value="—")
            ttk.Label(details, text=label, style="PanelContent.TLabel").grid(
                row=row, column=col, sticky="nw", padx=(5, 10), pady=2)
            ttk.Label(details, textvariable=self.info[key], style="PanelContent.TLabel", justify="left",
                      wraplength=215).grid(row=row, column=col+1, sticky="nw", pady=2)

    def schedule_refresh(self, *_):
        if self.last_query_job:
            self.root.after_cancel(self.last_query_job)
        self.last_query_job = self.root.after(230, self.refresh)

    def sort(self, key):
        self.descending = not self.descending if self.sort_by == key else False
        self.sort_by = key
        self.refresh()

    def refresh(self, preferred=None):
        if self.last_query_job:
            self.root.after_cancel(self.last_query_job)
            self.last_query_job = None
        active = preferred or (self.current.path if self.current else None)
        try:
            years = year_folders(self.archive)
            self.year_picker.configure(values=sorted(set(years + [self.year.get()]), reverse=True))
            entries = documents(self.archive, self.year.get(), self.search.get())
            self.footer.set("Válasszon egy kísérőlevelet a listából." if self.archive.is_dir()
                            else "A dokumentumtár a Beállítások ablakban adható meg.")
        except OSError:
            entries = []
            self.footer.set("A dokumentumtár nem olvasható. Ellenőrizze a beállított elérési utat.")
        self.result_count.set(f"{len(entries)} kísérőlevél")
        sorters = {
            "filename": lambda item: item.path.name.casefold(),
            "period": lambda item: (item.period or (date.min, date.min), item.path.name.casefold()),
            "count": lambda item: -1 if item.count is None else item.count,
            "pdf": lambda item: item.pdf is not None,
        }
        entries.sort(key=sorters[self.sort_by], reverse=self.descending)
        self.tree.delete(*self.tree.get_children())
        self.entries.clear()
        for index, entry in enumerate(entries):
            key = str(index)
            self.entries[key] = entry
            self.tree.insert("", "end", iid=key, text=entry.path.name, image=self.doc_icon,
                             tags=("alternate",) if index % 2 else (), values=(
                                 display_period(entry.period, compact=True),
                                 f"{entry.count} db" if entry.count is not None else "—",
                                 "Van" if entry.pdf else "Nincs",
                             ))
            if entry.path == active:
                self.tree.selection_set(key)
                self.tree.see(key)
        self.pdf_badges.schedule()
        self.select(force=True)

    def select(self, event=None, *, force=False):
        selection = self.tree.selection()
        current = self.entries.get(selection[0]) if selection else None
        if current == self.current and not force:
            return
        self.current = current
        self.metadata = read_record(current.path) if current else None
        record = self.metadata.record if self.metadata else None
        for button, enabled in ((self.edit_button, record is not None),
                                (self.open_button, current is not None), (self.print_button, current is not None)):
            button.configure(state="normal" if enabled else "disabled")
        for key, variable in self.info.items():
            if not current:
                value = "—"
            elif key == "period":
                value = display_period(current.period) if current.period else UNAVAILABLE
            elif key == "count":
                value = f"{current.count} db" if current.count is not None else UNAVAILABLE
            elif record:
                value = getattr(record, key)
                value = display_date(value) if isinstance(value, date) else value
            else:
                value = UNAVAILABLE
            variable.set(value)
        if current:
            self.footer.set("Kapcsolódó PDF található. A naprakészség nincs ellenőrizve." if current.pdf else
                            "Nincs kapcsolódó PDF.")
            if not record:
                self.footer.set(self.footer.get() + " A levél megtekinthető vagy Wordben szerkeszthető.")
        elif not force:
            self.footer.set("Válasszon egy kísérőlevelet a listából.")
        self.preview.select(current.path if current else None)

    def edit(self, new=False):
        previous = None if new or not self.current else self.current.path
        snapshot = None if new else self.metadata
        if not new and (not snapshot or not previous or not confirm_dialog(
            self.root, "Szerkesztés megerősítése", "Biztosan szeretné szerkeszteni a kijelölt kísérőlevelet?"
        )):
            return

        def save(record):
            archive = self.archive
            if archive == Settings().archive_path(self.base):
                archive.mkdir(exist_ok=True)
            return save_record(archive, self.settings.template_path(self.base), record,
                               previous=previous, expected=snapshot)

        editor = LetterEditor(self.root, self.settings, save, snapshot.record if snapshot else None)
        self.root.wait_window(editor)
        path = getattr(editor, "saved_path", None)
        if path:
            self.year.set(path.parent.name)
            self.search.set("")
            self.refresh(preferred=path)

    def open_in_word(self, printing=False):
        if self.current:
            try:
                if not printing or confirm_dialog(self.root, "Nyomtatás", "Kinyomtatja a kijelölt kísérőlevelet?"):
                    word_action(self.current.path, printing=printing)
            except OSError as error:
                messagebox.showerror("Word-művelet", str(error), parent=self.root)

    def configure(self):
        def save(settings, reset):
            settings.save(self.base)
            self.settings = settings
            self.settings_writable = True
            if reset:
                self.preview.zoom.set(settings.zoom)
                self.preview.draw_page()
                for col, width in zip(("#0", *COLUMNS[1:]), settings.columns, strict=True):
                    self.tree.column(col, width=max(width, self.tree.column(col, "minwidth")))
                self.maximize()
                self.root.after_idle(self.restore_sashes)
            self.refresh()

        SettingsDialog(self.root, self.settings, self.base, save)

    def about(self):
        messagebox.showinfo("Névjegy", f"{TITLE}\nv{VERSION}", parent=self.root)

    def help(self):
        messagebox.showinfo(
            "Súgó", "A Beállításokban adja meg a dokumentumtárat és a Word-sablont. "
            "A leveleket év és fájlnév szerint keresheti. A teljes adattartalommal "
            "rendelkező levelek az alkalmazásban szerkeszthetők.\n\n"
            "Ctrl+N: új levél  •  Ctrl+F: keresés  •  F5: frissítés",
            parent=self.root,
        )

    def close(self):
        state = self.root.state()
        if sys.platform != "win32" and state != "zoomed" and self.root.attributes("-zoomed"):
            state = "zoomed"
        self.settings.window_state = "zoomed" if state == "zoomed" else "normal"
        if self.settings.window_state == "normal":
            self.settings.geometry = self.root.geometry()
        self.settings.list_sash = self.left_panes.sashpos(0)
        self.settings.columns = tuple(self.tree.column(col, "width") for col in ("#0", *COLUMNS[1:]))
        self.settings.zoom = self.preview.zoom.get()
        self.settings.last_year = self.year.get()
        try:
            if self.settings_writable:
                self.settings.save(self.base)
        except OSError as error:
            messagebox.showerror("Beállítások", f"A beállítások nem menthetők: {error}", parent=self.root)
        self.root.destroy()


def create_root():
    if sys.platform == "win32":
        from ctypes import windll

        windll.user32.SetProcessDPIAware()
    return tk.Tk()


def main():
    root = create_root()
    Application(root, program_directory())
    root.mainloop()


if __name__ == "__main__":
    main()
