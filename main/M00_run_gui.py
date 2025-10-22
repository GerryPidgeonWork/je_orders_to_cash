# ====================================================================================================
# M00_run_gui.py
# ----------------------------------------------------------------------------------------------------
# Step 0 – Launch the Just Eat Reconciliation GUI
# ----------------------------------------------------------------------------------------------------
# Purpose:
# - Provides a user interface to run all Just Eat Orders-to-Cash reconciliation steps.
# - Connects GUI buttons to each processing module:
#       Step 1 → Combine DWH Data (M01_combined_dwh.py)
#       Step 2 → Process PDFs for selected date range (M02_process_pdfs.py)
#       Step 3 → Run Reconciliation (M03_run_reconciliation.py)
# - Handles background threading, status updates, and error messages.
# ----------------------------------------------------------------------------------------------------
# Inputs:
#   - User-selected start and end dates via GUI
#   - Data folders and paths defined in P01_set_file_paths.py
# Outputs:
#   - Status messages, progress bar updates, and CSV files from each step
# ----------------------------------------------------------------------------------------------------
# Notes:
#   - Designed as the main entry point for the full Orders-to-Cash workflow.
#   - Each step runs in its own background thread to keep the GUI responsive.
#   - Handles friendly error display for user-facing feedback.
# ====================================================================================================

# ====================================================================================================
# Import Libraries that are required to adjust sys path
# ====================================================================================================
import sys                      # Provides access to system-specific parameters and functions
from pathlib import Path        # Offers an object-oriented interface for filesystem paths

# Adjust sys.path so we can import modules from the parent folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True  # Prevents _pycache_ creation

# Import Project Libraries (global imports handled via P00_set_packages)
from processes.P00_set_packages import *

# ====================================================================================================
# Import Project Modules
# ====================================================================================================
from processes.P05_gui_elements import JustEatReconciliationGUI
from main.M01_combined_dwh import combine_je_dwh_files
from main.M02_process_pdfs import run_je_parser
from main.M03_run_reconciliation import run_reconciliation
from processes.P01_set_file_paths import (
    provider_dwh_folder,
    provider_output_folder,
    provider_pdf_unprocessed_folder,
)

# ====================================================================================================
# Step 1 – Combine DWH Handler
# ====================================================================================================

def run_combine_dwh(gui: JustEatReconciliationGUI):
    """Executes Step 1 (Combine DWH) with live status updates in GUI."""
    def task():
        try:
            gui.status_label.config(text="🔄 Combining DWH files...")
            gui.progress.start(10)

            output_path = combine_je_dwh_files(provider_dwh_folder, provider_output_folder)

            gui.progress.stop()
            if output_path:
                gui.status_label.config(text=f"✅ DWH Combined Successfully: {output_path.name}")
            else:
                gui.status_label.config(text="⚠ No valid DWH files found.")
        except Exception as e:
            gui.progress.stop()
            gui.status_label.config(text="❌ Error during DWH combination")
            tb = traceback.format_exc()
            print(tb)
            messagebox.showerror("Error", f"An error occurred:\n{e}\n\nFull details:\n{tb}")

    threading.Thread(target=task, daemon=True).start()

# ====================================================================================================
# Step 2 – Process PDFs Handler
# ====================================================================================================

def run_process_pdfs(gui: JustEatReconciliationGUI, start_date: str, end_date: str):
    """Executes Step 2 (Process PDFs) within the selected GUI date range."""
    def task():
        try:
            gui.status_label.config(text=f"🔄 Processing PDFs ({start_date} → {end_date})...")
            gui.progress.start(10)

            output_path = run_je_parser(
                provider_pdf_unprocessed_folder,
                provider_output_folder,
                start_date=start_date,
                end_date=end_date
            )

            gui.progress.stop()
            if isinstance(output_path, str) and output_path.startswith("⚠"):
                gui.status_label.config(text=output_path)
                messagebox.showwarning(
                    "No Matching PDFs Found",
                    "No Just Eat Statement PDFs were found for the selected date range.\n\n"
                    "Please choose a date range that matches the available statement periods."
                )
            elif output_path:
                gui.status_label.config(text=f"✅ PDF Extraction Complete: {Path(output_path).name}")
                messagebox.showinfo(
                    "PDF Extraction Complete",
                    f"The selected PDFs have been processed successfully.\n\nOutput file:\n{Path(output_path).name}"
                )
            else:
                gui.status_label.config(text="⚠ No matching PDFs found for this period.")
                messagebox.showwarning(
                    "No PDFs Found",
                    "No statement PDFs were processed.\n\nPlease verify the date range or check if new files exist in the folder."
                )
        except Exception as e:
            gui.progress.stop()
            gui.status_label.config(text="❌ Error during PDF extraction")
            tb = traceback.format_exc()
            print(tb)
            messagebox.showerror("Error", f"An error occurred:\n{e}\n\nFull details:\n{tb}")

    threading.Thread(target=task, daemon=True).start()

# ====================================================================================================
# Step 3 – Run Reconciliation Handler
# ====================================================================================================

def run_reconciliation_gui(gui: JustEatReconciliationGUI, start_date: str, end_date: str):
    """Executes Step 3 (Run Reconciliation) using selected GUI date range."""
    def task():
        try:
            gui.status_label.config(text=f"🔄 Running reconciliation ({start_date} → {end_date})...")
            gui.progress.start(10)

            output_path = run_reconciliation(
                provider_output_folder,
                start_date=start_date,
                end_date=end_date
            )

            gui.progress.stop()
            if isinstance(output_path, str) and output_path.startswith("⚠"):
                gui.status_label.config(text=output_path)
                messagebox.showwarning(
                    "No Matching Statement Found",
                    "No Just Eat statement CSV was found that matches the selected date range.\n\n"
                    "Please run Step 2 (Process PDFs) first or choose another period."
                )
            elif output_path:
                gui.status_label.config(text=f"✅ Reconciliation Complete: {Path(output_path).name}")
                messagebox.showinfo(
                    "Reconciliation Complete",
                    f"Reconciliation finished successfully.\n\nOutput file:\n{Path(output_path).name}"
                )
            else:
                gui.status_label.config(text="⚠ No reconciliation results produced.")
                messagebox.showwarning(
                    "No Reconciliation Results",
                    "No reconciliation results were produced.\n\n"
                    "Ensure the selected period aligns with your available statement data."
                )
        except Exception as e:
            gui.progress.stop()
            gui.status_label.config(text="❌ Error during reconciliation")
            tb = traceback.format_exc()
            print(tb)
            messagebox.showerror(
                "Error During Reconciliation",
                "An unexpected error occurred while running reconciliation.\n\n"
                "Please verify your inputs or contact support if this persists."
            )

    threading.Thread(target=task, daemon=True).start()

# ====================================================================================================
# Launch GUI and Link Button Callbacks
# ====================================================================================================

# ====================================================================================================
# Launch GUI and Link Button Callbacks
# ====================================================================================================

if __name__ == "__main__":
    app = JustEatReconciliationGUI()

    # Step 1: Combine DWH Data
    app.combine_dwh_callback = lambda: run_combine_dwh(app)

    # Step 2: Process PDFs for Period
    app.process_pdfs_callback = lambda s, e: run_process_pdfs(app, s, e)

    # Step 3: Run Reconciliation
    app.run_reconciliation_callback = lambda: run_reconciliation_gui(
        app, app.start_date_entry.get(), app.end_date_entry.get()
    )

    app.mainloop()
