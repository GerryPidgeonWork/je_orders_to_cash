# ====================================================================================================
# P07_module_configs.py
# ----------------------------------------------------------------------------------------------------
# Central configuration hub for the Orders-to-Cash Reconciliation project.
#
# Purpose:
#   - Store shared constants, configuration parameters, and toggle switches used across modules.
#   - Maintain one centralized source for settings such as date formats, thresholds, and
#     file-naming conventions.
#   - Simplify maintenance by avoiding hard-coded values in processing or GUI scripts.
#
# Optimized for:
#   • Cross-module reusability (e.g. file naming, reconciliation thresholds, logging flags)
#   • Compatibility with PyInstaller and external configuration loaders
#
# Usage:
#   from processes.P07_module_configs import FILE_DATE_FORMAT, RECONCILIATION_TOLERANCE
#
# Example:
#   >>> print(FILE_DATE_FORMAT)
#   '%Y-%m-%d'
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
# Bring in shared libraries and base settings from the central import hub.
# ====================================================================================================
from processes.P00_set_packages import *


# ====================================================================================================
# 3. GLOBAL CONFIGURATION CONSTANTS
# ----------------------------------------------------------------------------------------------------
# Shared constants for date formats, file naming, and reconciliation logic.
# These should remain consistent across all provider workflows.
# ----------------------------------------------------------------------------------------------------

# --- Date & Time Formats ---
FILE_DATE_FORMAT = "%y.%m.%d"             # Format used in JE filenames (e.g., 25.06.23)
STANDARD_DATE_FORMAT = "%Y-%m-%d"         # Standard ISO format for output and logs
DISPLAY_DATE_FORMAT = "%d %b %Y"          # Human-readable display format for GUIs

# --- File Naming Conventions ---
JE_STATEMENT_KEYWORD = "JE Statement"
JE_ORDER_DETAIL_KEYWORD = "JE Order Level Detail"
OUTPUT_MASTER_FILENAME = "je_dwh_all.csv"

# --- Reconciliation Thresholds ---
RECONCILIATION_TOLERANCE = 0.01           # Max allowed float variance between JE and DWH totals
MATCH_STATUS_EXACT = "Matched"
MATCH_STATUS_VARIANCE = "Variance"
MATCH_STATUS_UNMATCHED = "Unmatched"

# --- Folder Naming ---
DWH_FOLDER_NAME = "03 DWH"
PDF_FOLDER_NAME = "02 PDFs"
OUTPUT_FOLDER_NAME = "04 Consolidated Output"

# --- Logging Settings ---
ENABLE_DEBUG_LOGGING = False               # Toggle verbose console debug messages
LOG_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # Format for log timestamps


# ====================================================================================================
# 4. FUNCTIONAL CONFIGURATION TOGGLES
# ----------------------------------------------------------------------------------------------------
# Use these to enable/disable optional behaviours at runtime.
# ----------------------------------------------------------------------------------------------------

# Automatically open output folder when reconciliation completes
AUTO_OPEN_OUTPUT_FOLDER = True

# Skip previously processed PDFs to speed up reruns
SKIP_PROCESSED_PDFS = True

# Automatically create missing reference folders if not found
AUTO_CREATE_REFERENCE_FOLDERS = True


# ====================================================================================================
# 5. FUTURE EXTENSIONS
# ----------------------------------------------------------------------------------------------------
# Add additional environment-specific configurations (e.g. test/staging vs production),
# API tokens, or Snowflake connection parameters here if needed.
# ----------------------------------------------------------------------------------------------------

# Example placeholders (commented for now):
# SNOWFLAKE_ENV = "PROD"
# SNOWFLAKE_ROLE = "ANALYST"
# SNOWFLAKE_WAREHOUSE = "DATA_WH"