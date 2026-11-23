import re
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from .config import parse_date
from .filename import make_filename
from .finance import calculate, forints
from .models import Cost, Costs, SERVICES
from .records import Invoice, Record, period, total_costs

LABELS = [name for name, _ in SERVICES] + ["Mindösszesen"]
HEADINGS = ("Szolgáltatás megnevezése", "Működési (Ft)", "Ellátás (Ft)", "Összesen (Ft)")


def display_date(value: date) -> str:
    return f"{value:%Y.%m.%d.}"


def form_date(value: str, label: str) -> date:
    text = value.strip()
    if re.fullmatch(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.?", text):
        text = text.rstrip(".").replace(".", "-")
    return parse_date(text, label)


def amount(value: str) -> int:
    if not value.strip():
        return 0
    if not re.fullmatch(r"[0-9]+|[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+", value.strip()):
        raise ValueError("A költség mezőbe nemnegatív egész forintösszeget írjon.")
    return int("".join(value.split()))


def center_dialog(dialog, parent, width=None, height=None):
    dialog.update_idletasks()
    width = width or dialog.winfo_reqwidth()
    height = height or dialog.winfo_reqheight()
    x = max(0, parent.winfo_rootx() + (parent.winfo_width() - width) // 2)
    y = max(0, parent.winfo_rooty() + (parent.winfo_height() - height) // 2)
    dialog.geometry(f"{width}x{height}+{x}+{y}")


def confirm_dialog(parent, title, prompt):
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.resizable(False, False)
    answer = False
    previous_grab = parent.grab_current()

    def accept():
        nonlocal answer
        answer = True
        dialog.destroy()

    ttk.Label(dialog, text=prompt, padding=24, wraplength=420).pack(fill="x")
    actions = ttk.Frame(dialog, padding=(16, 0, 16, 16))
    actions.pack(fill="x")
    cancel = ttk.Button(actions, text="Mégse", command=dialog.destroy)
    cancel.pack(side="right", padx=(8, 0))
    ttk.Button(actions, text="Igen", style="Accent.TButton", command=accept).pack(side="right")
    dialog.bind("<Escape>", lambda event: dialog.destroy())
    center_dialog(dialog, parent)
    if not dialog.winfo_viewable():
        dialog.wait_visibility()
    dialog.grab_set()
    cancel.focus_set()
    parent.wait_window(dialog)
    if previous_grab and previous_grab.winfo_exists():
        previous_grab.grab_set()
    return answer


class LetterEditor(tk.Toplevel):
    def __init__(self, parent, settings, save, record=None):
        super().__init__(parent)
        self.title("Kísérőlevél szerkesztése" if record else "Új kísérőlevél létrehozása")
        self.transient(parent)
        self.minsize(650, 460)
        self.configure(background="#eff5f7")
        self.save_record = save
        self.editing = record is not None
        self.invoices = []
        self.selected = 0
        self.common = {}
        self.live = []
        self.summary = []
        self.preview_name = tk.StringVar()
        self.period_text = tk.StringVar()
        self._build(settings, record)
        for item in record.invoices if record else (None,):
            self.add_invoice(item)
        self.select_invoice(0)
        self.bind("<Escape>", lambda event: self.destroy())
        center_dialog(self, parent, int(self.winfo_screenwidth() * .85),
                      int(self.winfo_screenheight() * .83))
        if not self.winfo_viewable():
            self.wait_visibility()
        self.grab_set()
        self.first_entry.focus_set()

    def _build(self, settings, record):
        canvas = tk.Canvas(self, background="#eff5f7", highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        content = ttk.Frame(canvas, padding=16)
        window = canvas.create_window(0, 0, window=content, anchor="nw")
        content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-event.delta // 120, "units"))
        ttk.Label(content, text=self.title(), style="Title.TLabel").pack(fill="x", pady=(0, 12))
        common = ttk.Labelframe(content, text="Kísérőlevél közös adatai", padding=12)
        common.pack(fill="x", pady=(0, 10))
        for index, (key, label, default) in enumerate((
            ("reference", "Iktatószám", ""),
            ("clerk", "Ügyintéző", settings.clerk),
            ("dated", "Levél keltezése", display_date(date.today())),
            ("sent", "Megküldés dátuma", ""),
            ("signer", "Aláíró", settings.signer),
            ("position", "Aláíró beosztása", settings.position),
        )):
            value = getattr(record, key) if record else default
            variable = self.common[key] = tk.StringVar(value=display_date(value) if isinstance(value, date) else value)
            row, col = divmod(index, 3)
            common.columnconfigure(col, weight=1, uniform="common")
            ttk.Label(common, text=label).grid(row=row*2, column=col, sticky="w", padx=5, pady=(4, 2))
            entry = ttk.Entry(common, textvariable=variable, width=12)
            entry.grid(row=row*2+1, column=col, sticky="ew", padx=5)
            if index == 0:
                self.first_entry = entry

        invoices = ttk.Labelframe(content, text="Postaszámlák", padding=12)
        invoices.pack(fill="x", pady=(0, 10))
        toolbar = ttk.Frame(invoices)
        toolbar.pack(fill="x", pady=(0, 8))
        self.choices = ttk.Combobox(toolbar, state="readonly", width=32)
        self.choices.pack(side="left")
        self.choices.bind("<<ComboboxSelected>>", lambda event: self.select_invoice(self.choices.current()))
        ttk.Button(toolbar, text="Számla eltávolítása", command=self.remove_invoice).pack(side="right")
        ttk.Button(toolbar, text="＋ Számla hozzáadása", command=self.add_invoice).pack(side="right", padx=8)
        self.invoice_panel = ttk.Frame(invoices)
        self.invoice_panel.pack(fill="x")

        summary = ttk.Labelframe(content, text="Kísérőlevél összesítése", padding=12)
        summary.pack(fill="x", pady=(0, 10))
        ttk.Label(summary, textvariable=self.period_text, style="Total.TLabel", padding=8).pack(fill="x")
        grid = ttk.Frame(summary)
        grid.pack(fill="x", pady=(6, 0))
        self.summary = self.cost_grid(grid)
        ttk.Label(content, textvariable=self.preview_name, wraplength=650).pack(fill="x", pady=4)
        actions = ttk.Frame(content)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Elvetés", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="Módosítások mentése" if self.editing else "Kísérőlevél létrehozása",
                   style="Accent.TButton", command=self.submit).pack(side="right")

    def add_invoice(self, invoice=None):
        costs = [str(value) for cost in invoice.costs.rows() for value in (cost.operating, cost.benefits)] if invoice else ["0"] * 8
        values = (
            invoice.number if invoice else "",
            display_date(invoice.start) if invoice else "",
            display_date(invoice.end) if invoice else "",
            *costs,
        )
        variables = [tk.StringVar(value=value) for value in values]
        for variable in variables:
            variable.trace_add("write", self.update_totals)
        self.invoices.append(variables)
        self.select_invoice(len(self.invoices) - 1)

    def remove_invoice(self):
        if len(self.invoices) <= 1:
            messagebox.showinfo("Postaszámlák", "Legalább egy számlának meg kell maradnia.", parent=self)
            return
        if not confirm_dialog(self, "Számla eltávolítása", "Eltávolítja a kijelölt számlát a kísérőlevélből?"):
            return
        self.invoices.pop(self.selected)
        self.select_invoice(min(self.selected, len(self.invoices) - 1))

    def select_invoice(self, index):
        if not 0 <= index < len(self.invoices):
            return
        self.selected = index
        for child in self.invoice_panel.winfo_children():
            child.destroy()
        values = self.invoices[index]
        details = ttk.Frame(self.invoice_panel)
        details.pack(fill="x", pady=(0, 8))
        for col, label in enumerate(("Számlaszám", "Időszak kezdete (ÉÉÉÉ.HH.NN.)", "Időszak vége (ÉÉÉÉ.HH.NN.)")):
            details.columnconfigure(col, weight=1)
            ttk.Label(details, text=label).grid(row=0, column=col, sticky="w", padx=4)
            ttk.Entry(details, textvariable=values[col], width=12).grid(row=1, column=col, sticky="ew", padx=4, pady=3)
        table = ttk.Frame(self.invoice_panel)
        table.pack(fill="x")
        self.live = self.cost_grid(table, values[3:])
        self.update_totals()

    def cost_grid(self, frame, inputs=None):
        result = []
        for col, heading in enumerate(HEADINGS):
            frame.columnconfigure(col, weight=3 if col == 0 else 2)
            ttk.Label(frame, text=heading, style="TableHead.TLabel", padding=4).grid(row=0, column=col, sticky="nsew")
        for row, label in enumerate(LABELS):
            style = "Total.TLabel" if row == 4 else "Cell.TLabel"
            ttk.Label(frame, text=label, style=style, padding=4).grid(row=row+1, column=0, sticky="nsew")
            for col in range(3):
                if inputs and row < 4 and col < 2:
                    ttk.Entry(frame, textvariable=inputs[row*2+col], width=9, justify="right").grid(
                        row=row+1, column=col+1, sticky="ew", padx=3)
                else:
                    value = tk.StringVar(value="—")
                    result.append((row, col, value))
                    ttk.Label(frame, textvariable=value, anchor="e", style=style, padding=4).grid(
                        row=row+1, column=col+1, sticky="nsew")
        return result

    @staticmethod
    def costs(values):
        amounts = [amount(variable.get()) for variable in values[3:]]
        return Costs(*(Cost(amounts[index], amounts[index+1]) for index in range(0, 8, 2)))

    def invoice_values(self, values, *, dates_only=False):
        return Invoice(values[0].get().strip(),
                       form_date(values[1].get(), "Időszak kezdete"),
                       form_date(values[2].get(), "Időszak vége"),
                       None if dates_only else self.costs(values))

    @staticmethod
    def show_totals(labels, numbers=None):
        for row, col, value in labels:
            value.set(forints(numbers[row][col]) if numbers is not None else "—")

    def update_totals(self, *_):
        self.choices.configure(values=[f"{index}. számla" + (f" · {values[0].get()}" if values[0].get() else "")
                                       for index, values in enumerate(self.invoices, 1)])
        self.choices.current(self.selected)
        dates = costs = None
        try:
            dates = period(tuple(self.invoice_values(values, dates_only=True) for values in self.invoices))
        except ValueError:
            pass
        try:
            self.show_totals(self.live, calculate(self.costs(self.invoices[self.selected]), allow_zero=True))
        except ValueError:
            self.show_totals(self.live)
        try:
            costs = total_costs(tuple(self.costs(values) for values in self.invoices))
            self.show_totals(self.summary, calculate(costs, allow_zero=True))
        except ValueError:
            self.show_totals(self.summary)
        self.period_text.set("Összesített időszak  " + (
            " – ".join(map(display_date, dates)) if dates else "—"))
        try:
            name = make_filename(*dates, costs) if dates and costs else "—"
        except ValueError:
            name = "—"
        self.preview_name.set("Fájlnév  " + name)

    def submit(self):
        try:
            data = {key: variable.get().strip() for key, variable in self.common.items()}
            data["dated"] = form_date(data["dated"], "Keltezés")
            data["sent"] = form_date(data["sent"], "Megküldés dátuma")
            invoices = []
            for index, values in enumerate(self.invoices, 1):
                try:
                    invoices.append(self.invoice_values(values))
                except ValueError as error:
                    self.select_invoice(index - 1)
                    raise ValueError(f"{index}. számla: {error}") from error
            record = Record(**data, invoices=tuple(invoices))
            record.to_letter()
            if self.editing and not confirm_dialog(
                self, "Mentés megerősítése", "Menti a kijelölt kísérőlevél módosításait?"
            ):
                return
            path = self.save_record(record)
        except (OSError, ValueError) as error:
            messagebox.showerror("A mentés sikertelen", str(error), parent=self)
            return
        self.saved_path = path
        self.destroy()
