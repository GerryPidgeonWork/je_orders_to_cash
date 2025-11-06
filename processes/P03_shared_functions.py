# ====================================================================================================
# P03_shared_functions.py
# ----------------------------------------------------------------------------------------------------
# Shared helper functions used across multiple modules (e.g., PDF parser, reconciliation, GUI logic).
#
# Purpose:
#   - Centralize shared logic such as date overlap detection and JE statement coverage checks.
#   - Provide reusable building blocks for PDF and CSV processing across the Orders-to-Cash workflow.
#   - Maintain single definitions for common logic to ensure consistency across modules.
#
# Usage:
#   from processes.P03_shared_functions import statement_overlaps_file, get_je_statement_coverage
#
# Example:
#   >>> statement_overlaps_file("2025-06-02", "2025-06-08", "2025-06-01", "2025-06-30")
#   True
#
#   >>> get_je_statement_coverage(provider_pdf_unprocessed_folder, date(2025,6,1), date(2025,6,30))
#   (datetime.date(2025, 5, 26), datetime.date(2025, 6, 23))
#
# ----------------------------------------------------------------------------------------------------
# Author:        Gerry Pidgeon
# Created:       2025-11-05
# Project:       Just Eat Orders-to-Cash Reconciliation
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
# Bring in standard libraries and settings from the central import hub.
# ====================================================================================================
from processes.P00_set_packages import *


# ====================================================================================================
# 3. DATE RANGE OVERLAP CHECK
# ----------------------------------------------------------------------------------------------------
# Determines whether a file's statement date range overlaps the user-selected period in the GUI.
# Used by both PDF parsing (Step 2) and reconciliation (Step 3).
# ====================================================================================================

def statement_overlaps_file(file_start: str, file_end: str, gui_start: str, gui_end: str) -> bool:
    """
    Determine if the statement date range (from file) overlaps with the GUI-selected accounting range.

    Args:
        file_start (str): File's statement start date (YYYY-MM-DD).
        file_end (str): File's statement end date (YYYY-MM-DD).
        gui_start (str): GUI-selected start date (YYYY-MM-DD).
        gui_end (str): GUI-selected end date (YYYY-MM-DD).

    Returns:
        bool: True if the file overlaps the selected period, False otherwise.
    """
    fs = datetime.strptime(file_start, "%Y-%m-%d").date()
    fe = datetime.strptime(file_end, "%Y-%m-%d").date()
    gs = datetime.strptime(gui_start, "%Y-%m-%d").date()
    ge = datetime.strptime(gui_end, "%Y-%m-%d").date()

    # Overlap exists unless one range ends entirely before the other begins
    return not (fe < gs or fs > ge)


# ====================================================================================================
# 4. GET JE STATEMENT COVERAGE RANGE
# ----------------------------------------------------------------------------------------------------
# Scans all Just Eat statement PDFs and determines the earliest and latest Monday statement dates.
# Statements are named using their Monday start date (e.g., "25.06.02 - JE Statement.pdf").
# Used to determine statement coverage and missing accrual periods.
# ====================================================================================================

def get_je_statement_coverage(statement_folder: Path, acc_start: date, acc_end: date):
    """
    Determine the first and last Monday (statement start dates) for all JE statement PDFs
    that overlap with the selected accounting period.

    Args:
        statement_folder (Path): Folder containing JE statement PDFs.
        acc_start (date): Accounting period start date (YYYY-MM-DD from GUI).
        acc_end (date): Accounting period end date (YYYY-MM-DD from GUI).

    Returns:
        tuple[date|None, date|None]: (first_monday, last_monday)
            - Both are Mondays (JE statement start dates).
            - Returns (None, None) if no statements overlap.
    """

    # Regex pattern to extract date from filenames like "25.06.23 - JE Statement.pdf"
    pattern = re.compile(r"(\d{2,4})[.\-](\d{2})[.\-](\d{2}).*JE Statement\.pdf$", re.I)

    mondays_in_period = []

    # Loop through all JE statement PDFs in the folder
    for pdf_path in statement_folder.glob("*JE Statement*.pdf"):
        m = pattern.search(pdf_path.name)
        if not m:
            continue

        # Convert filename date (always Monday) to datetime.date object
        yy = int(m.group(1))
        yy = yy if yy > 99 else int("20" + f"{yy:02d}")
        mm = int(m.group(2))
        dd = int(m.group(3))
        week_start = date(yy, mm, dd)
        week_end = week_start + timedelta(days=6)

        # Check if statement week overlaps the accounting window
        if not (week_end < acc_start or week_start > acc_end):
            mondays_in_period.append(week_start)

    # Handle case where no statements fall within range
    if not mondays_in_period:
        print(f"⚠ No JE statements overlap {acc_start} → {acc_end} in {statement_folder}")
        return None, None

    # Identify the first and last overlapping Monday
    first_monday = min(mondays_in_period)
    last_monday = max(mondays_in_period)

    print(f"📅 Overlapping JE statements: {first_monday} → {last_monday}")

    return first_monday, last_monday


# ====================================================================================================
# 5. MODULE TEST (STANDALONE EXECUTION)
# ----------------------------------------------------------------------------------------------------
# Allows this module to be executed directly for quick verification.
# ====================================================================================================
if __name__ == "__main__":
    test_folder = Path.cwd() / "02 PDFs"
    test_start = date(2025, 6, 1)
    test_end = date(2025, 6, 30)

    first, last = get_je_statement_coverage(test_folder, test_start, test_end)
    print(f"First Monday: {first}, Last Monday: {last}")
