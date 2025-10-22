# ====================================================================================================
# M01_combined_dwh.py
# ----------------------------------------------------------------------------------------------------
# Step 1 – Combine all monthly Just Eat DWH CSV exports into a single master dataset.
# ----------------------------------------------------------------------------------------------------
# Purpose:
# - Consolidates multiple monthly DWH extracts into one complete file for reconciliation.
# - Standardises column names using DWH_COLUMN_RENAME_MAP.
# - Cleans order IDs to ensure numeric consistency.
# - Outputs the result as 'je_dwh_all.csv' into the provider_output_folder.
# ----------------------------------------------------------------------------------------------------
# Inputs:
#   - All *.csv files in provider_dwh_folder
# Outputs:
#   - je_dwh_all.csv (saved to provider_output_folder)
# ----------------------------------------------------------------------------------------------------
# Notes:
#   - Keeps all columns exactly as found.
#   - Designed to be triggered via Step 1 in the GUI (M00_run_gui.py)
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
from processes.P01_set_file_paths import provider_dwh_folder, provider_output_folder
from processes.P04_static_lists import DWH_COLUMN_RENAME_MAP

# ====================================================================================================
# Combine Just Eat DWH CSV Files
# ====================================================================================================

def combine_je_dwh_files(dwh_folder: Path, output_folder: Path):
    """
    Combine all DWH CSV files into a single master CSV.
    Keeps all columns and applies standard renaming.
    """

    # Collect all CSV files in the DWH folder
    all_files = list(dwh_folder.glob("*.csv"))
    if not all_files:
        print(f"No CSV files found in folder: {dwh_folder}")
        return None

    combined_df = []

    # Load each CSV and append to list; skip invalid files gracefully
    for file in all_files:
        try:
            df = pd.read_csv(file, dtype=str)  # Load all as string to preserve formatting
            combined_df.append(df)
            print(f"Loaded: {file.name}")
        except Exception as e:
            print(f"⚠ Skipped {file.name}: {e}")

    # Abort if no valid files were read
    if not combined_df:
        print("No valid CSV files to combine.")
        return None

    # Combine all DataFrames vertically into one master DataFrame
    final_df = pd.concat(combined_df, ignore_index=True)

    # Rename columns using standardized mapping
    final_df.rename(columns=DWH_COLUMN_RENAME_MAP, inplace=True, errors="ignore")

    # Clean JE order ID – remove trailing '.0', spaces, and non-numeric characters
    final_df['je_order_id'] = (
        final_df['je_order_id']
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"[^0-9]", "", regex=True)
    )

    # Sort by gp_order_id descending for consistency
    final_df = final_df.sort_values('gp_order_id', ascending=False).reset_index(drop=True)

    # Define and save output path
    output_path = output_folder / "je_dwh_all.csv"
    final_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # Console output for confirmation
    print(f"\n✅ Combined {len(all_files)} files into {output_path}")
    print(f"✅ Total rows: {len(final_df):,}")
    return output_path

# ====================================================================================================
# Run Main Script
# ====================================================================================================
if __name__ == "__main__":
    # When run directly, combine all DWH CSVs and save to provider_output_folder
    combine_je_dwh_files(provider_dwh_folder, provider_output_folder)