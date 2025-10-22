# ====================================================================================================
# P04_static_lists.py
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
# Static lists for renaming and filtering DataFrames
# ====================================================================================================

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

DWH_COLUMN_RENAME_MAP = {
    "ID_OBFUSCATED": "gp_order_id_obfuscated",
    "ORDER_ID": "gp_order_id",
    "PARTNER_CUSTOMER_ORDER_NUMBER": "je_order_id",
    "OPS_DAY": "gp_date",
    "ORDER_COMPLETED": "order_completed",
    "MFC_NAME": "mfc_name",
    "BLENDED_VAT_RATE": "blended_vat_rate",
    "ALC_PRODUCTS_TOTAL_PRICE_LOCAL": "alcohol_products_total",
    "NON_ALC_PRODUCTS_TOTAL_PRICE_LOCAL": "non_alcohol_products_total",
    "TOTAL_INC_TIPS_LOCAL": "total_excl_bag_fee",
    "BAG_FEE": "bag_fee",
    "TOTAL": "total_incl_bag_fee",
    "ORDER_VENDOR": "order_vendor",
    "ID": "id",
    "DBT_UPDATED_AT": "dbt_updated_at",
    "FAM_EXCLUSIVE_SAVINGS_LOCAL": "fam_exclusive_savings_local",
    "PRODUCTS_TOTAL_PRICE_LOCAL": "products_total_price_local",
    "COUPON_DISCOUNT_LOCAL": "coupon_discount_local",
    "VENDOR_COUPON_DISCOUNT_LOCAL": "vendor_coupon_discount_local",
    "GROWTH_COUPON_DISCOUNT_LOCAL": "growth_coupon_discount_local",
    "ORDER_TOTAL_DISCOUNT_LOCAL": "order_total_discount_local",
    "DELIVERY_FEE_LOCAL": "delivery_fee_local",
    "PRIORITY_FEE_LOCAL": "priority_fee_local",
    "SMALL_ORDER_FEE_LOCAL": "small_order_fee_local",
    "SUBTOTAL_EXC_TIPS_LOCAL": "subtotal_exc_tips_local",
    "TIPS_LOCAL": "tips_local",
}