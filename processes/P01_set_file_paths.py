# ====================================================================================================
# P01_set_file_paths.py
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
# Root Folder Definitions
# ====================================================================================================
root_folder = Path(r'H:\Shared drives\Automation Projects\Accounting\Orders to Cash')
provider_root_folder  = root_folder / '05 Just Eat' # Change the provider here

# ====================================================================================================
# Subfolder Definitions
# ====================================================================================================
provider_csv_folder = provider_root_folder / '01 CSVs'
provider_csv_unprocessed_folder = provider_csv_folder / '01 To Process'
provider_csv_processed_folder = provider_csv_folder / '02 Processed'

provider_pdf_folder = provider_root_folder / '02 PDFs'
provider_pdf_unprocessed_folder = provider_pdf_folder / '01 To Process'
provider_pdf_processed_folder = provider_pdf_folder / '02 Processed'

provider_dwh_folder = provider_root_folder / '03 DWH'
provider_output_folder = provider_root_folder / '04 Consolidated Output'

# ====================================================================================================
# Ensure folders exist
# ====================================================================================================
for folder in [
    provider_root_folder,
    provider_csv_folder,
    provider_csv_unprocessed_folder,
    provider_csv_processed_folder,
    provider_pdf_folder,
    provider_pdf_unprocessed_folder,
    provider_pdf_processed_folder,
    provider_dwh_folder,
    provider_output_folder,
]:
    folder.mkdir(parents=True, exist_ok=True)
