# ====================================================================================================
# P05_gui_elements.py
# ----------------------------------------------------------------------------------------------------
# Full GUI for Just Eat Orders-to-Cash Reconciliation
# ----------------------------------------------------------------------------------------------------
# Features:
# - Defaults accounting period to previous month
# - On startup → scans JE folder for latest Order Level Detail and sets statement period
# - When accounting dates change → rescans and updates statement period automatically
# - Includes all 3 steps (DWH / PDFs / Reconciliation) + status + progress bar
# ====================================================================================================

import sys
from pathlib import Path

# Allow imports from parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True

# Shared imports
from processes.P00_set_packages import *  # includes datetime as dt, tkinter as tk, ttk, messagebox, etc.
from processes.P01_set_file_paths import root_folder, provider_output_folder

# ====================================================================================================
# CLASS DEFINITION
# ====================================================================================================

class JustEatReconciliationGUI(tk.Tk):
    """Main Tkinter window for the Just Eat reconciliation workflow."""

    def __init__(self):
        super().__init__()

        # ----------------------------------------------------------------------------------------------------
        # Default Accounting Period = Start and End of Previous Month
        # ----------------------------------------------------------------------------------------------------
        today = dt.date.today()
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - dt.timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        self.default_acc_start = last_month_start
        self.default_acc_end = last_month_end

        # ----------------------------------------------------------------------------------------------------
        # Window Setup
        # ----------------------------------------------------------------------------------------------------
        self.title("Just Eat Reconciliation Tool")
        self.geometry("720x800")
        self.resizable(False, False)
        self.configure(bg="#f4f4f4")

        # External callbacks
        self.combine_dwh_callback = None
        self.process_pdfs_callback = None
        self.run_reconciliation_callback = None

        # Build the interface
        self.build_ui()

        # Wire change listeners
        self.wire_accounting_change_events()

        # Initial sync on load
        self.after(100, self.sync_statement_period)

    # -----------------------------------------------------------------------------------------------
    # BUILD UI
    # -----------------------------------------------------------------------------------------------
    def build_ui(self):
        # --- Header
        tk.Label(
            self, text="🍴 Just Eat Reconciliation Tool",
            font=("Segoe UI", 16, "bold"), bg="#f4f4f4", fg="#FF6600"
        ).pack(pady=(15, 5))

        tk.Label(
            self, text=f"Root Folder: {root_folder}",
            font=("Segoe UI", 9), bg="#f4f4f4", fg="#444"
        ).pack(pady=(0, 10))

        # --- Instructions
        instr_text = (
            "How it works:\n"
            "1️⃣ Set your ACCOUNTING PERIOD (what you want in the books)\n"
            "2️⃣ Combine all DWH monthly exports first\n"
            "3️⃣ Set the STATEMENT PERIOD (what JE has issued, Mon→Sun weeks)\n"
            "4️⃣ Process PDFs for that period\n"
            "5️⃣ Run reconciliation — JE covers full weeks; DWH accrues remainder"
        )
        instr_frame = tk.Frame(self, bg="#fff3e6", bd=1, relief="solid")
        instr_frame.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(
            instr_frame, text=instr_text, justify="left",
            bg="#fff3e6", fg="#333", font=("Segoe UI", 10),
            anchor="w", padx=10, pady=10
        ).pack(fill="x")

        # -------------------------------------------------------------------------------------------
        # Accounting Period
        # -------------------------------------------------------------------------------------------
        frame_acc = ttk.LabelFrame(self, text="Accounting Period (What goes in the books)")
        frame_acc.pack(fill="x", padx=20, pady=10)
        acc_frame = tk.Frame(frame_acc)
        acc_frame.pack(pady=5, fill="x")

        ttk.Label(acc_frame, text="Accounting Start:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.acc_start_entry = DateEntry(acc_frame, width=12, background="#FF6600", foreground="white",
                                         borderwidth=2, date_pattern="yyyy-MM-dd")
        self.acc_start_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(acc_frame, text="Accounting End:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.acc_end_entry = DateEntry(acc_frame, width=12, background="#FF6600", foreground="white",
                                       borderwidth=2, date_pattern="yyyy-MM-dd")
        self.acc_end_entry.grid(row=0, column=3, padx=5, pady=5)

        self.acc_start_entry.set_date(self.default_acc_start)
        self.acc_end_entry.set_date(self.default_acc_end)

        tk.Label(
            frame_acc,
            text="Tip: Pick your reporting month here. JE covers up to latest statement; DWH accrues rest.",
            bg="#f4f4f4", anchor="w", wraplength=640, justify="left"
        ).pack(fill="x", padx=10, pady=(0, 5))

        # -------------------------------------------------------------------------------------------
        # Step 1 – Combine DWH
        # -------------------------------------------------------------------------------------------
        frame_dwh = ttk.LabelFrame(self, text="Step 1 – Combine DWH Data")
        frame_dwh.pack(fill="x", padx=20, pady=10)
        ttk.Label(frame_dwh, text="Combines all monthly 'JE DWH Output.csv' files.").pack(anchor="w", padx=10, pady=5)
        ttk.Button(frame_dwh, text="Combine DWH Data", command=self.combine_dwh).pack(pady=(0, 5))

        # -------------------------------------------------------------------------------------------
        # Step 2 – Process PDFs
        # -------------------------------------------------------------------------------------------
        frame_pdf = ttk.LabelFrame(self, text="Step 2 – Process PDFs (Statement Period)")
        frame_pdf.pack(fill="x", padx=20, pady=10)
        date_frame = tk.Frame(frame_pdf)
        date_frame.pack(pady=5)

        ttk.Label(date_frame, text="Statement Start:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.start_date_entry = DateEntry(date_frame, width=12, background="#FF6600", foreground="white",
                                          borderwidth=2, date_pattern="yyyy-MM-dd")
        self.start_date_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(date_frame, text="Statement End:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.end_date_entry = DateEntry(date_frame, width=12, background="#FF6600", foreground="white",
                                        borderwidth=2, date_pattern="yyyy-MM-dd")
        self.end_date_entry.grid(row=0, column=3, padx=5, pady=5)

        self.statement_end_label = tk.Label(
            frame_pdf, text="Detected Statement End: (auto-calculated)",
            bg="#f4f4f4", anchor="w", fg="#666", font=("Segoe UI", 9, "italic")
        )
        self.statement_end_label.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Button(frame_pdf, text="Process PDFs for Statement Period",
                   command=self.process_pdfs).pack(pady=(5, 5))

        # -------------------------------------------------------------------------------------------
        # Step 3 – Run Reconciliation
        # -------------------------------------------------------------------------------------------
        frame_recon = ttk.LabelFrame(self, text="Step 3 – Run Reconciliation")
        frame_recon.pack(fill="x", padx=20, pady=10)
        ttk.Label(
            frame_recon,
            text="Matches DWH data with JE statements. JE covers full weeks; DWH accrues remainder."
        ).pack(anchor="w", padx=10, pady=5)
        ttk.Button(frame_recon, text="Run Reconciliation",
                   command=self.run_reconciliation).pack(pady=(5, 8))

        # -------------------------------------------------------------------------------------------
        # Status + Progress
        # -------------------------------------------------------------------------------------------
        ttk.Separator(self).pack(fill="x", pady=(10, 5))
        self.status_label = ttk.Label(self, text="Status: Waiting for user input...", anchor="w")
        self.status_label.pack(fill="x", padx=20)
        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=20, pady=(5, 15))
        ttk.Button(self, text="Open Output Folder", command=self.open_output_folder).pack(pady=(0, 15))

    # -----------------------------------------------------------------------------------------------
    # ACCOUNTING → STATEMENT AUTO-SYNC
    # -----------------------------------------------------------------------------------------------
    def wire_accounting_change_events(self):
        for w in (self.acc_start_entry, self.acc_end_entry):
            w.bind("<<DateEntrySelected>>", self.on_accounting_changed, add="+")
            w.bind("<FocusOut>", self.on_accounting_changed, add="+")
            w.bind("<KeyRelease>", self.on_accounting_changed, add="+")

    def on_accounting_changed(self, *_):
        self.sync_statement_period()

    def sync_statement_period(self):
        """Run on load or accounting change: set statement period to last JE file."""
        try:
            acc_start_str, acc_end_str = self.get_accounting_period()
            if not acc_start_str or not acc_end_str:
                return

            acc_start = dt.datetime.strptime(acc_start_str, "%Y-%m-%d").date()
            acc_end = dt.datetime.strptime(acc_end_str, "%Y-%m-%d").date()

            stat_start_det, stat_end_det = self.detect_statement_coverage()
            acc_start_monday, acc_end_monday = self.to_monday(acc_start), self.to_monday(acc_end)

            if not stat_end_det:
                stat_start, stat_end = acc_start_monday, acc_end_monday
            else:
                stat_end = min(stat_end_det, acc_end_monday)
                stat_start = acc_start_monday

            self.start_date_entry.set_date(stat_start.strftime("%Y-%m-%d"))
            self.end_date_entry.set_date(stat_end.strftime("%Y-%m-%d"))

            stmt_auto_end = stat_end + dt.timedelta(days=6)
            self.statement_end_label.config(
                text=f"Detected Statement End: {stmt_auto_end.strftime('%Y-%m-%d')} (auto-calculated)"
            )

            # print(f"🔄 Statement period updated → {stat_start} → {stmt_auto_end}")

        except Exception as e:
            print(f"⚠ Error syncing statement period: {e}")

    # -----------------------------------------------------------------------------------------------
    # HELPERS
    # -----------------------------------------------------------------------------------------------
    def to_monday(self, d):
        return d - dt.timedelta(days=d.weekday())

    def detect_statement_coverage(self):
        """Return earliest and latest Monday coverage from JE Order Level Detail filenames."""
        try:
            pat = re.compile(
                r"(?P<sYY>\d{2})\.(?P<sMM>\d{2})\.(?P<sDD>\d{2})\s*-\s*"
                r"(?P<eYY>\d{2})\.(?P<eMM>\d{2})\.(?P<eDD>\d{2})\s*-\s*JE Order Level Detail\.csv$",
                re.I,
            )
            earliest_start, latest_end = None, None
            for p in provider_output_folder.glob("*JE Order Level Detail*.csv"):
                m = pat.search(p.name)
                if not m:
                    continue
                s = dt.date(int("20" + m["sYY"]), int(m["sMM"]), int(m["sDD"]))
                e = dt.date(int("20" + m["eYY"]), int(m["eMM"]), int(m["eDD"]))
                if earliest_start is None or s < earliest_start:
                    earliest_start = s
                if latest_end is None or e > latest_end:
                    latest_end = e
            return earliest_start, latest_end
        except Exception as e:
            print(f"⚠ Error detecting statement coverage: {e}")
            return None, None

    # -----------------------------------------------------------------------------------------------
    # BUTTON ACTIONS
    # -----------------------------------------------------------------------------------------------
    def get_accounting_period(self):
        return self.acc_start_entry.get(), self.acc_end_entry.get()

    def get_statement_period(self):
        return self.start_date_entry.get(), self.end_date_entry.get()

    def get_all_dates(self):
        acc_start, acc_end = self.get_accounting_period()
        stmt_start, stmt_end = self.get_statement_period()
        m = re.search(r"(\d{4}-\d{2}-\d{2})", self.statement_end_label.cget("text"))
        stmt_auto_end = m.group(1) if m else None
        return {
            "acc_start": acc_start,
            "acc_end": acc_end,
            "stmt_start": stmt_start,
            "stmt_end": stmt_end,
            "stmt_auto_end": stmt_auto_end,
        }

    def combine_dwh(self):
        if self.combine_dwh_callback:
            self.combine_dwh_callback()
        else:
            messagebox.showinfo("Info", "No function linked for Combine DWH button yet.")

    def process_pdfs(self):
        if self.process_pdfs_callback:
            s, e = self.start_date_entry.get(), self.end_date_entry.get()
            self.process_pdfs_callback(s, e)
        else:
            messagebox.showinfo("Info", "No function linked for Process PDFs button yet.")

    def run_reconciliation(self):
        if not self.run_reconciliation_callback:
            messagebox.showinfo("Info", "No function linked for Run Reconciliation button yet.")
            return
        dates = self.get_all_dates()
        try:
            self.run_reconciliation_callback(
                dates["acc_start"], dates["acc_end"],
                dates["stmt_start"], dates["stmt_end"], dates["stmt_auto_end"]
            )
        except TypeError:
            self.run_reconciliation_callback()

    def open_output_folder(self):
        messagebox.showinfo("Info", f"This will open:\n{provider_output_folder}")