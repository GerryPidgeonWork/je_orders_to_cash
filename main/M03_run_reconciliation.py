# ====================================================================================================
# M03_run_reconciliation.py
# ----------------------------------------------------------------------------------------------------
# Step 3 – Just Eat Orders-to-Cash Reconciliation
# ----------------------------------------------------------------------------------------------------
# Purpose:
# - Reconciles parsed Just Eat statement data against the combined DWH export.
# - Identifies matched orders, missing orders, refunds without DWH matches, and accruals.
# - Produces a date-stamped reconciliation CSV summarising all JE and DWH relationships.
# ----------------------------------------------------------------------------------------------------
# Inputs:
#   - je_dwh_all.csv (from Step 1)
#   - <yy.mm.dd> - <yy.mm.dd> - JE Order Level Detail.csv (from Step 2)
# Outputs:
#   - <yy.mm.dd> - <yy.mm.dd> - JE Reconciliation Results.csv
# ----------------------------------------------------------------------------------------------------
# Notes:
#   - Commission and Marketing rows are excluded from missing-in-DWH logic.
#   - Accruals are derived from completed DWH orders after the last JE statement period.
#   - All merges and filters are date-safe and GUI-friendly for threaded operation.
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
from processes.P00_set_packages import *
from processes.P01_set_file_paths import provider_output_folder
from processes.P04_static_lists import DWH_COLUMN_RENAME_MAP, JET_COLUMN_RENAME_MAP

# ====================================================================================================
# Helper – Find Matching JE Statement File
# ====================================================================================================

def find_matching_statement_file(output_folder: Path, start_date: str, end_date: str) -> Path:
    """
    Find the JE Statement file overlapping the selected GUI date range.

    The filename pattern follows:
        "YY.MM.DD - YY.MM.DD - JE Order Level Detail.csv"

    Returns:
        Path to the matching file if overlap exists, else raises FileNotFoundError.
    """
    gui_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    gui_end = datetime.strptime(end_date, "%Y-%m-%d").date()

    # Pattern to extract date ranges from filenames
    pattern = re.compile(
        r"(\d{2})\.(\d{2})\.(\d{2}) - (\d{2})\.(\d{2})\.(\d{2}) - JE Order Level Detail\.csv$",
        re.I,
    )

    for file in output_folder.glob("*JE Order Level Detail.csv"):
        m = pattern.search(file.name)
        if not m:
            continue
        start = datetime.strptime(f"20{m.group(1)}-{m.group(2)}-{m.group(3)}", "%Y-%m-%d").date()
        end = datetime.strptime(f"20{m.group(4)}-{m.group(5)}-{m.group(6)}", "%Y-%m-%d").date()

        # Include file if its range overlaps with GUI range
        if not (end < gui_start or start > gui_end):
            print(f"✅ Found matching JE Statement: {file.name}")
            return file

    # Raise friendly error if no overlapping file found
    raise FileNotFoundError(
        f"No JE Statement file found in '{output_folder}' overlapping {gui_start} → {gui_end}.\n"
        f"Please run Step 2 (Process PDFs) first."
    )

# ====================================================================================================
# Utility – Clean JE Order ID
# ====================================================================================================

def _clean_je_order_id(series: pd.Series) -> pd.Series:
    """Normalise order IDs (strip, remove decimals/non-numeric). Keeps blanks intact."""
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"[^0-9]", "", regex=True)
    )

# ====================================================================================================
# Main Reconciliation Function
# ====================================================================================================

def run_reconciliation(output_folder: Path, start_date: str, end_date: str):
    """
    Perform full reconciliation between Just Eat statement data and DWH export.

    Steps:
    1. Load both JE and DWH datasets.
    2. Standardise columns and clean order IDs.
    3. Merge JE ↔ DWH to classify matches, missing-in-DWH, and non-order rows.
    4. Identify missing JE orders and accruals based on GUI date range.
    5. Output a single, date-stamped reconciliation CSV.

    Returns:
        Path to the reconciliation output file (or warning message for GUI).
    """
    try:
        print("\n=================== JUST EAT RECONCILIATION ===================")

        # ------------------------------------------------------------------------------------------------
        # Step 0 — Load Required Files
        # ------------------------------------------------------------------------------------------------
        dwh_file = output_folder / "je_dwh_all.csv"
        if not dwh_file.exists():
            raise FileNotFoundError("DWH file not found — please run Step 1 (Combine DWH Data) first.")

        je_statement = find_matching_statement_file(output_folder, start_date, end_date)

        # Read data as strings for compatibility
        print(f"📂 Loading DWH Combined: {dwh_file.name}")
        dwh_df = pd.read_csv(dwh_file, dtype=str)
        print(f"📂 Loading JE Statement: {je_statement.name}")
        je_df = pd.read_csv(je_statement, dtype=str)

        gui_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        gui_end = datetime.strptime(end_date, "%Y-%m-%d").date()

        # ------------------------------------------------------------------------------------------------
        # Step 1 — Prepare DWH (Full Dataset, No Filter)
        # ------------------------------------------------------------------------------------------------
        dwh_df.rename(columns=DWH_COLUMN_RENAME_MAP, inplace=True, errors="ignore")

        # Parse gp_date column safely
        if "gp_date" in dwh_df.columns:
            dwh_df["gp_date"] = pd.to_datetime(dwh_df["gp_date"], errors="coerce").dt.date
        else:
            dwh_df["gp_date"] = pd.NaT

        # Clean JE order ID from DWH export
        dwh_df["je_order_id"] = _clean_je_order_id(dwh_df.get("je_order_id", pd.Series(dtype=str)))

        # ------------------------------------------------------------------------------------------------
        # Step 2 — Prepare JE (Full Dataset, No Filter)
        # ------------------------------------------------------------------------------------------------
        je_df.rename(columns=JET_COLUMN_RENAME_MAP, inplace=True, errors="ignore")
        je_df["je_order_id"] = _clean_je_order_id(je_df.get("je_order_id", pd.Series(dtype=str)))

        print(f"🧾 Loaded JE records: {len(je_df):,}")
        overlap_before = len(set(je_df["je_order_id"]) & set(dwh_df["je_order_id"]))
        print(f"🔍 Overlap (JE vs DWH) before any filtering: {overlap_before:,}")

        # ------------------------------------------------------------------------------------------------
        # Step 3 — Enrich JE with DWH Data
        # ------------------------------------------------------------------------------------------------
        merged = je_df.merge(
            dwh_df,
            on="je_order_id",
            how="left",
            suffixes=("", "_dwh")
        )

        # Tag records by reconciliation type
        nonorder_mask = merged["transaction_type"].isin(["Commission", "Marketing"])
        has_dwh_match = merged["order_completed"].notna()

        merged["status_flag"] = np.where(
            nonorder_mask, "NonOrder_JE",
            np.where(has_dwh_match, "Matched", "Missing_in_DWH")
        )

        # ------------------------------------------------------------------------------------------------
        # Step 3b — Remove any DWH data paired to non-order rows
        # ------------------------------------------------------------------------------------------------
        # Commission and Marketing lines should never carry DWH fields.
        dwh_cols = [col for col in merged.columns if col.endswith("_dwh") or col in dwh_df.columns]
        merged.loc[nonorder_mask, dwh_cols] = np.nan


        # Display example unmatched orders for diagnostics
        sample_unmatched = merged[(~nonorder_mask) & (~has_dwh_match)]
        if not sample_unmatched.empty:
            sample_ids = sample_unmatched["je_order_id"].dropna().unique()[:10]
            if len(sample_ids) > 0:
                print(f"⚠ Example unmatched JE order_ids: {', '.join(sample_ids)}")

        # ------------------------------------------------------------------------------------------------
        # Step 4 — Identify DWH Orders Missing from JE
        # ------------------------------------------------------------------------------------------------
        dwh_in_window = dwh_df[
            (dwh_df["gp_date"] >= gui_start) & (dwh_df["gp_date"] <= gui_end)
        ].copy()

        je_ids = set(je_df["je_order_id"])
        missing_from_je = dwh_in_window[
            (dwh_in_window["order_completed"] == "1")
            & (~dwh_in_window["je_order_id"].isin(je_ids))
            & (dwh_in_window["je_order_id"] != "")
        ].copy()
        missing_from_je["status_flag"] = "Missing_from_JE"
        print(f"📉 Missing from JE: {len(missing_from_je):,}")

        # ------------------------------------------------------------------------------------------------
        # Step 5 — Add Month-End Accruals (Post-Statement Orders)
        # ------------------------------------------------------------------------------------------------
        latest_statement_end = None
        if "statement_end" in je_df.columns:
            latest_statement_end = pd.to_datetime(je_df["statement_end"], errors="coerce").dt.date.max()

        accrual_orders = pd.DataFrame()
        if latest_statement_end and latest_statement_end < gui_end:
            accrual_orders = dwh_df[
                (dwh_df["order_completed"] == "1")
                & (dwh_df["gp_date"] > latest_statement_end)
                & (dwh_df["gp_date"] <= gui_end)
                & (~dwh_df["je_order_id"].isin(je_ids))
                & (dwh_df["je_order_id"] != "")
            ].copy()
            accrual_orders["status_flag"] = "Accrual_from_DWH"
            print(f"📊 Added {len(accrual_orders):,} accrual orders (post-statement).")

        # ------------------------------------------------------------------------------------------------
        # Step 6 — Combine All Results and Save
        # ------------------------------------------------------------------------------------------------
        final = pd.concat([merged, missing_from_je, accrual_orders], ignore_index=True, sort=False)

        out_name = f"{start_date.replace('-', '.')[2:]} - {end_date.replace('-', '.')[2:]} - JE Reconciliation Results.csv"
        out_path = output_folder / out_name
        final.to_csv(out_path, index=False, encoding="utf-8-sig")

        # ------------------------------------------------------------------------------------------------
        # Step 7 — Summary Output
        # ------------------------------------------------------------------------------------------------
        print(f"\n💾 Saved reconciliation file → {out_path}")
        print(f"Matched: {(final['status_flag'] == 'Matched').sum():,}")
        print(f"Missing in DWH (Orders/Refunds only): {(final['status_flag'] == 'Missing_in_DWH').sum():,}")
        print(f"Missing from JE: {(final['status_flag'] == 'Missing_from_JE').sum():,}")
        print(f"Accrual from DWH: {(final['status_flag'] == 'Accrual_from_DWH').sum():,}")
        print(f"Non-order JE rows (Commission/Marketing): {(final['status_flag'] == 'NonOrder_JE').sum():,}")
        print("===============================================================")

        return out_path

    # ------------------------------------------------------------------------------------------------
    # Error Handling (Friendly for GUI)
    # ------------------------------------------------------------------------------------------------
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return f"⚠ {str(e)}"

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("❌ Error during reconciliation. Please check the selected date range.")
        return "⚠ The selected period does not align with available statements. Please run the matching period."

# # ====================================================================================================
# # DIRECT EXECUTION (for testing)
# # ====================================================================================================
# if __name__ == "__main__":
#     # Allows standalone execution for testing purposes
#     run_reconciliation(provider_output_folder, "2025-09-01", "2025-09-30")
