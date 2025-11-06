# ====================================================================================================
# M03_run_reconciliation.py
# ----------------------------------------------------------------------------------------------------
# Step 3 – Run Reconciliation
# ----------------------------------------------------------------------------------------------------
# Purpose:
#   - Matches JE Order Level Detail CSV (from PDFs) with combined DWH data.
#   - Determines which period is statement-covered and which requires accruals.
#   - Returns output file path for downstream processing or GUI message.
#
# Notes:
#   - Receives all 5 GUI dates directly from M00_run_gui.py
#   - Derives statement + accrual periods internally
#   - Simplified JE file detection (no redundant checks)
#   - Assumes all DWH columns from 'je_dwh_all.csv' are lowercase.
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
import sys
from pathlib import Path

# ----------------------------------------------------------------------------------------------------
# Ensure this module can import other "processes" packages by adding its parent folder to sys.path.
# Also disable __pycache__ creation for cleaner deployments (especially when bundled with PyInstaller).
# ----------------------------------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True


# ====================================================================================================
# 2. PROJECT IMPORTS
# ----------------------------------------------------------------------------------------------------
# Import shared, project-wide dependencies and utilities.
#   - All standard and third-party packages are centrally imported in P00_set_packages.py
#   - Path constants, shared functions, and column maps are sourced from the “processes” package.
# ====================================================================================================
from processes.P00_set_packages import * # Standardised imports (pandas, numpy, datetime as dt, etc.)
from processes.P01_set_file_paths import provider_output_folder, provider_pdf_unprocessed_folder
from processes.P02_system_processes import user_download_folder
from processes.P03_shared_functions import get_je_statement_coverage
from processes.P04_static_lists import DWH_COLUMN_RENAME_MAP, JET_COLUMN_RENAME_MAP

# ====================================================================================================
# 3. CORE RECONCILIATION FUNCTION
# ====================================================================================================

def run_reconciliation(provider_output_folder, acc_start, acc_end, stmt_start, stmt_end, stmt_auto_end):
    """
    Runs the Just Eat reconciliation process for the selected accounting and statement periods.

    Args:
        provider_output_folder (Path):
            Folder containing the combined DWH and JE Order Level Detail CSVs.
        acc_start (str):
            Accounting period start date (YYYY-MM-DD) from the GUI.
        acc_end (str):
            Accounting period end date (YYYY-MM-DD) from the GUI.
        stmt_start (str):
            JE statement start date (Monday of first week) from the GUI.
        stmt_end (str):
            JE statement end (Monday of last week) from the GUI.
        stmt_auto_end (str):
            JE statement auto-calculated end (Sunday of last week) from the GUI.

    Returns:
        Path:
            The `pathlib.Path` object pointing to the final reconciliation CSV.

    Raises:
        FileNotFoundError:
            If the required 'je_dwh_all.csv' or the expected
            'JE Order Level Detail.csv' file is not found.
    """

    # -------------------------------------------------------------------------------------------------
    # STEP 1: PARSE AND VALIDATE DATES
    # -------------------------------------------------------------------------------------------------
    # Convert all incoming GUI date values (str or date) to consistent date objects.
    def parse_date(d):
        """Safely parse a string or return the date unchanged."""
        return d if isinstance(d, dt.date) else dt.datetime.strptime(d, "%Y-%m-%d").date()

    acc_start = parse_date(acc_start)
    acc_end = parse_date(acc_end)
    stmt_start_dt = parse_date(stmt_start)
    stmt_end_dt = parse_date(stmt_end)
    stmt_auto_dt = parse_date(stmt_auto_end)

    # -------------------------------------------------------------------------------------------------
    # STEP 2: DERIVE WORKING DATE RANGES (STATEMENT VS. ACCRUAL)
    # -------------------------------------------------------------------------------------------------
    data_start = acc_start
    data_statement_end = max(stmt_auto_dt, acc_end)

    # Determine accrual range only if the accounting period ends after the last statement
    if stmt_auto_dt < acc_end:
        data_accrue_start = stmt_auto_dt + dt.timedelta(days=1)
        data_accrue_end = acc_end
        accrual_text = f"{data_accrue_start} → {data_accrue_end}"
    else:
        data_accrue_start = None
        data_accrue_end = None
        accrual_text = "Not Needed"

    print("🗓 Derived Periods:")
    print(f" - Accounting Start:   {acc_start}")
    print(f" - Accounting End:     {acc_end}")
    print(f" - Statement Start:    {stmt_start_dt}")
    print(f" - Statement End:      {stmt_auto_dt}")
    print(f" - Data Start:         {data_start}")
    print(f" - Statement Coverage: {data_statement_end}")
    print(f" - Accrual Period:     {accrual_text}")
    print("----------------------------------------------------------------------------------")

    # =================================================================================================
    # STEP 3: LOAD DWH DATA
    # =================================================================================================
    # 3.1: Find and validate the master DWH file.
    dwh_file = provider_output_folder / "je_dwh_all.csv"
    if not dwh_file.exists():
        raise FileNotFoundError("DWH file not found — please run Step 1 (Combine DWH Data) first.")
    print(f"📊 Found DWH file: {dwh_file.name}")

    # 3.2: Load DWH data into DataFrame.
    print("📂 Loading DWH data...")
    dwh_df = pd.read_csv(dwh_file, low_memory=False) # low_memory=False added for safety
    print(f"✅ DWH rows (raw): {len(dwh_df):,}")
    dwh_df['order_category'] = ''

    # =================================================================================================
    # STEP 4: LOAD JE STATEMENT DATA
    # =================================================================================================
    print(f"🔍 Looking for JE Order Level Detail file for statement period: {stmt_start_dt} → {stmt_end_dt}")

    # 4.1: Build the exact expected filename from GUI dates.
    expected_filename = f"{stmt_start_dt:%y.%m.%d} - {stmt_end_dt:%y.%m.%d} - JE Order Level Detail.csv"
    expected_path = provider_output_folder / expected_filename
    print(f"🔎 Expected file name: {expected_filename}")

    # 4.2: Check if the file exists and raise a clear error if not.
    if expected_path.exists():
        je_statement = expected_path
        print(f"✅ Found JE Order Level Detail file: {je_statement.name}")
    else:
        # Gather all possible JE statement files to display for debugging
        available_csvs = [f.name for f in provider_output_folder.glob("*JE Order Level Detail*.csv")]
        raise FileNotFoundError(
            f"❌ JE Order Level Detail file not found for statement period {stmt_start_dt} → {stmt_end_dt}.\n"
            f"Expected file:\n  {expected_filename}\n\n"
            f"Please run Step 2 (Extract PDFs) to generate this file.\n\n"
            f"Available files in folder:\n  " + "\n  ".join(available_csvs)
        )
    
    # 4.3: Load JE statement data into DataFrame.
    print("----------------------------------------------------------------------------------")
    print("📂 Loading JE Statement data...")
    je_df = pd.read_csv(je_statement)
    print(f"✅ JE rows (raw): {len(je_df):,}")

    # =================================================================================================
    # STEP 5: MERGE DWH DATA INTO JE STATEMENT DATA
    # =================================================================================================
    
    # 5.1: Orders (full DWH merge)
    je_orders = je_df.loc[je_df['transaction_type'] == 'Order'].copy()
    je_orders = pd.merge(je_orders, dwh_df, left_on='je_order_id', right_on='mp_order_id', how='left') # <-- CHANGED
    je_orders['order_category'] = 'Matched'

    # 5.2: Refunds (partial DWH merge for metadata)
    je_refunds = je_df.loc[je_df['transaction_type'] == 'Refund'].copy()
    je_refunds = pd.merge( je_refunds, dwh_df[['mp_order_id', 'gp_order_id', 'gp_order_id_obfuscated', # <-- CHANGED
                                'location_name', 'order_vendor', 'vendor_group', 'order_completed',
                                'created_at_day', 'created_at_week', 'created_at_month', 
                                'delivered_at_day', 'delivered_at_week', 'delivered_at_month', 
                                'ops_date_day', 'ops_date_week', 'ops_date_month']],
                                left_on='je_order_id', right_on='mp_order_id', how='left') # <-- CHANGED
    je_refunds['order_category'] = 'Matched'

    # 5.3: Commission (JE only, no DWH merge)
    je_commission = je_df.loc[je_df['transaction_type'] == 'Commission'].copy()
    je_commission['order_category'] = 'Commission'

    # 5.4: Marketing (JE only, no DWH merge)
    je_marketing = je_df.loc[je_df['transaction_type'] == 'Marketing'].copy()
    je_marketing['order_category'] = 'Marketing'

    # 5.5: Combine all processed JE types.
    je_df = pd.concat([je_orders, je_refunds, je_commission, je_marketing], ignore_index=True)

    print(f"✅ Final JE rows after combining all transaction types: {len(je_df):,}")

    # =================================================================================================
    # STEP 6: FIND MISSING DWH ORDERS (STATEMENT PERIOD)
    # =================================================================================================
    print("----------------------------------------------------------------------------------")
    print("🔍 Checking for missing completed DWH orders not in JE data (using CREATED_AT_DAY)...")

    # 6.1: Isolate DWH orders within the statement window.
    dwh_df['created_at_day'] = pd.to_datetime(dwh_df['created_at_day'], errors='coerce').dt.date # <-- CHANGED

    mask_dwh_window = (
        (dwh_df['created_at_day'] >= stmt_start_dt) & # <-- CHANGED
        (dwh_df['created_at_day'] <= stmt_auto_dt) & # <-- CHANGED
        (dwh_df['order_completed'] == 1) # <-- CHANGED
    )
    dwh_window = dwh_df.loc[mask_dwh_window].copy()

    print(f"📅 DWH completed orders in statement window ({stmt_start_dt} → {stmt_auto_dt}): {len(dwh_window):,}")

    # 6.2: Identify DWH orders that are *not* in the JE file.
    existing_je_orders = set(je_df['je_order_id'].dropna().astype(str))
    missing_dwh = dwh_window.loc[~dwh_window['mp_order_id'].astype(str).isin(existing_je_orders)].copy() # <-- CHANGED

    # 6.3: Format and append these "Missing in Statement" orders.
    missing_dwh['order_category'] = 'Missing in Statement'
    missing_dwh['transaction_type'] = 'Order'
    missing_dwh['je_order_id'] = missing_dwh['mp_order_id'] # <-- CHANGED
    missing_dwh['je_total'] = missing_dwh['total_payment_with_tips_inc_vat'] # <-- CHANGED
    missing_dwh['je_refund'] = 0

    final_df = pd.concat([je_df, missing_dwh], ignore_index=True)

    print(f"✅ Added {len(missing_dwh):,} missing completed orders from DWH.")
    print(f"📊 Final combined rows: {len(final_df):,}")
    print("----------------------------------------------------------------------------------")

    # =================================================================================================
    # STEP 7: ADD DWH ACCRUALS (POST-STATEMENT PERIOD)
    # =================================================================================================
    
    # 7.1: Check if an accrual period is necessary.
    if data_accrue_start and data_accrue_end:
        print("----------------------------------------------------------------------------------")
        print(f"🧾 Adding accrual orders from DWH between {data_accrue_start} → {data_accrue_end}...")

        # 7.2: Isolate DWH orders within the accrual window.
        dwh_df['created_at_day'] = pd.to_datetime(dwh_df['created_at_day'], errors='coerce').dt.date # <-- CHANGED

        mask_accrual = (
            (dwh_df['created_at_day'] >= data_accrue_start) & # <-- CHANGED
            (dwh_df['created_at_day'] <= data_accrue_end) & # <-- CHANGED
            (dwh_df['order_completed'] == 1) # <-- CHANGED
        )
        accrual_orders = dwh_df.loc[mask_accrual].copy()

        # Exclude any already present in JE (for safety)
        existing_orders = set(final_df['je_order_id'].dropna().astype(str))
        accrual_orders = accrual_orders.loc[~accrual_orders['mp_order_id'].astype(str).isin(existing_orders)].copy() # <-- CHANGED

        # 7.3: Format and append these "Accrual" orders.
        accrual_orders['order_category'] = 'Accrual (Post-Statement)'
        accrual_orders['transaction_type'] = 'Order'
        accrual_orders['je_order_id'] = accrual_orders['mp_order_id'] # <-- CHANGED
        accrual_orders['je_total'] = accrual_orders['total_payment_with_tips_inc_vat'] # <-- CHANGED
        accrual_orders['je_refund'] = 0

        final_df = pd.concat([final_df, accrual_orders], ignore_index=True)

        print(f"✅ Added {len(accrual_orders):,} accrual orders from DWH.")
        print(f"📊 Final combined rows: {len(final_df):,}")
    else:
        print("🟢 No accrual period required — skipping accrual detection.")

    # =================================================================================================
    # STEP 8: FINAL CLEANUP AND FORMATTING
    # =================================================================================================

    # 8.1: Clean and type-cast order IDs.
    final_df['je_order_id'] = (final_df['je_order_id'].replace(r'^\s*$', np.nan, regex=True).replace('', np.nan))
    final_df['je_order_id'] = pd.to_numeric(final_df['je_order_id'], errors='coerce').astype('Int64') 
 
    # 8.2: Standardise all date columns.
    # List all columns that should be treated as dates
    date_columns = ['je_date', 'created_at_day', 'delivered_at_day', 'ops_date_day', # <-- CHANGED
                    'created_at_week', 'delivered_at_week', 'ops_date_week', 
                    'created_at_month', 'delivered_at_month', 'ops_date_month']

    # Apply the same cleaning logic to each existing column
    for col in date_columns:
        if col in final_df.columns:
            final_df[col] = final_df[col].replace(r'^\s*$', np.nan, regex=True)
            # Attempt to parse both 'dd/mm/yy' and 'YYYY-MM-DD' formats
            final_df[col] = pd.to_datetime(final_df[col], format='%d/%m/%y', errors='coerce').fillna(pd.to_datetime(final_df[col], format='%Y-%m-%d', errors='coerce'))
            final_df[col] = final_df[col].dt.strftime('%Y-%m-%d')
            final_df.loc[final_df[col].isna(), col] = np.nan
            print(f"🗓 Cleaned {col}: {final_df[col].notna().sum():,} valid dates")

    # 8.3: Clean and finalise column names (lowercase, underscores).
    final_df['mp_order_id'] = np.where(final_df['mp_order_id'].isna(), final_df['je_order_id'], final_df['mp_order_id']) # <-- CHANGED
    # This next line is a safeguard, ensuring all columns are lowercase,
    # even though DWH cols already are.
    final_df.columns = final_df.columns.str.strip().str.lower().str.replace(' ', '_', regex=False).str.replace(r'[^\w_]', '', regex=True)

    # 8.4: Calculate variance for matched orders.
    mask = final_df['transaction_type'] == 'Order'
    final_df.loc[mask, 'matched_amount'] = np.where(final_df.loc[mask, 'je_total'].fillna(0).round(2) == final_df.loc[mask, 'total_payment_with_tips_inc_vat'].fillna(0).round(2), 'Matched', 'Not Matched')
    final_df.loc[mask, 'amount_variance'] = np.where(final_df.loc[mask, 'je_total'].fillna(0).round(2) == final_df.loc[mask, 'total_payment_with_tips_inc_vat'].fillna(0).round(2), 0, (final_df.loc[mask, 'je_total'].fillna(0).round(2) - final_df.loc[mask, 'total_payment_with_tips_inc_vat'].fillna(0).round(2)).round(2))

    mask = final_df['transaction_type'].isin(['Refund', 'Commission', 'Marketing'])
    final_df.loc[mask, 'matched_amount'] = 'Ignore'
    final_df.loc[mask, 'amount_variance'] = 0

    # 8.5: Re-order columns to final specification.
    # This list is already lowercase and should match the DWH output.
    final_df = final_df[['gp_order_id', 'gp_order_id_obfuscated', 'mp_order_id', 'statement_start', 'transaction_type', 'order_category', 'matched_amount', 'amount_variance', 
                         'je_total', 'je_refund', 'location_name', 'order_vendor', 'vendor_group', 'order_completed', 'created_at_day', 'created_at_week', 'created_at_month', 
                         'post_promo_sales_inc_vat', 'delivery_fee_inc_vat', 'priority_fee_inc_vat', 'small_order_fee_inc_vat', 'mp_bag_fee_inc_vat', 'total_payment_inc_vat', 
                         'tips_amount', 'total_payment_with_tips_inc_vat', 'post_promo_sales_exc_vat', 'delivery_fee_exc_vat', 'priority_fee_exc_vat', 'small_order_fee_exc_vat', 
                         'mp_bag_fee_exc_vat', 'total_revenue_exc_vat', 'cost_of_goods_inc_vat', 'cost_of_goods_exc_vat',  'total_products', 'item_quantity_count_0', 
                         'item_quantity_count_5', 'item_quantity_count_20', 'total_price_exc_vat_0', 'total_price_exc_vat_5', 'total_price_exc_vat_20', 'total_price_inc_vat_0', 
                         'total_price_inc_vat_5', 'total_price_inc_vat_20']]
    
    # 8.6: Sort by order ID.
    final_df = final_df.sort_values(by = 'gp_order_id')
    
    # =================================================================================================
    # STEP 9: SAVE AND RETURN OUTPUT
    # =================================================================================================
    # 9.1: Define final output path.
    output_path = provider_output_folder / f"{stmt_start_dt:%y.%m.%d} - {stmt_end_dt:%y.%m.%d} - JE Reconciliation.csv"
    
    # 9.2: Save to CSV.
    final_df.to_csv(output_path, index=False)
    print(f"💾 Output written to: {output_path}")
    print("✅ Reconciliation completed successfully.")
    print("----------------------------------------------------------------------------------")

    return output_path


# ====================================================================================================
# 4. MAIN EXECUTION (STANDALONE TEST)
# ----------------------------------------------------------------------------------------------------
# Purpose:
#   - Allows the module to run independently for direct testing outside the GUI framework.
# ----------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    print("--- Running M03_run_reconciliation in standalone mode for testing ---")
    
    # --- DEFINE TEST DATES ---
    # These dates must correspond to files you have in your '04 Consolidated Output' folder.
    # Example: Simulating a run for the October 2025 accounting period.
    TEST_ACC_START = "2025-10-01"
    TEST_ACC_END = "2025-10-31"
    
    # These dates must match a 'JE Order Level Detail.csv' file.
    # e.g., "25.09.30 - 25.10.20 - JE Order Level Detail.csv"
    TEST_STMT_START = "2025-09-30" # Monday of first week
    TEST_STMT_END = "2025-10-20"   # Monday of last week
    TEST_STMT_AUTO_END = "2025-10-26" # Sunday of last week (stmt_end + 6 days)

    try:
        run_reconciliation(
            provider_output_folder,
            TEST_ACC_START,
            TEST_ACC_END,
            TEST_STMT_START,
            TEST_STMT_END,
            TEST_STMT_AUTO_END
        )
    except Exception as e:
        print(f"\n--- SCRIPT FAILED ---")
        print(f"Error: {e}")