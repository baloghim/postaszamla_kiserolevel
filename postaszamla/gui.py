import sys
import tkinter as tk
from dataclasses import replace
from datetime import date
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, messagebox, ttk

from .archive import documents, initial_year, read_record, save_record, year_folders
from .editor import LetterEditor, center_dialog, confirm_dialog, display_date
from .preview import prepare_preview, render_pdf, word_action
from .settings import InvalidSettings, Settings, backup_settings, load_settings, program_directory

TITLE = "Postaszámla – Kísérőlevelek"
ZOOMS = ("Szélesség", "Teljes oldal", "50%", "75%", "100%", "125%", "150%", "200%")
COLUMNS = ("filename", "period", "count", "pdf")
UNAVAILABLE = "Nem érhető el"


def display_period(period):
    return " – ".join(map(display_date, period)) if period else "—"


def apply_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=("Segoe UI", 10), background="#edf3f6", foreground="#172b39")
    style.configure("TButton", padding=(10, 8), relief="flat", background="#dfe9ef")
    style.map("TButton", background=[("active", "#d0e3ea")])
    style.configure("Accent.TButton", background="#086f71", foreground="white", font=("Segoe UI", 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#0b8584")], foreground=[("active", "white")])
    style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"), foreground="#123846")
    style.configure("Muted.TLabel", foreground="#456273")
    style.configure("TableHead.TLabel", background="#d9e6ee", font=("Segoe UI", 10, "bold"))
    style.configure("Cell.TLabel", background="#f9fcfd")
    style.configure("Total.TLabel", background="#dcefe5", foreground="#075651", font=("Segoe UI", 10, "bold"))
    style.configure("Treeview", rowheight=max(25, int(root.winfo_fpixels("0.32i"))),
                    background="#f9fcfd", fieldbackground="#f9fcfd")
    style.configure("Treeview.Heading", background="#d9e6ee", padding=7, font=("Segoe UI", 10, "bold"))
    style.map("Treeview", background=[("selected", "#c6e4ef")], foreground=[("selected", "#123846")])


class PreviewPanel(ttk.Labelframe):
    def __init__(self, parent, zoom):
        super().__init__(parent, text="Dokumentum-előnézet", padding=8)
        self.zoom = tk.StringVar(value=zoom)
        self.path = self.data = self.image = None
        self.page = 0
        self.page_count = 0
        self.results = Queue()
        self.requests = Queue()
        self.resize_job = None
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 5))
        self.prev_button = ttk.Button(controls, width=3, text="‹", command=lambda: self.turn(-1))
        self.prev_button.pack(side="left")
        self.page_text = tk.StringVar(value="—")
        ttk.Label(controls, width=8, anchor="center", textvariable=self.page_text).pack(side="left")
        self.next_button = ttk.Button(controls, width=3, text="›", command=lambda: self.turn(1))
        self.next_button.pack(side="left")
        self.zoom_picker = ttk.Combobox(controls, state="readonly", width=13, textvariable=self.zoom, values=ZOOMS)
        self.zoom_picker.pack(side="right")
        self.zoom_picker.bind("<<ComboboxSelected>>", lambda event: self.draw_page())
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, style="Muted.TLabel", wraplength=480).pack(fill="x", pady=(0, 5))
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(body, background="#dce6ed", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.text = tk.Text(body, wrap="word", padx=20, pady=20, font=("Segoe UI", 11),
                            background="white", foreground="#172b39", state="disabled")
        self.yscroll = ttk.Scrollbar(body, command=self.canvas.yview)
        self.yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.yscroll.set, xscrollcommand=xscroll.set)
        self.canvas.bind("<Configure>", self.size_changed)
        self.canvas.bind("<MouseWheel>", lambda event: self.canvas.yview_scroll(-event.delta // 120, "units"))
        self.canvas.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda event: self.canvas.yview_scroll(1, "units"))
        Thread(target=self.worker, args=(self.requests, self.results), daemon=True).start()
        self.poll_job = self.after(100, self.poll)
        self.bind("<Destroy>", self.stop)
        self.controls()

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
        self.poll_job = self.after(100, self.poll)

    def size_changed(self, event):
        if self.resize_job:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(140, self.draw_page)

    def turn(self, delta):
        if 0 <= self.page + delta < self.page_count:
            self.page += delta
            self.draw_page()
            self.canvas.yview_moveto(0)

    def controls(self):
        self.prev_button.configure(state="normal" if self.page > 0 else "disabled")
        self.next_button.configure(state="normal" if self.page + 1 < self.page_count else "disabled")
        self.zoom_picker.configure(state="readonly" if self.data else "disabled")
        self.page_text.set(f"{self.page + 1} / {self.page_count}" if self.page_count else "—")

    def draw_page(self):
        self.resize_job = None
        if not self.data:
            return
        width = max(100, self.canvas.winfo_width() - 24)
        height = max(100, self.canvas.winfo_height() - 24)
        try:
            self.page_count, pixels = render_pdf(self.data, self.page, self.zoom.get(), width, height)
            self.image = tk.PhotoImage(data=pixels, format="ppm")
        except Exception:
            self.data = None
            self.page_count = 0
            self.controls()
            self.status.set("A PDF-oldal nem jeleníthető meg. Nyissa meg a dokumentumot Wordben.")
            return
        self.canvas.delete("all")
        canvas_width = max(self.image.width(), width)
        self.canvas.create_image((canvas_width - self.image.width()) / 2 + 12, 12,
                                 anchor="nw", image=self.image)
        self.canvas.configure(scrollregion=(0, 0, canvas_width + 24, self.image.height() + 24))
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
        self.info = {}
        self.last_query_job = None
        apply_theme(root)
        root.geometry(self.settings.geometry or "1200x760")
        self.build()
        if self.settings.window_state == "zoomed":
            self.maximize()
        self.refresh()
        self.preview.select(None)
        self.root.after_idle(self.restore_sashes)
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

    def restore_sashes(self):
        self.main_panes.sashpos(0, self.settings.main_sash or self.main_panes.winfo_width() // 2)
        self.left_panes.sashpos(0, self.settings.list_sash or self.left_panes.winfo_height() * 2 // 3)

    def build(self):
        bar = ttk.Frame(self.root, padding=(12, 10))
        bar.pack(fill="x")
        controls = (
            ("＋ Új kísérőlevél", lambda: self.edit(new=True), "Accent.TButton"),
            ("✎ Szerkesztés", self.edit, "TButton"),
            ("Megnyitás Wordben", self.open_in_word, "TButton"),
            ("Nyomtatás", lambda: self.open_in_word(printing=True), "TButton"),
            ("↻ Frissítés", self.refresh, "TButton"),
            ("⚙ Beállítások", self.configure, "TButton"),
            ("Névjegy", self.about, "TButton"),
            ("Súgó", self.help, "TButton"),
        )
        buttons = []
        for index, (text, action, style) in enumerate(controls):
            button = ttk.Button(bar, text=text, command=action, style=style)
            buttons.append(button)
            button.grid(row=0, column=index, padx=3, pady=2, sticky="ew")
        self.edit_button, self.open_button, self.print_button = buttons[1:4]

        def wrap(event):
            narrow = event.width < sum(button.winfo_reqwidth() + 6 for button in buttons)
            for index, button in enumerate(buttons):
                row, col = divmod(index, 4) if narrow else (0, index)
                button.grid_configure(row=row, column=col)

        bar.bind("<Configure>", wrap)
        ttk.Label(self.root, textvariable=self.footer, style="Muted.TLabel", padding=(14, 5)).pack(
            side="bottom", fill="x")
        self.main_panes = ttk.Panedwindow(self.root, orient="horizontal")
        self.main_panes.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.left_panes = ttk.Panedwindow(self.main_panes, orient="vertical")
        self.preview = PreviewPanel(self.main_panes, self.settings.zoom)
        self.main_panes.add(self.left_panes, weight=1)
        self.main_panes.add(self.preview, weight=1)
        listing = ttk.Labelframe(self.left_panes, text="Kísérőlevelek", padding=8)
        details = ttk.Labelframe(self.left_panes, text="A kijelölt kísérőlevél adatai", padding=8)
        self.left_panes.add(listing, weight=3)
        self.left_panes.add(details, weight=1)
        filterbar = ttk.Frame(listing)
        filterbar.pack(fill="x", pady=(0, 8))
        ttk.Label(filterbar, text="Év").pack(side="left")
        self.year_picker = ttk.Combobox(filterbar, state="readonly", textvariable=self.year, width=6)
        self.year_picker.pack(side="left", padx=(5, 12))
        self.year_picker.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        ttk.Label(filterbar, text="Fájlnév keresése").pack(side="left")
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
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=xscroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.tree.bind("<Return>", lambda event: self.open_in_word())
        self.doc_icon = tk.PhotoImage(width=15, height=17)
        self.doc_icon.put("#2168a6", to=(1, 0, 14, 17))
        self.doc_icon.put("#f8fbfd", to=(4, 3, 11, 14))
        for y in (5, 8, 11):
            self.doc_icon.put("#2168a6", to=(5, y, 10, y+1))
        for index, (key, label) in enumerate(zip(COLUMNS, ("Fájlnév", "Időszak", "Számlák", "PDF"), strict=True)):
            col = "#0" if index == 0 else key
            self.tree.heading(col, text=label, command=lambda k=key: self.sort(k))
            self.tree.column(col, width=self.settings.columns[index], minwidth=45, stretch=(index == 0),
                             anchor="w" if index < 2 else "center")
        ttk.Label(listing, text="✓ PDF: van kapcsolódó fájl     × PDF: hiányzik",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        for index, (key, label) in enumerate((
            ("reference", "Iktatószám"), ("clerk", "Ügyintéző"), ("signer", "Aláíró"),
            ("position", "Beosztás"), ("dated", "Keltezés"), ("sent", "Megküldés dátuma"),
            ("count", "Számlák száma"), ("period", "Összesített időszak"),
        )):
            row, col = index % 4, (index // 4) * 2
            details.columnconfigure(col + 1, weight=1)
            self.info[key] = tk.StringVar(value="—")
            ttk.Label(details, text=label).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=2)
            ttk.Label(details, textvariable=self.info[key], style="Muted.TLabel",
                      wraplength=145).grid(row=row, column=col+1, sticky="w", pady=2)

    def schedule_refresh(self, *_):
        if self.last_query_job:
            self.root.after_cancel(self.last_query_job)
        self.last_query_job = self.root.after(230, self.refresh)

    def sort(self, key):
        self.descending = not self.descending if self.sort_by == key else False
        self.sort_by = key
        self.refresh()

    def refresh(self, preferred=None):
        self.last_query_job = None
        active = preferred or (self.current.path if self.current else None)
        try:
            years = year_folders(self.archive)
            self.year_picker.configure(values=sorted(set(years + [self.year.get()]), reverse=True))
            entries = documents(self.archive, self.year.get(), self.search.get())
            self.footer.set(f"{len(entries)} kísérőlevél" if self.archive.is_dir()
                            else "A dokumentumtár a Beállítások ablakban adható meg.")
        except OSError:
            entries = []
            self.footer.set("A dokumentumtár nem olvasható. Ellenőrizze a beállított elérési utat.")
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
            self.tree.insert("", "end", iid=key, text=entry.path.name, image=self.doc_icon, values=(
                display_period(entry.period), f"{entry.count} db" if entry.count is not None else "—",
                "🟩 ✓ PDF" if entry.pdf else "🟥 × PDF",
            ))
            if entry.path == active:
                self.tree.selection_set(key)
                self.tree.see(key)
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
                    self.tree.column(col, width=width)
                self.maximize()
                self.root.after_idle(self.restore_sashes)
            self.refresh()

        SettingsDialog(self.root, self.settings, self.base, save)

    def about(self):
        messagebox.showinfo("Névjegy", TITLE + "\nv0.3.2", parent=self.root)

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
        self.settings.main_sash = self.main_panes.sashpos(0)
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


def main():
    root = tk.Tk()
    Application(root, program_directory())
    root.mainloop()


if __name__ == "__main__":
    main()
