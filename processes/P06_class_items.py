# ====================================================================================================
# P06_class_items.py
# ----------------------------------------------------------------------------------------------------
# Contains shared data classes and structured objects used throughout the
# Orders-to-Cash reconciliation process.
#
# Purpose:
#   - Define reusable, lightweight data models for invoice metadata, financial summaries,
#     or structured statement representations.
#   - Provide consistent and type-safe containers that make data passing between modules
#     (PDF parser, reconciliation, GUI, etc.) more robust and maintainable.
#
# Usage:
#   from processes.P06_class_items import InvoiceMetadata, ReconciliationSummary
#
# Example:
#   >>> meta = InvoiceMetadata(store_no="1234", invoice_no="JE-2025-06-15", net_amount=125.00)
#   >>> print(meta.invoice_no)
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
# Bring in standard libraries and settings from the centralized import hub.
# ====================================================================================================
from processes.P00_set_packages import *


# ====================================================================================================
# 3. CLASS DEFINITIONS
# ----------------------------------------------------------------------------------------------------
# Define reusable @dataclass structures for metadata, PDFs, and reconciliation results.
# ----------------------------------------------------------------------------------------------------



# ====================================================================================================
# 4. FUTURE EXTENSIONS
# ----------------------------------------------------------------------------------------------------
# Placeholder section for adding additional structured objects, e.g.:
#   - PDF extraction results
#   - JE weekly aggregates
#   - Vendor refund summaries
# ----------------------------------------------------------------------------------------------------
