# ====================================================================================================
# P05_gui_elements.py
# ----------------------------------------------------------------------------------------------------
# Full Tkinter GUI for the Just Eat Orders-to-Cash Reconciliation workflow.
#
# Purpose:
#   - Provide a single, user-friendly interface to run the 3-step reconciliation process:
#       Step 1 → Combine DWH Data
#       Step 2 → Process PDFs for the selected statement period
#       Step 3 → Run reconciliation between JE statements and DWH data
#
# Features:
#   • Automatically defaults accounting period to the previous month.
#   • Scans existing JE Order Level Detail CSVs on startup to detect the latest statement coverage.
#   • Auto-syncs statement period whenever accounting dates change.
#   • Displays live status updates, progress indicators, and completion messages.
#
# Usage:
#   from processes.P05_gui_elements import JustEatReconciliationGUI
#
# ----------------------------------------------------------------------------------------------------
# Author:         Gerry Pidgeon
# Created:        2025-11-05
# Project:        Just Eat Orders-to-Cash Reconciliation
# ====================================================================================================


# ====================================================================================================
# 1. SYSTEM IMPORTS
# ----------------------------------------------------------------------------------------------------
# Add parent directory to sys.path so this module can import other "processes" packages.
# ====================================================================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True  # Prevents __pycache__ folders from being created


# ====================================================================================================
# 2. PROJECT IMPORTS
# ----------------------------------------------------------------------------------------------------
# All dependencies come from P00_set_packages.py.
# NEVER import external packages directly in this file.
# ====================================================================================================
from processes.P00_set_packages import * # includes datetime as dt, tkinter as tk, ttk, messagebox, etc.
from processes.P01_set_file_paths import root_folder, provider_output_folder
from processes.P02_system_processes import detect_os # <-- ADDED IMPORT


# ====================================================================================================
# 3. MAIN GUI CLASS DEFINITION
# ----------------------------------------------------------------------------------------------------
# Provides the core Tkinter window and interactive workflow logic.
# ====================================================================================================

class JustEatReconciliationGUI(tk.Tk):
    """
    Main GUI window for the Just Eat Orders-to-Cash Reconciliation process.

    This guided interface enables users to:
        1️⃣ Combine DWH exports into a master dataset.
        2️⃣ Process all Just Eat statement PDFs for the chosen date range.
        3️⃣ Run reconciliation to match DWH and JE statement data.

    Attributes:
        default_acc_start (date): Default accounting start date (1st of previous month).
        default_acc_end (date): Default accounting end date (end of previous month).
        combine_dwh_callback (callable | None): Linked function for Step 1.
        process_pdfs_callback (callable | None): Linked function for Step 2.
        run_reconciliation_callback (callable | None): Linked function for Step 3.
    """

    # ------------------------------------------------------------------------------------------------
    # INITIALISATION
    # ------------------------------------------------------------------------------------------------
    def __init__(self):
        """Initialises the GUI window, default periods, and layout."""
        super().__init__()

        # Default accounting period = previous month (1st → last day)
        today = dt.date.today()
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - dt.timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        self.default_acc_start = last_month_start
        self.default_acc_end = last_month_end

        # Window configuration
        self.title("Just Eat Reconciliation Tool")
        self.geometry("720x800")
        self.resizable(False, False)
        self.configure(bg="#f4f4f4")

        # External callbacks (wired by M00_run_gui.py)
        self.combine_dwh_callback = None
        self.process_pdfs_callback = None
        self.run_reconciliation_callback = None

        # Build UI and event bindings
        self.build_ui()
        self.wire_accounting_change_events()

        # Initial sync of statement period after GUI load
        self.after(100, self.sync_statement_period)


    # ====================================================================================================
    # 4. BUILD USER INTERFACE
    # ----------------------------------------------------------------------------------------------------
    # Creates all visible UI components: headers, date pickers, buttons, progress indicators.
    # ====================================================================================================
    def build_ui(self):
        """Builds and lays out all GUI widgets, including headers, date selectors, and buttons."""
        # --- Header ---
        tk.Label(
            self, text="🍴 Just Eat Reconciliation Tool",
            font=("Segoe UI", 16, "bold"), bg="#f4f4f4", fg="#FF6600"
        ).pack(pady=(15, 5))

        tk.Label(
            self, text=f"Root Folder: {root_folder}",
            font=("Segoe UI", 9), bg="#f4f4f4", fg="#444"
        ).pack(pady=(0, 10))

        # --- Instructions ---
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
        # ACCOUNTING PERIOD SELECTION
        # -------------------------------------------------------------------------------------------
        frame_acc = ttk.LabelFrame(self, text="Accounting Period (What goes in the books)")
        frame_acc.pack(fill="x", padx=20, pady=10)
        acc_frame = tk.Frame(frame_acc)
        acc_frame.pack(pady=5, fill="x")

        ttk.Label(acc_frame, text="Accounting Start:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.acc_start_entry = DateEntry(
            acc_frame, width=12, background="#FF6600", foreground="white",
            borderwidth=2, date_pattern="yyyy-MM-dd"
        )
        self.acc_start_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(acc_frame, text="Accounting End:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.acc_end_entry = DateEntry(
            acc_frame, width=12, background="#FF6600", foreground="white",
            borderwidth=2, date_pattern="yyyy-MM-dd"
        )
        self.acc_end_entry.grid(row=0, column=3, padx=5, pady=5)

        self.acc_start_entry.set_date(self.default_acc_start)
        self.acc_end_entry.set_date(self.default_acc_end)

        tk.Label(
            frame_acc,
            text="Tip: Pick your reporting month here. JE covers up to latest statement; DWH accrues rest.",
            bg="#f4f4f4", anchor="w", wraplength=640, justify="left"
        ).pack(fill="x", padx=10, pady=(0, 5))

        # -------------------------------------------------------------------------------------------
        # STEP 1 — Combine DWH Data
        # -------------------------------------------------------------------------------------------
        frame_dwh = ttk.LabelFrame(self, text="Step 1 – Combine DWH Data")
        frame_dwh.pack(fill="x", padx=20, pady=10)
        ttk.Label(
            frame_dwh,
            text="Combines all monthly 'JE DWH Output.csv' files."
        ).pack(anchor="w", padx=10, pady=5)
        ttk.Button(frame_dwh, text="Combine DWH Data", command=self.combine_dwh).pack(pady=(0, 5))

        # -------------------------------------------------------------------------------------------
        # STEP 2 — Process PDFs
        # -------------------------------------------------------------------------------------------
        frame_pdf = ttk.LabelFrame(self, text="Step 2 – Process PDFs (Statement Period)")
        frame_pdf.pack(fill="x", padx=20, pady=10)
        date_frame = tk.Frame(frame_pdf)
        date_frame.pack(pady=5)

        ttk.Label(date_frame, text="Statement Start:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.start_date_entry = DateEntry(
            date_frame, width=12, background="#FF6600", foreground="white",
            borderwidth=2, date_pattern="yyyy-MM-dd"
        )
        self.start_date_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(date_frame, text="Statement End:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.end_date_entry = DateEntry(
            date_frame, width=12, background="#FF6600", foreground="white",
            borderwidth=2, date_pattern="yyyy-MM-dd"
        )
        self.end_date_entry.grid(row=0, column=3, padx=5, pady=5)

        self.statement_end_label = tk.Label(
            frame_pdf, text="Detected Statement End: (auto-calculated)",
            bg="#f4f4f4", anchor="w", fg="#666", font=("Segoe UI", 9, "italic")
        )
        self.statement_end_label.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Button(
            frame_pdf, text="Process PDFs for Statement Period",
            command=self.process_pdfs
        ).pack(pady=(5, 5))

        # -------------------------------------------------------------------------------------------
        # STEP 3 — Run Reconciliation
        # -------------------------------------------------------------------------------------------
        frame_recon = ttk.LabelFrame(self, text="Step 3 – Run Reconciliation")
        frame_recon.pack(fill="x", padx=20, pady=10)
        ttk.Label(
            frame_recon,
            text="Matches DWH data with JE statements. JE covers full weeks; DWH accrues remainder."
        ).pack(anchor="w", padx=10, pady=5)
        ttk.Button(frame_recon, text="Run Reconciliation", command=self.run_reconciliation).pack(pady=(5, 8))

        # -------------------------------------------------------------------------------------------
        # STATUS + PROGRESS BAR
        # -------------------------------------------------------------------------------------------
        ttk.Separator(self).pack(fill="x", pady=(10, 5))
        self.status_label = ttk.Label(self, text="Status: Waiting for user input...", anchor="w")
        self.status_label.pack(fill="x", padx=20)
        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=20, pady=(5, 15))
        ttk.Button(self, text="Open Output Folder", command=self.open_output_folder).pack(pady=(0, 15))


    # ====================================================================================================
    # 5. ACCOUNTING ↔ STATEMENT AUTO-SYNC
    # ----------------------------------------------------------------------------------------------------
    # Keeps statement period aligned automatically with accounting date selection.
    # ====================================================================================================

    def wire_accounting_change_events(self):
        """Attach bindings to trigger re-sync when accounting dates are modified."""
        for w in (self.acc_start_entry, self.acc_end_entry):
            w.bind("<<DateEntrySelected>>", self.on_accounting_changed, add="+")
            w.bind("<FocusOut>", self.on_accounting_changed, add="+")
            w.bind("<KeyRelease>", self.on_accounting_changed, add="+")

    def on_accounting_changed(self, *_):
        """Triggered whenever the accounting period is updated."""
        self.sync_statement_period()

    def sync_statement_period(self):
        """Automatically detect and align the statement period based on accounting dates."""
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

        except Exception as e:
            print(f"⚠ Error syncing statement period: {e}")


    # ====================================================================================================
    # 6. HELPER METHODS
    # ----------------------------------------------------------------------------------------------------
    # Utility functions for date conversion, detection, and input retrieval.
    # ====================================================================================================
    def to_monday(self, d):
        """Return the Monday of the given date's week."""
        return d - dt.timedelta(days=d.weekday())

    def detect_statement_coverage(self):
        """Detect earliest and latest JE Order Level Detail CSV statement coverage."""
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


    # ====================================================================================================
    # 7. BUTTON ACTIONS
    # ----------------------------------------------------------------------------------------------------
    # Triggered when GUI buttons are pressed (linked via M00_run_gui.py callbacks).
    # ====================================================================================================

    def get_accounting_period(self):
        """Return a tuple (start, end) for the selected accounting period."""
        return self.acc_start_entry.get(), self.acc_end_entry.get()

    def get_statement_period(self):
        """Return a tuple (start, end) for the selected statement period."""
        return self.start_date_entry.get(), self.end_date_entry.get()

    def get_all_dates(self):
        """Return all relevant date values as a dictionary."""
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
        """Trigger Step 1 – Combine DWH Data."""
        if self.combine_dwh_callback:
            self.combine_dwh_callback()
        else:
            messagebox.showinfo("Info", "No function linked for Combine DWH button yet.")

    def process_pdfs(self):
        """Trigger Step 2 – Process PDFs."""
        if self.process_pdfs_callback:
            s, e = self.start_date_entry.get(), self.end_date_entry.get()
            self.process_pdfs_callback(s, e)
        else:
            messagebox.showinfo("Info", "No function linked for Process PDFs button yet.")

    def run_reconciliation(self):
        """Trigger Step 3 – Run Reconciliation."""
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

    # --- MODIFIED SECTION ---

    def open_folder_in_explorer(self, path_to_open: Path):
        """Cross-platform function to open a folder in the native file explorer."""
        try:
            os_type = detect_os()
            # Use os.startfile on Windows
            if os_type == "Windows":
                os.startfile(path_to_open)
            # Use 'open' command on macOS
            elif os_type == "macOS":
                subprocess.run(["open", path_to_open], check=True)
            # Use 'xdg-open' on Linux/WSL
            elif os_type in ["Linux", "Windows (WSL)"]:
                subprocess.run(["xdg-open", path_to_open], check=True)
            else:
                messagebox.showerror("Error", f"Unsupported OS: {os_type}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def open_output_folder(self):
        """Opens the provider output folder in the native file explorer."""
        self.open_folder_in_explorer(provider_output_folder)