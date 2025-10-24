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