# ====================================================================================================
# M03_run_reconciliation.py
# ----------------------------------------------------------------------------------------------------
# Step 3 – Run Reconciliation
# ----------------------------------------------------------------------------------------------------
# Purpose:
# - Matches JE Order Level Detail CSV (from PDFs) with combined DWH data.
# - Determines which period is statement-covered and which requires accruals.
# - Returns output file path for downstream processing or GUI message.
# ----------------------------------------------------------------------------------------------------
# Updated:
# - Receives all 5 GUI dates directly from M00_run_gui.py
# - Derives statement + accrual periods internally
# - Simplified JE file detection (no redundant checks)
# ====================================================================================================

import sys
from pathlib import Path

# Adjust sys.path so we can import from parent folder (../processes/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True

# ====================================================================================================
# Import Project Packages and Shared Modules
# ====================================================================================================
from processes.P00_set_packages import *  # Standardised imports (pandas, numpy, datetime as dt, etc.)
from processes.P01_set_file_paths import provider_output_folder, provider_pdf_unprocessed_folder
from processes.P02_system_processes import user_download_folder
from processes.P03_shared_functions import get_je_statement_coverage
from processes.P04_static_lists import DWH_COLUMN_RENAME_MAP, JET_COLUMN_RENAME_MAP

# ====================================================================================================
# Main Reconciliation Function
# ====================================================================================================

def run_reconciliation(provider_output_folder, acc_start, acc_end, stmt_start, stmt_end, stmt_auto_end):
    """
    Runs the Just Eat reconciliation process for the selected accounting and statement periods.

    Parameters:
        provider_output_folder (Path): Folder containing DWH and JE CSVs
        acc_start (str): Accounting period start date (YYYY-MM-DD)
        acc_end (str): Accounting period end date (YYYY-MM-DD)
        stmt_start (str): JE statement start date
        stmt_end (str): JE statement end (Monday of last statement week)
        stmt_auto_end (str): JE statement auto-calculated end (Sunday of last week)

    Returns:
        str: Path to the reconciliation output CSV (or raises FileNotFoundError)
    """

    # =================================================================================================
    # Convert all incoming GUI date values (str or date) to date objects
    # =================================================================================================
    def parse_date(d):
        """Safely parse a string or return the date unchanged."""
        return d if isinstance(d, dt.date) else dt.datetime.strptime(d, "%Y-%m-%d").date()

    acc_start = parse_date(acc_start)
    acc_end = parse_date(acc_end)
    stmt_start_dt = parse_date(stmt_start)
    stmt_end_dt = parse_date(stmt_end)
    stmt_auto_dt = parse_date(stmt_auto_end)

    # =================================================================================================
    # Derive working date ranges
    # =================================================================================================
    data_start = acc_start
    data_statement_end = max(stmt_auto_dt, acc_end)

    # Determine accrual range only if needed
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
    print(f" - Statement End:      {stmt_auto_end}")
    print(f" - Data Start:         {data_start}")
    print(f" - Statement Coverage: {data_statement_end}")
    print(f" - Accrual Period:     {accrual_text}")
    print("----------------------------------------------------------------------------------")

    # =================================================================================================
    # Step 0 — Verify Combined DWH File
    # =================================================================================================
    dwh_file = provider_output_folder / "je_dwh_all.csv"
    if not dwh_file.exists():
        raise FileNotFoundError("DWH file not found — please run Step 1 (Combine DWH Data) first.")
    print(f"📊 Found DWH file: {dwh_file.name}")

    # =================================================================================================
    # Step 1 — Identify JE Statement File Based on GUI Statement Dates
    # =================================================================================================
    print(f"🔍 Looking for JE Order Level Detail file for statement period: {stmt_start_dt} → {stmt_end_dt}")

    # Build exact expected filename from GUI-provided statement dates
    expected_filename = f"{stmt_start_dt:%y.%m.%d} - {stmt_end_dt:%y.%m.%d} - JE Order Level Detail.csv"
    expected_path = provider_output_folder / expected_filename

    # Print what the script is looking for
    print(f"🔎 Expected file name: {expected_filename}")

    # Check if the file exists
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
    
    # =================================================================================================
    # Step 2 — Load and filter PDF (JE Order Level Detail) data
    # =================================================================================================
    print("----------------------------------------------------------------------------------")
    print("📂 Loading JE Statement data...")
    je_df = pd.read_csv(je_statement)
    print(f"✅ JE rows (raw): {len(je_df):,}")

    # --- Filter DWH to align with GUI dates ---
    print("📂 Loading DWH data...")
    dwh_df = pd.read_csv(dwh_file)
    print(f"✅ DWH rows (raw): {len(dwh_df):,}")
    dwh_df['order_category'] = ''

    # =================================================================================================
    # Step 3 — Populate all data from DWH
    # =================================================================================================
    # --- Case 1: Orders (full DWH merge) ---
    je_orders = je_df.loc[je_df['transaction_type'] == 'Order'].copy()
    je_orders = pd.merge(je_orders, dwh_df, left_on='je_order_id', right_on='MP_ORDER_ID', how='left')
    je_orders['order_category'] = 'Matched'

    # --- Case 2: Refunds (partial DWH merge, only metadata) ---
    je_refunds = je_df.loc[je_df['transaction_type'] == 'Refund'].copy()
    je_refunds = pd.merge( je_refunds, dwh_df[['MP_ORDER_ID', 'GP_ORDER_ID', 'GP_ORDER_ID_OBFUSCATED',
                'LOCATION_NAME', 'ORDER_VENDOR', 'VENDOR_GROUP', 'ORDER_COMPLETED',
                'CREATED_AT_DAY', 'CREATED_AT_WEEK', 'CREATED_AT_MONTH', 
                'DELIVERED_AT_DAY', 'DELIVERED_AT_WEEK', 'DELIVERED_AT_MONTH', 
                'OPS_DATE_DAY', 'OPS_DATE_WEEK', 'OPS_DATE_MONTH']],
                left_on='je_order_id', right_on='MP_ORDER_ID', how='left')
    je_refunds['order_category'] = 'Matched'

    # --- Case 3: Commission (JE only, no DWH merge) ---
    je_commission = je_df.loc[je_df['transaction_type'] == 'Commission'].copy()
    je_commission['order_category'] = 'Commission'

    # --- Case 4: Marketing (JE only, no DWH merge) ---
    je_marketing = je_df.loc[je_df['transaction_type'] == 'Marketing'].copy()
    je_marketing['order_category'] = 'Marketing'

    # --- Combine all together ---
    je_df = pd.concat([je_orders, je_refunds, je_commission, je_marketing], ignore_index=True)

    print(f"✅ Final JE rows after combining all transaction types: {len(je_df):,}")

    # =================================================================================================
    # Step 4 — Add any completed DWH orders not in JE data (based on CREATED_AT_DAY)
    # =================================================================================================
    print("----------------------------------------------------------------------------------")
    print("🔍 Checking for missing completed DWH orders not in JE data (using CREATED_AT_DAY)...")

    # Ensure CREATED_AT_DAY is a proper date
    dwh_df['CREATED_AT_DAY'] = pd.to_datetime(dwh_df['CREATED_AT_DAY'], errors='coerce').dt.date

    # Filter DWH for completed orders in the statement window
    mask_dwh_window = (
        (dwh_df['CREATED_AT_DAY'] >= stmt_start_dt) &
        (dwh_df['CREATED_AT_DAY'] <= stmt_auto_dt) &
        (dwh_df['ORDER_COMPLETED'] == 1)
    )
    dwh_window = dwh_df.loc[mask_dwh_window].copy()

    print(f"📅 DWH completed orders in statement window ({stmt_start_dt} → {stmt_auto_dt}): {len(dwh_window):,}")

    # Identify orders not already in JE data
    existing_je_orders = set(je_df['je_order_id'].dropna().astype(str))
    missing_dwh = dwh_window.loc[~dwh_window['MP_ORDER_ID'].astype(str).isin(existing_je_orders)].copy()

    # Label missing ones
    missing_dwh['order_category'] = 'Missing in Statement'
    missing_dwh['transaction_type'] = 'Order'
    missing_dwh['je_order_id'] = missing_dwh['MP_ORDER_ID']
    missing_dwh['je_total'] = missing_dwh['TOTAL_PAYMENT_WITH_TIPS_INC_VAT']
    missing_dwh['je_refund'] = 0

    # Combine with existing JE dataframe
    final_df = pd.concat([je_df, missing_dwh], ignore_index=True)

    print(f"✅ Added {len(missing_dwh):,} missing completed orders from DWH.")
    print(f"📊 Final combined rows: {len(final_df):,}")
    print("----------------------------------------------------------------------------------")

    # =================================================================================================
    # Step 5 — Add completed DWH orders after statement end (true accruals)
    # =================================================================================================
    if data_accrue_start and data_accrue_end:
        print("----------------------------------------------------------------------------------")
        print(f"🧾 Adding accrual orders from DWH between {data_accrue_start} → {data_accrue_end}...")

        # Ensure CREATED_AT_DAY is in datetime.date format
        dwh_df['CREATED_AT_DAY'] = pd.to_datetime(dwh_df['CREATED_AT_DAY'], errors='coerce').dt.date

        # Filter DWH for accrual period completed orders
        mask_accrual = (
            (dwh_df['CREATED_AT_DAY'] >= data_accrue_start) &
            (dwh_df['CREATED_AT_DAY'] <= data_accrue_end) &
            (dwh_df['ORDER_COMPLETED'] == 1)
        )
        accrual_orders = dwh_df.loc[mask_accrual].copy()

        # Exclude any already present in JE (for safety)
        existing_orders = set(final_df['je_order_id'].dropna().astype(str))
        accrual_orders = accrual_orders.loc[~accrual_orders['MP_ORDER_ID'].astype(str).isin(existing_orders)].copy()

        # Label accruals
        accrual_orders['order_category'] = 'Accrual (Post-Statement)'
        accrual_orders['transaction_type'] = 'Order'
        accrual_orders['je_order_id'] = accrual_orders['MP_ORDER_ID']
        accrual_orders['je_total'] = accrual_orders['TOTAL_PAYMENT_WITH_TIPS_INC_VAT']
        accrual_orders['je_refund'] = 0

        # Append to final dataframe
        final_df = pd.concat([final_df, accrual_orders], ignore_index=True)

        print(f"✅ Added {len(accrual_orders):,} accrual orders from DWH.")
        print(f"📊 Final combined rows: {len(final_df):,}")
    else:
        print("🟢 No accrual period required — skipping accrual detection.")

    # =================================================================================================
    # Step 6 — Clean Data
    # =================================================================================================

    final_df['je_order_id'] = (final_df['je_order_id'].replace(r'^\s*$', np.nan, regex=True).replace('', np.nan))
    final_df['je_order_id'] = pd.to_numeric(final_df['je_order_id'], errors='coerce').astype('Int64') 
  
    # --- List all columns that should be treated as dates ---
    date_columns = ['je_date', 'CREATED_AT_DAY', 'DELIVERED_AT_DAY', 'OPS_DATE_DAY', 'CREATED_AT_WEEK', 'DELIVERED_AT_WEEK', 'OPS_DATE_WEEK', 'CREATED_AT_MONTH', 'DELIVERED_AT_MONTH', 'OPS_DATE_MONTH']

    # --- Apply the same cleaning logic to each existing column ---
    for col in date_columns:
        if col in final_df.columns:
            final_df[col] = final_df[col].replace(r'^\s*$', np.nan, regex=True)
            final_df[col] = pd.to_datetime(final_df[col], format='%d/%m/%y', errors='coerce').fillna(pd.to_datetime(final_df[col], format='%Y-%m-%d', errors='coerce'))
            final_df[col] = final_df[col].dt.strftime('%Y-%m-%d')
            final_df.loc[final_df[col].isna(), col] = np.nan
            print(f"🗓 Cleaned {col}: {final_df[col].notna().sum():,} valid dates")

    final_df['MP_ORDER_ID'] = np.where(final_df['MP_ORDER_ID'].isna(), final_df['je_order_id'], final_df['MP_ORDER_ID'])
    final_df.columns = final_df.columns.str.strip().str.lower().str.replace(' ', '_', regex=False).str.replace(r'[^\w_]', '', regex=True)

    mask = final_df['transaction_type'] == 'Order'
    final_df.loc[mask, 'matched_amount'] = np.where(final_df.loc[mask, 'je_total'].fillna(0).round(2) == final_df.loc[mask, 'total_payment_with_tips_inc_vat'].fillna(0).round(2), 'Matched', 'Not Matched')
    final_df.loc[mask, 'amount_variance'] = np.where(final_df.loc[mask, 'je_total'].fillna(0).round(2) == final_df.loc[mask, 'total_payment_with_tips_inc_vat'].fillna(0).round(2), 0, (final_df.loc[mask, 'je_total'].fillna(0).round(2) - final_df.loc[mask, 'total_payment_with_tips_inc_vat'].fillna(0).round(2)).round(2))

    mask = final_df['transaction_type'].isin(['Refund', 'Commission', 'Marketing'])
    final_df.loc[mask, 'matched_amount'] = 'Ignore'
    final_df.loc[mask, 'amount_variance'] = 0

    final_df = final_df[['gp_order_id', 'gp_order_id_obfuscated', 'mp_order_id', 'statement_start', 'transaction_type', 'order_category', 'matched_amount', 'amount_variance', 
                         'je_total', 'je_refund', 'location_name', 'order_vendor', 'vendor_group', 'order_completed', 'created_at_day', 'created_at_week', 'created_at_month', 
                         'post_promo_sales_inc_vat', 'delivery_fee_inc_vat', 'priority_fee_inc_vat', 'small_order_fee_inc_vat', 'mp_bag_fee_inc_vat', 'total_payment_inc_vat', 
                         'tips_amount', 'total_payment_with_tips_inc_vat', 'post_promo_sales_exc_vat', 'delivery_fee_exc_vat', 'priority_fee_exc_vat', 'small_order_fee_exc_vat', 
                         'mp_bag_fee_exc_vat', 'total_revenue_exc_vat', 'cost_of_goods_inc_vat', 'cost_of_goods_exc_vat',  'total_products', 'item_quantity_count_0', 
                         'item_quantity_count_5', 'item_quantity_count_20', 'total_price_exc_vat_0', 'total_price_exc_vat_5', 'total_price_exc_vat_20', 'total_price_inc_vat_0', 
                         'total_price_inc_vat_5', 'total_price_inc_vat_20']]
    
    final_df = final_df.sort_values(by = 'gp_order_id')
    
    # =================================================================================================
    # Step 7 — Save and Return Output Path
    # =================================================================================================
    output_path = provider_output_folder / f"{stmt_start_dt:%y.%m.%d} - {stmt_end_dt:%y.%m.%d} - JE Reconciliation.csv"
    final_df.to_csv(output_path, index=False)
    print(f"💾 Output written to: {output_path}")
    print("✅ Reconciliation completed successfully.")
    print("----------------------------------------------------------------------------------")

    return output_path