"""
Vinod Medical Store - Medicine Stock & Expiry Alert Software
Python + SQL (SQLite) + Tkinter (koi extra install nahi chahiye)

Chalane ke liye:  python vinod_medical_store.py
Date format:      DD-MM-YYYY  (jaise 25-12-2026)
"""

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date

DB_FILE = "vinod_medical_store.db"
ALERT_DAYS = 60            # 2 mahine pehle alert
DATE_FMT = "%d-%m-%Y"      # screen par dikhne wala format
RECHECK_MS = 60 * 60 * 1000  # app khula ho to har 1 ghante mein dobara check


# ---------------------------------------------------------------- DATABASE
def get_conn():
    return sqlite3.connect(DB_FILE)


def init_db():
    with get_conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS medicines (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                mfd_date    TEXT    NOT NULL,   -- YYYY-MM-DD
                expiry_date TEXT    NOT NULL,   -- YYYY-MM-DD
                rate        REAL    NOT NULL,
                quantity    INTEGER NOT NULL,
                size        TEXT
            )
            """
        )


def add_medicine(name, mfd, expiry, rate, qty, size):
    with get_conn() as con:
        con.execute(
            "INSERT INTO medicines (name, mfd_date, expiry_date, rate, quantity, size) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, mfd, expiry, rate, qty, size),
        )


def update_medicine(med_id, name, mfd, expiry, rate, qty, size):
    with get_conn() as con:
        con.execute(
            "UPDATE medicines SET name=?, mfd_date=?, expiry_date=?, rate=?, "
            "quantity=?, size=? WHERE id=?",
            (name, mfd, expiry, rate, qty, size, med_id),
        )


def delete_medicine(med_id):
    with get_conn() as con:
        con.execute("DELETE FROM medicines WHERE id=?", (med_id,))


def search_medicines(text=""):
    with get_conn() as con:
        return con.execute(
            "SELECT id, name, mfd_date, expiry_date, rate, quantity, size "
            "FROM medicines WHERE name LIKE ? ORDER BY expiry_date",
            (f"%{text}%",),
        ).fetchall()


def get_expiring(days=ALERT_DAYS):
    """Wo dawai jo expire ho chuki hain ya agle `days` din mein expire hongi."""
    with get_conn() as con:
        return con.execute(
            "SELECT id, name, expiry_date, quantity, "
            "CAST(julianday(expiry_date) - julianday('now', 'localtime') AS INTEGER) "
            "FROM medicines "
            "WHERE expiry_date <= date('now', 'localtime', ?) "
            "ORDER BY expiry_date",
            (f"+{days} days",),
        ).fetchall()


# ----------------------------------------------------------------- HELPERS
def to_iso(text):
    """DD-MM-YYYY -> YYYY-MM-DD (galat date par ValueError)."""
    return datetime.strptime(text.strip(), DATE_FMT).strftime("%Y-%m-%d")


def to_display(iso_text):
    return datetime.strptime(iso_text, "%Y-%m-%d").strftime(DATE_FMT)


def status_of(expiry_iso):
    days_left = (datetime.strptime(expiry_iso, "%Y-%m-%d").date() - date.today()).days
    if days_left < 0:
        return "EXPIRED", "expired"
    if days_left <= ALERT_DAYS:
        return f"{days_left} din bache", "soon"
    return "OK", "ok"


# --------------------------------------------------------------------- GUI
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Vinod Medical Store")
        self.geometry("980x600")
        self.selected_id = None
        self.vars = {}
        self._build_ui()
        self.refresh()
        self.after(500, lambda: self.show_alert(auto=True))
        self.after(RECHECK_MS, self._recheck)

    def _build_ui(self):
        tk.Label(self, text="VINOD MEDICAL STORE", font=("Arial", 20, "bold"),
                 fg="#0b6e4f").pack(pady=(10, 2))

        self.banner = tk.Label(self, text="", font=("Arial", 11, "bold"),
                               fg="white", bg="#0b6e4f", pady=4)
        self.banner.pack(fill="x", padx=10, pady=4)

        form = ttk.LabelFrame(self, text="Dawai ki details")
        form.pack(fill="x", padx=10, pady=6)
        fields = [
            ("name", "Dawai ka naam"),
            ("mfd", "MFD (DD-MM-YYYY)"),
            ("expiry", "Expiry (DD-MM-YYYY)"),
            ("rate", "Rate (Rs.)"),
            ("qty", "Quantity"),
            ("size", "Size (jaise 10 tablets / 100 ml)"),
        ]
        for i, (key, label) in enumerate(fields):
            r, c = divmod(i, 3)
            ttk.Label(form, text=label).grid(row=r * 2, column=c, sticky="w", padx=8, pady=(6, 0))
            self.vars[key] = tk.StringVar()
            ttk.Entry(form, textvariable=self.vars[key], width=30).grid(
                row=r * 2 + 1, column=c, padx=8, pady=(0, 6))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10)
        for text, cmd in [("Add", self.on_add), ("Update", self.on_update),
                          ("Delete", self.on_delete), ("Clear", self.clear_form),
                          ("Expiry Alert dekho", lambda: self.show_alert(auto=False))]:
            ttk.Button(btns, text=text, command=cmd).pack(side="left", padx=4, pady=6)

        ttk.Label(btns, text="Search:").pack(side="left", padx=(20, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(btns, textvariable=self.search_var, width=25).pack(side="left")

        cols = ("name", "mfd", "expiry", "rate", "qty", "size", "status")
        heads = ("Dawai", "MFD", "Expiry", "Rate", "Qty", "Size", "Status")
        widths = (220, 100, 100, 80, 70, 150, 120)
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="center" if c != "name" else "w")
        self.tree.tag_configure("expired", background="#f8b4b4")
        self.tree.tag_configure("soon", background="#fde9a8")
        self.tree.pack(fill="both", expand=True, padx=10, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    # ---- form helpers
    def read_form(self):
        name = self.vars["name"].get().strip()
        if not name:
            raise ValueError("Dawai ka naam likhiye.")
        mfd = to_iso(self.vars["mfd"].get())
        expiry = to_iso(self.vars["expiry"].get())
        if expiry <= mfd:
            raise ValueError("Expiry date, MFD ke baad honi chahiye.")
        rate = float(self.vars["rate"].get())
        qty = int(self.vars["qty"].get())
        if rate < 0 or qty < 0:
            raise ValueError("Rate aur quantity negative nahi ho sakte.")
        return name, mfd, expiry, rate, qty, self.vars["size"].get().strip()

    def clear_form(self):
        self.selected_id = None
        for v in self.vars.values():
            v.set("")
        self.tree.selection_remove(self.tree.selection())

    # ---- button actions
    def on_add(self):
        try:
            add_medicine(*self.read_form())
        except ValueError as e:
            return messagebox.showerror("Galti", f"Details check kijiye.\n{e}")
        self.clear_form()
        self.refresh()

    def on_update(self):
        if self.selected_id is None:
            return messagebox.showinfo("Update", "Pehle list mein se dawai chuniye.")
        try:
            update_medicine(self.selected_id, *self.read_form())
        except ValueError as e:
            return messagebox.showerror("Galti", f"Details check kijiye.\n{e}")
        self.clear_form()
        self.refresh()

    def on_delete(self):
        if self.selected_id is None:
            return messagebox.showinfo("Delete", "Pehle list mein se dawai chuniye.")
        if messagebox.askyesno("Delete", "Kya aap sach mein ye dawai hatana chahte hain?"):
            delete_medicine(self.selected_id)
            self.clear_form()
            self.refresh()

    def on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        v = self.tree.item(sel[0], "values")
        for key, val in zip(["name", "mfd", "expiry", "rate", "qty", "size"], v[:6]):
            self.vars[key].set(val)

    # ---- table + alerts
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for mid, name, mfd, exp, rate, qty, size in search_medicines(self.search_var.get()):
            label, tag = status_of(exp)
            self.tree.insert("", "end", iid=str(mid), tags=(tag,),
                             values=(name, to_display(mfd), to_display(exp),
                                     f"{rate:.2f}", qty, size or "", label))
        self.update_banner()

    def update_banner(self):
        rows = get_expiring()
        if rows:
            self.banner.config(bg="#c0392b",
                               text=f"CHETAVNI: {len(rows)} dawai expire ho chuki hain ya 2 mahine mein expire hongi!")
        else:
            self.banner.config(bg="#0b6e4f", text="Sab theek hai - 2 mahine mein koi dawai expire nahi ho rahi.")

    def show_alert(self, auto=False):
        rows = get_expiring()
        if not rows:
            if not auto:
                messagebox.showinfo("Expiry Alert", "2 mahine mein koi dawai expire nahi ho rahi.")
            return
        lines = []
        for _id, name, exp, qty, days in rows:
            when = "EXPIRE HO CHUKI" if days < 0 else f"{days} din mein expire"
            lines.append(f"- {name} | Expiry: {to_display(exp)} | Qty: {qty} | {when}")
        messagebox.showwarning("Expiry Alert", "Ye dawaiyan dhyan maangti hain:\n\n" + "\n".join(lines))

    def _recheck(self):
        self.update_banner()
        self.after(RECHECK_MS, self._recheck)


if __name__ == "__main__":
    init_db()
    App().mainloop()
