# Just Eat Orders-to-Cash Reconciliation

### Project Overview

This project automates the **Just Eat Orders-to-Cash reconciliation** process. It integrates Data Warehouse (DWH) exports, PDF statement parsing, and final reconciliation within a structured and GUI-driven workflow. The system ensures consistent data handling across multiple periods, supports audit trails, and outputs standardized reconciliation-ready CSVs.

---

## 🔧 Folder & File Structure

```
GoPuff/OrdersToCash/
│
├── main/
│   ├── M00_run_gui.py              # Launches the full 3-step reconciliation GUI
│   ├── M01_combined_dwh.py         # Step 1 – Combines DWH monthly CSV exports
│   ├── M02_process_mp_data.py      # Step 2 – Parses Just Eat PDFs and builds JE Order Level Detail
│   ├── M03_run_reconciliation.py   # Step 3 – Runs reconciliation logic between DWH + JE data
│
├── processes/
│   ├── P00_set_packages.py         # Centralised imports for all core/third-party libraries
│   ├── P01_set_file_paths.py       # Defines all folder paths and provider-specific directories
│   ├── P02_system_processes.py     # Shared system-level helper utilities
│   ├── P03_shared_functions.py     # Common logic for date overlap, coverage, etc.
│   ├── P04_static_lists.py         # Column rename maps and static configuration lists
│   ├── P05_gui_elements.py         # Tkinter GUI elements (Just Eat GUI interface)
│   ├── P06_class_items.py          # Data class definitions for metadata, financial summaries, etc.
│   ├── P07_module_configs.py       # Shared configuration templates and structured module objects
│
├── sql/                            # (Optional) Shared SQL scripts or warehouse queries
│
└── binary_files/                   # PyInstaller build output folders
```

---

## 🧩 Key Components

### 1️⃣ P00_set_packages.py

* **Purpose:** Central hub for all imports.
* Prevents duplication across scripts.
* Ensures consistent dependency loading for Pandas, PDFMiner, Tkinter, etc.
* *Third-party packages*: `pandas`, `numpy`, `pdfplumber`, `pdfminer.six`, `tkcalendar`, `snowflake-connector-python`.

### 2️⃣ P01_set_file_paths.py

* **Purpose:** Defines all input/output directories dynamically.
* Supports platform-agnostic paths (Windows/Mac/WSL).
* Example variables:

  ```python
  provider_csv_reference_folder = provider_csv_folder / '03 Reference'
  provider_pdf_reference_folder = provider_pdf_folder / '03 Reference'
  ```

### 3️⃣ M01_combined_dwh.py

* **Step 1** – Combines all monthly DWH exports into one master dataset.
* Cleans order IDs and standardises column naming via `DWH_COLUMN_RENAME_MAP`.
* Saves `je_dwh_all.csv` to the output folder.

### 4️⃣ M02_process_mp_data.py

* **Step 2** – Parses Just Eat statement PDFs.
* Extracts Orders, Refunds, Commission, and Marketing lines.
* Produces both per-PDF audit files and a consolidated `JE Order Level Detail.csv`.
* Performs internal validation (order count, total sales, payouts, etc.).

### 5️⃣ M03_run_reconciliation.py

* **Step 3** – Merges and reconciles DWH vs. Just Eat Order Level Detail.
* Flags matched/unmatched orders, identifies timing differences, and generates variance summaries.
* Produces the final accounting-ready reconciliation dataset.

---

## 🖥 GUI Overview (M00_run_gui.py)

The GUI provides a three-step workflow:

1. **Combine DWH Data** → Merges all DWH CSVs.
2. **Process PDFs** → Parses and builds statement-level data.
3. **Run Reconciliation** → Matches and validates results.

**Features:**

* Automatically sets previous month as default accounting period.
* Auto-syncs Just Eat statement coverage based on detected files.
* Includes a progress bar, status messages, and tooltips.

---

## 🧠 Code Style & Structure

* All modules follow consistent headers and sectioning.

* Imports and system setup always appear as:

  ```python
  # ====================================================================================================
  # 1. SYSTEM IMPORTS
  # ----------------------------------------------------------------------------------------------------
  import sys
  from pathlib import Path

  sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
  sys.dont_write_bytecode = True

  # ====================================================================================================
  # 2. PROJECT IMPORTS
  # ----------------------------------------------------------------------------------------------------
  from processes.P00_set_packages import *
  ```

* All functions include docstrings describing:

  * **Purpose**
  * **Args / Returns**
  * **Notes**

---

## ⚙️ Dependencies

To install all required packages in your virtual environment:

```bash
pip install pandas numpy pdfplumber pdfminer.six tkcalendar snowflake-connector-python
```

For Windows GUI builds (PyInstaller):

```bash
pip install pyinstaller
```

---

## 🧾 Output Files

| File Name                                             | Description                                     |
| ----------------------------------------------------- | ----------------------------------------------- |
| `je_dwh_all.csv`                                      | Combined monthly DWH dataset (Step 1)           |
| `<yy.mm.dd> - <yy.mm.dd> - JE Order Level Detail.csv` | Consolidated JE PDF data (Step 2)               |
| `RefundDetails.csv`                                   | Per-PDF refund/commission audit files (Step 2)  |
| `JE_Reconciliation_Final.csv`                         | Final matched/unmatched reconciliation (Step 3) |

---

## 🧱 Development Notes

* **All imports must go in P00_set_packages.py** (never directly in M or P scripts).
* Column names in DWH are now **lowercase**.
* No logic changes allowed without comment or docstring updates.
* Inline comments and docstrings must remain consistent across all modules.

---

## 👤 Author

**Gerry Pidgeon**
Created: November 2025
Project: *Just Eat Orders-to-Cash Reconciliation*

---

## 🧰 Future Enhancements

* Extend PDF parsing for multi-page statement anomalies.
* Add error logging and GUI progress tracking.
* Enable optional reconciliation report export (Excel or PDF).
* Integrate cross-provider mode (Deliveroo / Uber Eats).

---

> **This documentation is automatically aligned with the current codebase structure (P00–M03) and adheres to the internal commenting and layout conventions.**
