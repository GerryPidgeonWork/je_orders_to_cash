# ====================================================================================================
# M00_run_gui.py
# ----------------------------------------------------------------------------------------------------
# Step 0 – Launch the Just Eat Reconciliation GUI
# ----------------------------------------------------------------------------------------------------
# Purpose:
# - Provides a user interface to run all Just Eat Orders-to-Cash reconciliation steps.
# - Connects GUI buttons to each processing module:
#       Step 1 → Combine DWH Data (M01_combined_dwh.py)
#       Step 2 → Process PDFs for selected date range (M02_process_mp_data.py)
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
# ----------------------------------------------------------------------------------------------------
# Author:         Gerry Pidgeon
# Created:        2025-11-05
# Project:        Just Eat Orders-to-Cash Reconciliation
# ====================================================================================================


# ====================================================================================================
# 1. SYSTEM IMPORTS
# ----------------------------------------------------------------------------------------------------
# Lightweight built-in modules for path handling and interpreter setup.
# ====================================================================================================
import sys              # Provides access to system-specific parameters and functions
from pathlib import Path      # Offers an object-oriented interface for filesystem paths

# ----------------------------------------------------------------------------------------------------
# Ensure this module can import other "processes" packages by adding its parent folder to sys.path.
# Also disable __pycache__ creation for cleaner deployments (especially when bundled with PyInstaller).
# ----------------------------------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True  # Prevents _pycache_ creation


# ====================================================================================================
# 2. PROJECT IMPORTS
# ----------------------------------------------------------------------------------------------------
# Import all dependencies, GUI elements, and business logic modules.
# ====================================================================================================
# --- Central Package Hub ---
from processes.P00_set_packages import * # Includes tkinter, ttk, messagebox, threading, etc.

# --- GUI Class ---
from processes.P05_gui_elements import JustEatReconciliationGUI

# --- Business Logic Modules (The "Steps") ---
from main.M01_combined_dwh import combine_je_dwh_files
from main.M02_process_mp_data import run_je_parser
from main.M03_run_reconciliation import run_reconciliation

# --- Configuration & Paths ---
from processes.P01_set_file_paths import (
    provider_dwh_folder,
    provider_output_folder,
    provider_pdf_unprocessed_folder,
)


# ====================================================================================================
# 3. THREADED HANDLERS (GUI BUTTON ACTIONS)
# ----------------------------------------------------------------------------------------------------
# These functions wrap the core business logic in background threads.
# This is CRITICAL to prevent the GUI from freezing during long operations.
# ====================================================================================================

def run_combine_dwh(gui: JustEatReconciliationGUI):
    """
    Wraps the DWH combination (Step 1) in a thread to run in the background.
    Updates the GUI with status, progress, and error messages.

    Args:
        gui (JustEatReconciliationGUI): The main GUI application instance.
    """
    def task():
        try:
            # 1. Update GUI to "running" state
            gui.status_label.config(text="🔄 Combining DWH files...")
            gui.progress.start(10)

            # 2. Run the actual business logic from M01
            output_path = combine_je_dwh_files(provider_dwh_folder, provider_output_folder)

            # 3. Stop progress bar and update GUI on success
            gui.progress.stop()
            if output_path:
                gui.status_label.config(text=f"✅ DWH Combined Successfully: {output_path.name}")
            else:
                gui.status_label.config(text="⚠ No valid DWH files found.")
        
        except Exception as e:
            # 4. On failure, stop progress and show a detailed error
            gui.progress.stop()
            gui.status_label.config(text="❌ Error during DWH combination")
            tb = traceback.format_exc() # Get full traceback for debugging
            print(tb)
            messagebox.showerror("Error", f"An error occurred:\n{e}\n\nFull details:\n{tb}")

    # Run the task in a daemon thread so it doesn't block the GUI
    threading.Thread(target=task, daemon=True).start()


def run_process_pdfs(gui: JustEatReconciliationGUI, start_date: str, end_date: str):
    """
    Wraps the PDF parsing (Step 2) in a thread to run in the background.
    Passes the selected date range from the GUI to the parser.

    Args:
        gui (JustEatReconciliationGUI): The main GUI application instance.
        start_date (str): The start date (YYYY-MM-DD) from the GUI.
        end_date (str): The end date (YYYY-MM-DD) from the GUI.
    """
    def task():
        try:
            # 1. Update GUI to "running" state
            gui.status_label.config(text=f"🔄 Processing PDFs ({start_date} → {end_date})...")
            gui.progress.start(10)

            # 2. Run the actual business logic from M02
            output_path = run_je_parser(
                provider_pdf_unprocessed_folder,
                provider_output_folder,
                start_date=start_date,
                end_date=end_date
            )

            # 3. Stop progress bar and handle success/warnings
            gui.progress.stop()
            
            # Check for a "soft warning" (e.g., "No files found") from the parser
            if isinstance(output_path, str) and output_path.startswith("⚠"):
                gui.status_label.config(text=output_path)
                messagebox.showwarning(
                    "No Matching PDFs Found",
                    "No Just Eat Statement PDFs were found for the selected date range.\n\n"
                    "Please choose a date range that matches the available statement periods."
                )
            # Handle successful run
            elif output_path:
                gui.status_label.config(text=f"✅ PDF Extraction Complete: {Path(output_path).name}")
                messagebox.showinfo(
                    "PDF Extraction Complete",
                    f"The selected PDFs have been processed successfully.\n\nOutput file:\n{Path(output_path).name}"
                )
            # Handle other "no output" scenarios
            else:
                gui.status_label.config(text="⚠ No matching PDFs found for this period.")
                messagebox.showwarning(
                    "No PDFs Found",
                    "No statement PDFs were processed.\n\nPlease verify the date range or check if new files exist in the folder."
                )
        except Exception as e:
            # 4. On failure, stop progress and show a detailed error
            gui.progress.stop()
            gui.status_label.config(text="❌ Error during PDF extraction")
            tb = traceback.format_exc()
            print(tb)
            messagebox.showerror("Error", f"An error occurred:\n{e}\n\nFull details:\n{tb}")

    # Run the task in a daemon thread so it doesn't block the GUI
    threading.Thread(target=task, daemon=True).start()


def run_reconciliation_gui(gui: JustEatReconciliationGUI, dates: dict):
    """
    Wraps the final reconciliation (Step 3) in a thread to run in the background.
    Gathers all required dates from the GUI's internal state.

    Args:
        gui (JustEatReconciliationGUI): The main GUI application instance.
        dates (dict): A dictionary from `gui.get_all_dates()` containing
                      all 5 required date strings.
    """
    def task():
        try:
            # 1. Update GUI to "running" state
            gui.status_label.config(
                text=f"🔄 Running reconciliation ({dates['acc_start']} → {dates['acc_end']})..."
            )
            gui.progress.start(10)

            # 2. Run the actual business logic from M03
            output_path = run_reconciliation(
                provider_output_folder,
                acc_start=dates['acc_start'],
                acc_end=dates['acc_end'],
                stmt_start=dates['stmt_start'],
                stmt_end=dates['stmt_end'],
                stmt_auto_end=dates['stmt_auto_end']
            )

            # 3. Stop progress bar and handle success/warnings
            gui.progress.stop()
            
            # Check for a "soft warning" (e.g., "No statement CSV found")
            if isinstance(output_path, str) and output_path.startswith("⚠"):
                gui.status_label.config(text=output_path)
                messagebox.showwarning(
                    "No Matching Statement Found",
                    "No Just Eat statement CSV was found that matches the selected date range.\n\n"
                    "Please run Step 2 (Process PDFs) first or choose another period."
                )
            # Handle successful run
            elif output_path:
                gui.status_label.config(text=f"✅ Reconciliation Complete: {Path(output_path).name}")
                messagebox.showinfo(
                    "Reconciliation Complete",
                    f"Reconciliation finished successfully.\n\nOutput file:\n{Path(output_path).name}"
                )
            # Handle other "no output" scenarios
            else:
                gui.status_label.config(text="⚠ No reconciliation results produced.")
                messagebox.showwarning(
                    "No Reconciliation Results",
                    "No reconciliation results were produced.\n\n"
                    "Ensure the selected period aligns with your available statement data."
                )
        except Exception as e:
            # 4. On failure, stop progress and show a detailed error
            gui.progress.stop()
            gui.status_label.config(text="❌ Error during reconciliation")
            tb = traceback.format_exc()
            print(tb)
            messagebox.showerror(
                "Error During Reconciliation",
                f"An unexpected error occurred while running reconciliation.\n\n{e}\n\n{tb}"
            )

    # Run the task in a daemon thread so it doesn't block the GUI
    threading.Thread(target=task, daemon=True).start()


# ====================================================================================================
# 4. MAIN EXECUTION (LAUNCH GUI)
# ----------------------------------------------------------------------------------------------------
# This block is the main entry point for the application.
# It creates the GUI and "wires" the buttons to their respective handlers.
# ====================================================================================================

if __name__ == "__main__":
    # 1. Create an instance of the GUI window
    app = JustEatReconciliationGUI()

    # 2. "Wire up" the GUI buttons to their threaded handlers
    # Use lambdas to pass the 'app' instance (and dates) to the callbacks
    
    # Step 1: Combine DWH Data
    app.combine_dwh_callback = lambda: run_combine_dwh(app)

    # Step 2: Process PDFs for Period
    app.process_pdfs_callback = lambda s, e: run_process_pdfs(app, s, e)

    # Step 3: Run Reconciliation
    app.run_reconciliation_callback = lambda: run_reconciliation_gui(app, app.get_all_dates())

    # 3. Start the GUI main loop
    app.mainloop()