# ====================================================================================================
# P01_set_file_paths.py
# ----------------------------------------------------------------------------------------------------
# Defines all root, provider, and subfolder paths used across the project.
# Ensures centralised path management for consistent use across all modules.
#
# Purpose:
#   - Centralise all file and folder paths used throughout the project.
#   - Simplify portability between environments (Windows, Mac, WSL, etc.).
#   - Ensure all required folders exist before processing begins.
#
# Usage:
#   from processes.P01_set_file_paths import provider_output_folder
#
# Folder Hierarchy:
#   01 CSVs
#       ├── 01 To Process
#       ├── 02 Processed
#       └── 03 Reference
#   02 PDFs
#       ├── 01 To Process
#       ├── 02 Processed
#       └── 03 Reference
#   03 DWH
#   04 Consolidated Output
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
# 3. ROOT FOLDER DEFINITIONS
# ----------------------------------------------------------------------------------------------------
# Define the base directory and the provider-specific root.
# ====================================================================================================
root_folder = Path(r'H:\Shared drives\Automation Projects\Accounting\Orders to Cash')
provider_root_folder = root_folder / '05 Just Eat'  # Change the provider here


# ====================================================================================================
# 4. SUBFOLDER DEFINITIONS
# ----------------------------------------------------------------------------------------------------
# Define the folder structure for CSVs, PDFs, DWH exports, and consolidated outputs.
# ====================================================================================================

# --- CSV folders ---
provider_csv_folder = provider_root_folder / '01 CSVs'
provider_csv_unprocessed_folder = provider_csv_folder / '01 To Process'
provider_csv_processed_folder = provider_csv_folder / '02 Processed'
provider_csv_reference_folder = provider_csv_folder / '03 Reference'  # Reference CSV files (e.g., mapping tables)

# --- PDF folders ---
provider_pdf_folder = provider_root_folder / '02 PDFs'
provider_pdf_unprocessed_folder = provider_pdf_folder / '01 To Process'
provider_pdf_processed_folder = provider_pdf_folder / '02 Processed'
provider_pdf_reference_folder = provider_pdf_folder / '03 Reference'  # Reference PDFs (e.g., templates or samples)

# --- DWH + Output folders ---
provider_dwh_folder = provider_root_folder / '03 DWH'
provider_output_folder = provider_root_folder / '04 Consolidated Output'
provider_refund_folder = provider_output_folder / '01 Refund Data'


# ====================================================================================================
# 5. ENSURE FOLDERS EXIST
# ----------------------------------------------------------------------------------------------------
# Create all expected subdirectories if they don't already exist.
# This ensures compatibility across users and environments.
# ====================================================================================================
for folder in [
    provider_root_folder,
    provider_csv_folder,
    provider_csv_unprocessed_folder,
    provider_csv_processed_folder,
    provider_csv_reference_folder,
    provider_pdf_folder,
    provider_pdf_unprocessed_folder,
    provider_pdf_processed_folder,
    provider_pdf_reference_folder,
    provider_dwh_folder,
    provider_output_folder,
    provider_refund_folder,
]:
    folder.mkdir(parents=True, exist_ok=True)
