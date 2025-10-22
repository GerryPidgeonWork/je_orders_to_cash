# ====================================================================================================
# P05_gui_elements.py
# ====================================================================================================

# ====================================================================================================
# Import Libraries that are required to adjust sys path
# ====================================================================================================
import sys                      # Provides access to system-specific parameters and functions
from pathlib import Path        # Offers an object-oriented interface for filesystem paths

# Adjust sys.path so we can import modules from the parent folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True  # Prevents _pycache_ creation

# Import Project Libraries
from processes.P00_set_packages import *

# ====================================================================================================
# Import shared functions and file paths from other folders
# ====================================================================================================



# ----------------------------------------------------------------------------------------------------
# Import Project Libraries
# ----------------------------------------------------------------------------------------------------
from processes.P01_set_file_paths import root_folder, provider_dwh_folder, provider_pdf_unprocessed_folder, provider_output_folder

# ====================================================================================================
# GUI CLASS DEFINITION
# ====================================================================================================
class JustEatReconciliationGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Just Eat Reconciliation Tool")
        self.geometry("720x620")
        self.resizable(False, False)
        self.configure(bg="#f4f4f4")

        # External callbacks (set from M00_run_gui.py)
        self.combine_dwh_callback = None
        self.process_pdfs_callback = None
        self.run_reconciliation_callback = None

        # Build the UI layout
        self._build_ui()

    # -----------------------------------------------------------------------------------------------
    # Build user interface
    # -----------------------------------------------------------------------------------------------
    def _build_ui(self):
        # Title
        tk.Label(
            self,
            text="🍴 Just Eat Reconciliation Tool",
            font=("Segoe UI", 16, "bold"),
            bg="#f4f4f4",
            fg="#FF6600"
        ).pack(pady=(15, 5))

        # Root Folder
        tk.Label(
            self,
            text=f"Root Folder: {root_folder}",
            font=("Segoe UI", 9),
            bg="#f4f4f4",
            fg="#444"
        ).pack(pady=(0, 10))

        # Instructions box
        instr_text = (
            "How it works:\n"
            "1️⃣  Combine all DWH monthly exports first\n"
            "2️⃣  Choose the start and end dates for your statement period\n"
            "3️⃣  Process PDFs within that range\n"
            "4️⃣  Run reconciliation to find missing or unmatched orders"
        )

        instr_frame = tk.Frame(self, bg="#fff3e6", bd=1, relief="solid")
        instr_frame.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(
            instr_frame,
            text=instr_text,
            justify="left",
            bg="#fff3e6",
            fg="#333",
            font=("Segoe UI", 10),
            anchor="w",
            padx=10,
            pady=10
        ).pack(fill="x")

        # -------------------------------------------------------------------------------------------
        # Step 1 – Combine DWH Data
        # -------------------------------------------------------------------------------------------
        frame_dwh = ttk.LabelFrame(self, text="Step 1 – Combine DWH Data")
        frame_dwh.pack(fill="x", padx=20, pady=10)

        ttk.Label(
            frame_dwh,
            text="Combines all monthly 'JE DWH Output.csv' files in your DWH folder."
        ).pack(anchor="w", padx=10, pady=5)

        ttk.Button(
            frame_dwh,
            text="Combine DWH Data",
            command=self._combine_dwh
        ).pack(pady=(0, 5))

        tk.Label(
            frame_dwh,
            text=f"📁 Source: {provider_dwh_folder.relative_to(root_folder)}",
            bg="#f4f4f4",
            anchor="w"
        ).pack(fill="x", padx=10)

        tk.Label(
            frame_dwh,
            text=f"💾 Output: {provider_output_folder.name}\\DWH_Combined.csv",
            bg="#f4f4f4",
            anchor="w"
        ).pack(fill="x", padx=10, pady=(0, 5))

        # -------------------------------------------------------------------------------------------
        # Step 2 – Process PDFs for Selected Period
        # (currently inactive but designed for later linking)
        # -------------------------------------------------------------------------------------------
        frame_pdf = ttk.LabelFrame(self, text="Step 2 – Process PDFs for Selected Period")
        frame_pdf.pack(fill="x", padx=20, pady=10)

        date_frame = tk.Frame(frame_pdf)
        date_frame.pack(pady=5)

        ttk.Label(date_frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5)
        self.start_date_entry = DateEntry(
            date_frame,
            width=12,
            background="#FF6600",
            foreground="white",
            borderwidth=2,
            date_pattern="yyyy-MM-dd"
        )
        self.start_date_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(date_frame, text="End Date:").grid(row=0, column=2, padx=5, pady=5)
        self.end_date_entry = DateEntry(
            date_frame,
            width=12,
            background="#FF6600",
            foreground="white",
            borderwidth=2,
            date_pattern="yyyy-MM-dd"
        )
        self.end_date_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(
            frame_pdf,
            text="Process PDFs for Period",
            command=self._process_pdfs
        ).pack(pady=(5, 5))

        tk.Label(
            frame_pdf,
            text=f"📁 Source: {provider_pdf_unprocessed_folder.relative_to(root_folder)}",
            bg="#f4f4f4",
            anchor="w"
        ).pack(fill="x", padx=10)

        tk.Label(
            frame_pdf,
            text=f"💾 Output: {provider_output_folder.name}\\JE_Statement.csv",
            bg="#f4f4f4",
            anchor="w"
        ).pack(fill="x", padx=10, pady=(0, 5))

                # -------------------------------------------------------------------------------------------
        # Step 3 – Run Reconciliation
        # -------------------------------------------------------------------------------------------
        frame_recon = ttk.LabelFrame(self, text="Step 3 – Run Reconciliation")
        frame_recon.pack(fill="x", padx=20, pady=10)

        ttk.Label(
            frame_recon,
            text="Matches the combined DWH data with your processed JE statement to find missing or unmatched orders."
        ).pack(anchor="w", padx=10, pady=5)

        # Run button
        ttk.Button(
            frame_recon,
            text="Run Reconciliation",
            command=self._run_reconciliation
        ).pack(pady=(5, 8))

        # Output location info
        tk.Label(
            frame_recon,
            text=f"💾 Output: {provider_output_folder.name}\\<date-range> - JE Reconciliation Results.csv",
            bg="#f4f4f4",
            anchor="w"
        ).pack(fill="x", padx=10, pady=(0, 5))

        # -------------------------------------------------------------------------------------------
        # Status + Progress Bar
        # -------------------------------------------------------------------------------------------
        ttk.Separator(self).pack(fill="x", pady=(10, 5))

        self.status_label = ttk.Label(self, text="Status: Waiting for user input...", anchor="w")
        self.status_label.pack(fill="x", padx=20)

        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=20, pady=(5, 15))

        # -------------------------------------------------------------------------------------------
        # Open Output Folder Button
        # -------------------------------------------------------------------------------------------
        ttk.Button(
            self,
            text="Open Output Folder",
            command=self._open_output_folder
        ).pack(pady=(0, 15))

    # -----------------------------------------------------------------------------------------------
    # Button event methods (emit callbacks to main/M00_run_gui.py)
    # -----------------------------------------------------------------------------------------------
    def _combine_dwh(self):
        if self.combine_dwh_callback:
            self.combine_dwh_callback()
        else:
            messagebox.showinfo("Info", "No function linked for Combine DWH button yet.")

    def _process_pdfs(self):
        if self.process_pdfs_callback:
            start, end = self.start_date_entry.get(), self.end_date_entry.get()
            self.process_pdfs_callback(start, end)
        else:
            messagebox.showinfo("Info", "No function linked for Process PDFs button yet.")

    def _run_reconciliation(self):
        if self.run_reconciliation_callback:
            self.run_reconciliation_callback()
        else:
            messagebox.showinfo("Info", "No function linked for Run Reconciliation button yet.")

    def _open_output_folder(self):
        messagebox.showinfo("Info", f"This will open:\n{provider_output_folder}")
