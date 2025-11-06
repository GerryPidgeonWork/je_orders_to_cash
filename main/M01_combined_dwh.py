# ====================================================================================================
# M01_combined_dwh.py
# ----------------------------------------------------------------------------------------------------
# Step 1 – Combine all monthly Just Eat DWH CSV exports into a single master dataset.
# ----------------------------------------------------------------------------------------------------
# Purpose:
#   - Consolidate multiple monthly DWH extracts into one complete dataset for reconciliation.
#   - Standardise column names using DWH_COLUMN_RENAME_MAP (lowercase version).
#   - Clean order IDs to ensure numeric consistency.
#   - Output the result as 'je_dwh_all.csv' into the provider_output_folder.
#
# Inputs:
#   • All *.csv files in provider_dwh_folder
# Outputs:
#   • je_dwh_all.csv (saved to provider_output_folder)
#
# Notes:
#   - Keeps all columns exactly as found.
#   - Designed to be triggered via Step 1 in the GUI (M00_run_gui.py).
# ----------------------------------------------------------------------------------------------------
# Author:        Gerry Pidgeon
# Created:       2025-11-05
# Project:       Just Eat Orders-to-Cash Reconciliation
# ====================================================================================================


# ====================================================================================================
# 1. SYSTEM IMPORTS
# ----------------------------------------------------------------------------------------------------
# Add parent directory to sys.path so this module can import from "processes" packages.
# ====================================================================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True  # Prevents __pycache__ folders from being created


# ====================================================================================================
# 2. PROJECT IMPORTS
# ----------------------------------------------------------------------------------------------------
# Import all dependencies and shared settings from the centralized import hub.
# ====================================================================================================
from processes.P00_set_packages import *
from processes.P01_set_file_paths import provider_dwh_folder, provider_output_folder
from processes.P04_static_lists import DWH_COLUMN_RENAME_MAP


# ====================================================================================================
# 3. CORE FUNCTION — Combine DWH CSV Files
# ----------------------------------------------------------------------------------------------------
# Reads all DWH CSV exports, concatenates them, cleans IDs, and outputs a master CSV.
# ----------------------------------------------------------------------------------------------------
def combine_je_dwh_files(dwh_folder: Path, output_folder: Path):
    """
    Combine all DWH CSV files into a single master dataset for reconciliation.

    Args:
        dwh_folder (Path): Folder containing individual DWH CSV files.
        output_folder (Path): Folder to save the combined master CSV.

    Returns:
        Path | None: Path to the combined output CSV, or None if no files were processed.
    """

    # ------------------------------------------------------------------------------------------------
    # 1️⃣ Gather all DWH CSV files from the folder
    # ------------------------------------------------------------------------------------------------
    all_files = list(dwh_folder.glob("*.csv"))
    if not all_files:
        print(f"⚠ No CSV files found in folder: {dwh_folder}")
        return None

    combined_df_list = []

    # ------------------------------------------------------------------------------------------------
    # 2️⃣ Load each CSV safely and store in list
    # ------------------------------------------------------------------------------------------------
    for file in all_files:
        try:
            df = pd.read_csv(file, dtype=str)  # Load all as string to preserve formatting
            combined_df_list.append(df)
            print(f"📄 Loaded: {file.name}")
        except Exception as e:
            print(f"⚠ Skipped {file.name}: {e}")

    # Abort if no valid files were read
    if not combined_df_list:
        print("⚠ No valid CSV files to combine.")
        return None

    # ------------------------------------------------------------------------------------------------
    # 3️⃣ Combine all DataFrames vertically into one master DataFrame
    # ------------------------------------------------------------------------------------------------
    final_df = pd.concat(combined_df_list, ignore_index=True)

    # ------------------------------------------------------------------------------------------------
    # 4️⃣ Rename columns using standardized lowercase mapping
    # ------------------------------------------------------------------------------------------------
    # Note: The DWH files now have lowercase column names.
    # We apply the mapping only where names differ.
    final_df.rename(columns=DWH_COLUMN_RENAME_MAP, inplace=True, errors="ignore")

    # ------------------------------------------------------------------------------------------------
    # 5️⃣ Clean JE Order ID – remove trailing '.0', spaces, and non-numeric characters
    # ------------------------------------------------------------------------------------------------
    if "mp_order_id" in final_df.columns:
        final_df["mp_order_id"] = (
            final_df["mp_order_id"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .str.replace(r"[^0-9]", "", regex=True)
        )

    # ------------------------------------------------------------------------------------------------
    # 6️⃣ Sort by gp_order_id descending for consistency (if available)
    # ------------------------------------------------------------------------------------------------
    if "gp_order_id" in final_df.columns:
        final_df = final_df.sort_values("gp_order_id", ascending=False).reset_index(drop=True)

    # ------------------------------------------------------------------------------------------------
    # 7️⃣ Save the combined output
    # ------------------------------------------------------------------------------------------------
    output_path = output_folder / "je_dwh_all.csv"
    final_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------------------------------------------
    # 8️⃣ Log summary to console
    # ------------------------------------------------------------------------------------------------
    print(f"\n✅ Combined {len(all_files)} DWH files into: {output_path}")
    print(f"✅ Total rows in final dataset: {len(final_df):,}")

    return output_path


# ====================================================================================================
# 4. MAIN EXECUTION
# ----------------------------------------------------------------------------------------------------
# Enables standalone testing outside the GUI by running this script directly.
# ====================================================================================================
if __name__ == "__main__":
    combine_je_dwh_files(provider_dwh_folder, provider_output_folder)