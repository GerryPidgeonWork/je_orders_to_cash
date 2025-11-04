# ====================================================================================================
# P03_shared_functions.py
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


# ====================================================================================================

def statement_overlaps_file(file_start: str, file_end: str, gui_start: str, gui_end: str) -> bool:
    """
    Returns True if the statement date range overlaps the GUI-selected date range.
    Used consistently by both PDF parser and reconciliation.
    """
    fs = datetime.strptime(file_start, "%Y-%m-%d").date()
    fe = datetime.strptime(file_end, "%Y-%m-%d").date()
    gs = datetime.strptime(gui_start, "%Y-%m-%d").date()
    ge = datetime.strptime(gui_end, "%Y-%m-%d").date()
    return not (fe < gs or fs > ge)

# ====================================================================================================
# Shared Function – Get JE Statement Coverage Range
# ----------------------------------------------------------------------------------------------------
# Purpose:
# Scans all Just Eat statement PDFs in the given folder and determines the
# earliest and latest Monday statement dates available.
#
# Why:
# - JE statements are always weekly (Mon→Sun) and named by their Monday start date.
# - This provides a single, consistent way to derive <first_monday> and <last_monday>
#   for use in both M02 (PDF processing) and M03 (reconciliation).
# ----------------------------------------------------------------------------------------------------
# Returns:
#   (earliest_monday, latest_monday)
# ----------------------------------------------------------------------------------------------------
# Example:
#   PDFs found: 25.05.26, 25.06.02, 25.06.09, 25.06.16, 25.06.23
#   → returns (2025-05-26, 2025-06-23)
# ----------------------------------------------------------------------------------------------------
# Typical usage:
#   from processes.P03_shared_functions import get_je_statement_coverage
#   first_monday, last_monday = get_je_statement_coverage(provider_pdf_unprocessed_folder)
# ====================================================================================================

# ====================================================================================================
# Shared Function – Get JE Statement Coverage Range (intersect with accounting period)
# ----------------------------------------------------------------------------------------------------
# Purpose:
#   - Look at all Just Eat statement PDFs in provider_pdf_unprocessed_folder.
#   - Identify which statement weeks overlap with the selected accounting period.
#   - Return the earliest and latest Monday dates from that subset.
# ----------------------------------------------------------------------------------------------------
# Example:
#   PDFs present: 25.05.26, 25.06.02, 25.06.09, 25.06.16, 25.06.23, 25.06.30
#   Accounting Period: 2025-06-01 → 2025-06-30
#   Overlapping PDFs: 25.05.26 → 25.06.23
#   Returns: (2025-05-26, 2025-06-23)
# ----------------------------------------------------------------------------------------------------
def get_je_statement_coverage(statement_folder: Path, acc_start: date, acc_end: date):
    """
    Determine the first and last Monday (statement start dates) for all JE statement PDFs
    that overlap with the given accounting period.

    Args:
        statement_folder (Path): Folder containing JE Statement PDFs.
        acc_start (date): Accounting period start date (YYYY-MM-DD from GUI).
        acc_end (date): Accounting period end date (YYYY-MM-DD from GUI).

    Returns:
        tuple[date|None, date|None]: (first_monday, last_monday)
            - Both are Mondays (JE statement start dates).
            - Returns (None, None) if no files overlap.
    """
    import re
    from datetime import datetime, timedelta, date

    # Pattern to extract date from filename (e.g. "25.06.23 - JE Statement.pdf")
    pattern = re.compile(r"(\d{2,4})[.\-](\d{2})[.\-](\d{2}).*JE Statement\.pdf$", re.I)

    mondays_in_period = []

    # Loop through all JE statement PDFs
    for pdf_path in statement_folder.glob("*JE Statement*.pdf"):
        m = pattern.search(pdf_path.name)
        if not m:
            continue

        # Convert filename date (always Monday) into a datetime.date object
        yy = int(m.group(1))
        yy = yy if yy > 99 else int("20" + f"{yy:02d}")
        mm = int(m.group(2))
        dd = int(m.group(3))
        week_start = date(yy, mm, dd)
        week_end = week_start + timedelta(days=6)

        # Check if statement week overlaps the accounting window
        if not (week_end < acc_start or week_start > acc_end):
            mondays_in_period.append(week_start)

    if not mondays_in_period:
        print(f"⚠ No JE statements overlap {acc_start} → {acc_end} in {statement_folder}")
        return None, None

    first_monday = min(mondays_in_period)
    last_monday = max(mondays_in_period)
    print(f"📅 Overlapping JE statements: {first_monday} → {last_monday}")

    return first_monday, last_monday