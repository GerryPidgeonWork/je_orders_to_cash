# ====================================================================================================
# P04_static_lists.py
# ----------------------------------------------------------------------------------------------------
# Contains static mappings, renaming dictionaries, and reference lists used across the project.
#
# Purpose:
#   - Define consistent column rename maps for Just Eat (JET) and DWH datasets.
#   - Standardize naming conventions to simplify DataFrame operations across modules.
#   - Ensure consistent structure when merging JE statement data with DWH exports.
#
# Usage:
#   from processes.P04_static_lists import JET_COLUMN_RENAME_MAP, DWH_COLUMN_RENAME_MAP
#
# Example:
#   >>> df.rename(columns=JET_COLUMN_RENAME_MAP, inplace=True)
#   >>> df.rename(columns=DWH_COLUMN_RENAME_MAP, inplace=True)
#
# Notes:
#   - All DWH columns have been converted to lowercase for standardization.
#   - Mappings are used in reconciliation scripts to ensure uniform schema across sources.
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
# 3. STATIC COLUMN RENAME MAPS
# ----------------------------------------------------------------------------------------------------
# Provides consistent naming conventions between Just Eat exports and DWH data.
# ====================================================================================================

# ----------------------------------------------------------------------------------------------------
# Just Eat Column Rename Map
# ----------------------------------------------------------------------------------------------------
JET_COLUMN_RENAME_MAP = {
    "order_id": "je_order_id",
    "date": "je_date",
    "total_incl_vat": "je_total",
    "refund_amount": "je_refund",
    "type": "transaction_type",
    "source_file": "source_file",
    "statement_start": "statement_start",
    "order_type": "order_type",
    "statement_end": "statement_end",
    "payment_date": "payment_date",
}

# ----------------------------------------------------------------------------------------------------
# DWH Column Rename Map
# ----------------------------------------------------------------------------------------------------
DWH_COLUMN_RENAME_MAP = {
    "id_obfuscated": "gp_order_id_obfuscated",
    "order_id": "gp_order_id",
    "partner_customer_order_number": "je_order_id",
    "ops_day": "gp_date",
    "order_completed": "order_completed",
    "mfc_name": "mfc_name",
    "blended_vat_rate": "blended_vat_rate",
    "alc_products_total_price_local": "alcohol_products_total",
    "non_alc_products_total_price_local": "non_alcohol_products_total",
    "total_inc_tips_local": "total_excl_bag_fee",
    "bag_fee": "bag_fee",
    "total": "total_incl_bag_fee",
    "order_vendor": "order_vendor",
    "id": "id",
    "dbt_updated_at": "dbt_updated_at",
    "fam_exclusive_savings_local": "fam_exclusive_savings_local",
    "products_total_price_local": "products_total_price_local",
    "coupon_discount_local": "coupon_discount_local",
    "vendor_coupon_discount_local": "vendor_coupon_discount_local",
    "growth_coupon_discount_local": "growth_coupon_discount_local",
    "order_total_discount_local": "order_total_discount_local",
    "delivery_fee_local": "delivery_fee_local",
    "priority_fee_local": "priority_fee_local",
    "small_order_fee_local": "small_order_fee_local",
    "subtotal_exc_tips_local": "subtotal_exc_tips_local",
    "tips_local": "tips_local",
}
