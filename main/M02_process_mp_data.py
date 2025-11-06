# ====================================================================================================
# M02_process_mp_data.py
# ----------------------------------------------------------------------------------------------------
# Step 2 – Parse all Just Eat Statement PDFs and extract Orders, Refunds, Commission & Marketing
# ----------------------------------------------------------------------------------------------------
# Purpose:
#   - Reads all Just Eat statement PDFs (e.g. "25.09.01 - JE Statement.pdf") within a given date range.
#   - Extracts detailed transaction-level data including Orders, Refunds, Commission, and Marketing.
#   - Produces one consolidated CSV file suitable for reconciliation against the DWH export.
#
# Inputs:
#   - All PDFs matching "*JE Statement*.pdf" in provider_pdf_unprocessed_folder
#   - Optional date range (start_date, end_date) passed from GUI or CLI
#
# Outputs:
#   - One “RefundDetails.csv” file per processed PDF (for audit/debugging)
#   - One consolidated "<yy.mm.dd> - <yy.mm.dd> - JE Order Level Detail.csv" in provider_output_folder
#
# Notes:
#   - All amounts are stored as positive during parsing; refund/commission signs are applied later.
#   - Commission and Marketing totals are adjusted to include VAT (20% uplift).
#   - Statement file names are assumed to indicate Monday-start week (Mon → Sun).
#
# Author:         Gerry Pidgeon
# Created:        2025-11-05
# Project:        Just Eat Orders-to-Cash Reconciliation
# ====================================================================================================


# ====================================================================================================
# 1. SYSTEM IMPORTS
# ----------------------------------------------------------------------------------------------------
# Lightweight built-in modules for path handling and interpreter setup.
# ====================================================================================================
import sys              # Provides access to system-specific parameters and runtime config
from pathlib import Path      # Offers an object-oriented interface for filesystem paths

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

# Import the shared project-level package set (tkinter, pandas, pdfplumber, datetime, etc.)
from processes.P00_set_packages import *

# Import core path constants from P01
from processes.P01_set_file_paths import (
    provider_pdf_folder,
    provider_pdf_unprocessed_folder,
    provider_output_folder,
    provider_refund_folder,
)

# Import shared helper utilities from P03 (date/statement overlap logic)
from processes.P03_shared_functions import (
    statement_overlaps_file,
    get_je_statement_coverage,
)

# Import shared static column rename maps from P04
from processes.P04_static_lists import JET_COLUMN_RENAME_MAP


# ====================================================================================================
# 3. CONFIGURATION
# ----------------------------------------------------------------------------------------------------
# Central configuration for PDF I/O directories.
# These are mapped to the provider-specific folders declared in P01_set_file_paths.py.
# ====================================================================================================
PDF_FOLDER = provider_pdf_unprocessed_folder    # Source folder containing unprocessed JE statement PDFs
OUTPUT_FOLDER = provider_output_folder          # Destination folder for final consolidated CSVs
REFUND_FOLDER = provider_refund_folder          # Folder to hold per-statement refund detail CSVs (for audit)

# ====================================================================================================
# 4. HELPER FUNCTIONS – PDF TEXT PARSING & NORMALIZATION
# ----------------------------------------------------------------------------------------------------
# Low-level functions for extracting and cleaning text from the PDF statements.
# ====================================================================================================
def get_segment_text(pdf_path: Path) -> str:
    """
    Extracts the portion of text from a Just Eat statement PDF that lies between
    the markers "Commission to Just Eat" and "Subtotal".

    This section of the PDF typically contains:
        - Commission charges
        - Marketing deductions
        - Refunds and compensations
        - "Outside the scope of VAT" entries

    Args:
        pdf_path (Path):
            Full filesystem path to a single "Just Eat Statement" PDF file.

    Returns:
        str:
            The raw text segment found between "Commission to Just Eat" and "Subtotal".
            If either marker is missing, an empty string ("") is returned to ensure
            the calling code can continue safely without raising an exception.

    Notes:
        - Uses `pdfminer.six.extract_text()` (imported via P00_set_packages) to extract text.
        - Markers are searched sequentially; "Subtotal" must appear after "Commission to Just Eat".
        - Returning only this slice reduces downstream noise and parsing complexity.
    """

    # ------------------------------------------------------------------------------------------------
    # Step 1: Extract full raw text from the given PDF file.
    # ------------------------------------------------------------------------------------------------
    txt = extract_text(str(pdf_path))  # Read all text into a single string.

    # ------------------------------------------------------------------------------------------------
    # Step 2: Locate the start and end positions of the target section.
    # ------------------------------------------------------------------------------------------------
    start = txt.find("Commission to Just Eat")  # Beginning of section
    end = txt.find("Subtotal", start)          # End of section (search after start index)

    # ------------------------------------------------------------------------------------------------
    # Step 3: Handle missing markers gracefully.
    # ------------------------------------------------------------------------------------------------
    if start == -1 or end == -1:
        # Either marker not found — return empty string so the parser can skip this section.
        return ""

    # ------------------------------------------------------------------------------------------------
    # Step 4: Return only the extracted substring.
    # ------------------------------------------------------------------------------------------------
    return txt[start:end]

def extract_descriptions(segment_text: str):
    """
    Cleans and consolidates multi-line description entries found in the
    “Commission to Just Eat” → “Subtotal” section of a Just Eat statement PDF.

    Purpose:
        This function normalises the extracted text segment into a list of readable
        description lines that can later be paired with their corresponding monetary
        amounts. It resolves formatting irregularities caused by PDF text wrapping.

    Args:
        segment_text (str):
            The raw text segment between "Commission to Just Eat" and "Subtotal"
            as returned by `get_segment_text()`.

    Returns:
        list[str]:
            A list of cleaned, coherent description strings.
            Each entry represents one logical refund, commission, or compensation line.

    Notes:
        - Removes empty or whitespace-only lines.
        - Strips standalone monetary values (lines containing only £ amounts).
        - Merges wrapped lines (where a continuation starts with a lowercase letter).
        - Produces clean, human-readable text ready for regex-based extraction.
    """

    # ------------------------------------------------------------------------------------------------
    # Step 1: Guard clause — if no text was extracted, return an empty list immediately.
    # ------------------------------------------------------------------------------------------------
    if not segment_text:
        return []

    # ------------------------------------------------------------------------------------------------
    # Step 2: Normalise line formatting.
    # ------------------------------------------------------------------------------------------------
    # - Replace multiple whitespace characters with single spaces.
    # - Strip leading/trailing spaces from each line.
    # - Remove any blank lines created by PDF formatting.
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in segment_text.splitlines()]
    lines = [ln for ln in lines if ln]  # Keep only non-empty lines.

    # ------------------------------------------------------------------------------------------------
    # Step 3: Identify and remove standalone monetary lines (e.g., "£123.45").
    # ------------------------------------------------------------------------------------------------
    money_re = re.compile(r'[–\-]?\s*£\s*[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}')
    # Remove full lines that only contain a £-amount and strip inline residuals.
    lines = [money_re.sub('', ln).strip() for ln in lines if not money_re.fullmatch(ln)]

    # ------------------------------------------------------------------------------------------------
    # Step 4: Merge continuation lines caused by PDF word wrapping.
    # ------------------------------------------------------------------------------------------------
    # - If a line starts with a capital letter → treat as new entry.
    # - If it starts with lowercase → append to previous line.
    merged = []
    for ln in lines:
        if not merged:
            merged.append(ln)
            continue
        if ln[0].isupper():
            merged.append(ln)
        else:
            merged[-1] += " " + ln  # Join continuation line (lowercase) to previous entry.

    # ------------------------------------------------------------------------------------------------
    # Step 5: Final cleanup to remove redundant spacing and empty items.
    # ------------------------------------------------------------------------------------------------
    merged = [re.sub(r'\s{2,}', ' ', s).strip() for s in merged]
    return [s for s in merged if s]  # Return final cleaned description list.

def extract_amounts(segment_text: str):
    """
    Extracts all monetary (£) amounts from the provided text segment, handling
    negative values, en-dashes, and line-break irregularities often found in PDFs.

    Purpose:
        This isolates all pound values from the Commission/Refund section of
        a Just Eat statement, returning them as signed floats for arithmetic use.

    Args:
        segment_text (str):
            The raw text segment extracted between "Commission to Just Eat" and "Subtotal".

    Returns:
        list[float]:
            A list of numeric £ amounts, including negatives (e.g., [-5.20, 2.30, ...]).
            Returns an empty list if no matches are found.

    Notes:
        - Handles typographic en-dashes (–) as standard minus signs.
        - Corrects broken lines such as "- \n£12.34" → "-£12.34".
        - Supports numbers with commas as thousand separators.
        - Each matched £ value is converted to a float with the correct sign.
    """

    # ------------------------------------------------------------------------------------------------
    # Step 1: Guard clause — if no text is provided, return an empty list.
    # ------------------------------------------------------------------------------------------------
    if not segment_text:
        return []

    # ------------------------------------------------------------------------------------------------
    # Step 2: Normalise text to make regex parsing consistent across PDF variants.
    # ------------------------------------------------------------------------------------------------
    segment_text = (
        segment_text
        .replace('–', '-')      # Replace en dash (–) with standard hyphen (-)
        .replace('- \n£', '-£')  # Fix cases where dash and £ are separated by line breaks
        .replace('-\n£', '-£')   # Handle tighter variant
    )

    # ------------------------------------------------------------------------------------------------
    # Step 3: Define the regex pattern for monetary amounts.
    # ------------------------------------------------------------------------------------------------
    # Pattern breakdown:
    # ([\-]?)                   → optional minus sign (Group 1)
    # \s*£\s* → pound sign (with optional spaces)
    # ([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}) → numeric part (supports commas + 2 decimals) (Group 2)
    money_pattern = re.compile(r'([\-]?)\s*£\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})')

    # ------------------------------------------------------------------------------------------------
    # Step 4: Iterate over all matches and convert each to a float with correct sign.
    # ------------------------------------------------------------------------------------------------
    results = []
    for m in money_pattern.finditer(segment_text):
        sign = -1 if m.group(1) == '-' else 1          # Apply negative if prefixed with '-'
        value = float(m.group(2).replace(",", "")) * sign  # Remove commas, cast to float
        results.append(value)

    # ------------------------------------------------------------------------------------------------
    # Step 5: Return list of extracted £ amounts (floats).
    # ------------------------------------------------------------------------------------------------
    return results

def parse_reason_and_order(desc: str):
    """
    Parses a single description line from a Just Eat PDF statement to extract:
    - The refund or compensation reason, and
    - The associated Just Eat order number.

    Purpose:
        Each line within the “Commission to Just Eat” section often includes an
        explanation of the adjustment (e.g., customer compensation, recook, or
        cancelled order). This helper standardises and extracts key fields to make
        downstream reconciliation easier.

    Args:
        desc (str):
            A single text line describing a refund or compensation entry,
            typically one of several lines returned by `extract_descriptions()`.

    Returns:
        tuple[str, str]:
            A tuple containing:
                - reason (str): Description of the refund or compensation cause.
                - order (str): The Just Eat order number (numeric string).
            Returns empty strings ("", "") if no known format matches.

    Notes:
        - Supports multiple known statement formats:
            1️⃣ "Customer compensation for Missing Item query 123456"
            2️⃣ "Restaurant Comp – Cancelled Order – 123456"
            3️⃣ "Order ID: 123456 - Partner Compensation Recook (Outside the scope of VAT)"
        - Can be extended easily with new regex patterns for emerging statement types.
    """
    # ------------------------------------------------------------------------------------------------
    # Step 1: Initialise default values for return (empty strings).
    # ------------------------------------------------------------------------------------------------
    reason, order = "", ""

    # ------------------------------------------------------------------------------------------------
    # Step 2: Pattern 1 – Customer Compensation format
    # Example:
    #   "Customer compensation for Missing Item query 123456"
    # Extracts:
    #   - reason → "Missing Item"
    #   - order  → "123456"
    # ------------------------------------------------------------------------------------------------
    m1 = re.search(r"Customer compensation for (.*?) query (\d+)", desc, re.IGNORECASE)
    if m1:
        return m1.group(1).strip(), m1.group(2).strip()

    # ------------------------------------------------------------------------------------------------
    # Step 3: Pattern 2 – Restaurant Comp (Cancelled Order)
    # Example:
    #   "Restaurant Comp – Cancelled Order – 123456"
    # Extracts:
    #   - reason → "Restaurant Comp - Cancelled Order"
    #   - order  → "123456"
    # ------------------------------------------------------------------------------------------------
    m2 = re.search(r"Restaurant\s+Comp\s*[-–]?\s*Cancelled\s+Order\s*[-–\s]*?(\d+)", desc, re.IGNORECASE)
    if m2:
        return "Restaurant Comp - Cancelled Order", m2.group(1).strip()

    # ------------------------------------------------------------------------------------------------
    # Step 4: Pattern 3 – Partner Compensation Recook
    # Example:
    #   "Order ID: 123456 - Partner Compensation Recook (Outside the scope of VAT)"
    # Extracts:
    #   - reason → "Partner Compensation Recook"
    #   - order  → "123456"
    # ------------------------------------------------------------------------------------------------
    m3 = re.search(r"Order\s*ID[:\s]*([0-9]+)\s*[-–]\s*Partner\s+Compensation\s+Recook", desc, re.IGNORECASE)
    if m3:
        return "Partner Compensation Recook", m3.group(1).strip()

    # ------------------------------------------------------------------------------------------------
    # Step 5: Fallback — no known format matched.
    # Return empty placeholders for safe unpacking by caller.
    # ------------------------------------------------------------------------------------------------
    return reason, order

def build_dataframe(descriptions, amounts):
    """
    Combines parallel lists of text descriptions and monetary amounts into a
    structured pandas DataFrame, enriched with parsed metadata (reason, order, VAT flag).

    Purpose:
        This function takes the cleaned refund/commission descriptions and
        the extracted £ values from a Just Eat PDF statement, pairs them up,
        and builds a structured, analysis-ready dataset.

    Args:
        descriptions (list[str]):
            A list of cleaned description lines returned by `extract_descriptions()`.
        amounts (list[float]):
            A list of corresponding £ values returned by `extract_amounts()`.

    Returns:
        pandas.DataFrame:
            A structured table with the following columns:
                - description (str): Original text entry from the PDF.
                - amount (float): Monetary value (£), positive or negative.
                - reason (str): Parsed refund/compensation reason.
                - order_number (str): Extracted Just Eat order ID (if present).
                - outside_scope (bool): True if entry includes “Outside the scope of VAT”.

    Notes:
        - Pairs only up to the smaller list length (safe handling of mismatched input sizes).
        - Enriches data with refund reason and order number using `parse_reason_and_order()`.
        - Serves as an intermediate dataset for downstream reconciliation and validation.
    """

    # ------------------------------------------------------------------------------------------------
    # Step 1: Match pairs safely up to the smaller of the two list lengths.
    # ------------------------------------------------------------------------------------------------
    n = min(len(descriptions), len(amounts))

    # ------------------------------------------------------------------------------------------------
    # Step 2: Create a structured list of row dictionaries to prepare for DataFrame creation.
    # ------------------------------------------------------------------------------------------------
    data = []
    for i in range(n):
        desc = descriptions[i]
        amt = amounts[i]

        # Parse semantic metadata from each description.
        reason, order = parse_reason_and_order(desc)

        # Build structured record for each entry.
        data.append({
            "description": desc,                    # Original text line
            "amount": amt,                          # £ value as float (can be negative)
            "reason": reason,                       # Parsed reason (e..g., "Missing Item")
            "order_number": order,                  # Extracted JE order ID (if found)
            "outside_scope": "Outside the scope of VAT" in desc    # Boolean VAT exclusion flag
        })

    # ------------------------------------------------------------------------------------------------
    # Step 3: Convert the list of dictionaries to a pandas DataFrame for easier manipulation.
    # ------------------------------------------------------------------------------------------------
    return pd.DataFrame(data)


# ====================================================================================================
# 5. MAIN PARSING FUNCTION
# ====================================================================================================
def run_je_parser(pdf_folder: Path, output_folder: Path, start_date: str = None, end_date: str = None):
    """
    Master parser for all Just Eat (JE) weekly PDF statements.

    Purpose:
        Executes Step 2 of the Orders-to-Cash workflow by parsing all JE statement
        PDFs within a selected date range and consolidating their data into a single,
        structured CSV file.

    Workflow Summary:
        1️⃣ Identify all PDFs matching "*JE Statement*.pdf" in the given folder.
        2️⃣ Filter PDFs to only those overlapping the accounting (GUI-selected) period.
        3️⃣ Parse Orders, Refunds, Commission, and Marketing details from each valid PDF.
        4️⃣ Validate parsed totals against the PDF’s printed summary fields.
        5️⃣ Combine all parsed data into a master CSV output.

    Args:
        pdf_folder (Path):
            Folder containing weekly Just Eat statement PDFs.
        output_folder (Path):
            Destination folder for the final consolidated CSV file.
        start_date (str, optional):
            Inclusive start date (YYYY-MM-DD) for filtering statements.
        end_date (str, optional):
            Inclusive end date (YYYY-MM-DD) for filtering statements.

    Returns:
        str | Path:
            - Returns a message string if no PDFs were processed.
            - Returns the Path to the consolidated CSV file if successful.

    Notes:
        - The filename date (YY.MM.DD) is always the statement’s start Monday.
        - Commission and Marketing are adjusted for VAT uplift (+20%).
        - All financial values remain positive (signs applied during aggregation).
    """

    # =================================================================================================
    # STEP 0: Console banner for readability when script runs standalone or via GUI
    # =================================================================================================
    print("\n=================== JustEat PARSER ===================")

    # -------------------------------------------------------------------------------------------------
    # STEP 1: Convert date-picker strings (YYYY-MM-DD) to Python date objects
    # -------------------------------------------------------------------------------------------------
    # These are used to check whether a given PDF’s statement period overlaps the GUI-selected range.
    gui_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    gui_end   = datetime.strptime(end_date, "%Y-%m-%d").date()   if end_date   else None

    print(f"🧭 Running JE Parser for range: {start_date} → {end_date}")

    # -------------------------------------------------------------------------------------------------
    # STEP 2: Locate all candidate PDF files
    # -------------------------------------------------------------------------------------------------
    # JE statement filenames always follow a consistent pattern:
    #   YY.MM.DD - JE Statement.pdf
    # A simple wildcard search reliably captures all files in the folder.
    pdf_files = sorted(pdf_folder.glob("*JE Statement*.pdf"))

    # Guard clause — exit early if the folder is empty or misconfigured.
    if not pdf_files:
        raise FileNotFoundError(f"No matching PDFs found in: {pdf_folder}")

    # Console summary
    print(f"📂 Found {len(pdf_files)} total PDF(s) to check.")

    # =================================================================================================
    # STEP 3: Identify PDF files that overlap the selected date range
    # =================================================================================================
    
    # -------------------------------------------------------------------------------------------------
    # STEP 3.1: Get the broad date coverage from all available PDF filenames
    # -------------------------------------------------------------------------------------------------
    # Purpose:
    #   - Identify which PDF statements (weekly Monday → Sunday) overlap with the selected
    #     accounting period.
    #   - This uses get_je_statement_coverage() to detect the earliest and latest Mondays
    #     covered by *any* PDFs within the given range, informing the output filename.
    # -------------------------------------------------------------------------------------------------
    first_monday, last_monday = get_je_statement_coverage(
        pdf_folder,
        gui_start,
        gui_end
    )

    # Guard clause — if no overlapping statements were detected, stop execution.
    if not first_monday or not last_monday:
        raise FileNotFoundError(
            f"No JE statements overlap {gui_start} → {gui_end} in {pdf_folder}"
        )

    print(f"📅 Broadest JE statement coverage in range: {first_monday} → {last_monday}")

    # -------------------------------------------------------------------------------------------------
    # STEP 3.2: Filter the complete PDF list to only those overlapping the GUI range
    # -------------------------------------------------------------------------------------------------
    if gui_start and gui_end:
        print(f"🧭 Limiting processing to PDFs overlapping {gui_start} → {gui_end}")

    valid_files = [] # Create an empty list for filtered file paths

    # Loop through all JE statement PDFs in chronological order
    for pdf_path in pdf_files:
        # Extract the date embedded in the filename (YY.MM.DD)
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", pdf_path.name)
        if not m:
            print(f"⏭ Skipped {pdf_path.name} (could not parse date from filename)")
            continue

        # Convert extracted filename date into a Monday date object
        start = datetime.strptime(f"20{m.group(1)}-{m.group(2)}-{m.group(3)}", "%Y-%m-%d").date()
        end = start + timedelta(days=6)  # Monday → Sunday (inclusive week)

        # Use helper to test whether statement overlaps with GUI-selected period
        if statement_overlaps_file(str(start), str(end), str(gui_start), str(gui_end)):
            valid_files.append(pdf_path)
        else:
            # This check is based on filename only; a final check is done on PDF-header dates
            pass

    # Replace full list with filtered subset
    pdf_files = valid_files

    # Summary output
    print(f"📄 {len(pdf_files)} PDF(s) selected for processing.")
    if not pdf_files:
         print("⚠ No PDFs matched the date range.")
         return "⚠ No matching PDF statements found for this date range. Please check your selected period."


    # =================================================================================================
    # STEP 4: Loop through each valid PDF and extract all required details
    # =================================================================================================
    # Each PDF is parsed independently, producing a structured DataFrame that will later be merged.
    all_rows = []  # Collects DataFrames for final consolidation

    for pdf_path in pdf_files:
        print(f"\n📄 Processing: {pdf_path.name}")

        # ---------------------------------------------------------------------------------------------
        # STEP 4.1 – Read and flatten all text content from the PDF
        # ---------------------------------------------------------------------------------------------
        # Purpose:
        #   - Some JE statement content (e.g. totals, headings) spans multiple pages.
        #   - pdfplumber reads text page-by-page; we merge into a single multiline string for parsing.
        # ---------------------------------------------------------------------------------------------
        with pdfplumber.open(pdf_path) as pdf:
            full_text_pages = [p.extract_text() or "" for p in pdf.pages]
        full_text = "\n".join(full_text_pages)

        # ---------------------------------------------------------------------------------------------
        # STEP 4.2 – Detect the statement period (start and end dates) printed in the PDF header
        # ---------------------------------------------------------------------------------------------
        # Purpose:
        #   - JE uses varying header formats to show the statement range (Mon → Sun).
        #   - We attempt multiple regex patterns to capture all variants.
        # ---------------------------------------------------------------------------------------------
        period_patterns = [
            re.compile(
                r"(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})\s*[-–to]+\s*(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})",
                re.I
            ),
            re.compile(
                r"(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–to]+\s*(\d{1,2}/\d{1,2}/\d{2,4})",
                re.I
            ),
        ]

        m_period = None

        # Loop through pages and patterns until a match is found
        for page_text in full_text_pages:
            for pat in period_patterns:
                m_period = pat.search(page_text)
                if m_period:
                    break
            if m_period:
                break

        # Extract matched strings (if found)
        statement_start_raw = m_period.group(1) if m_period else None
        statement_end_raw   = m_period.group(2) if m_period else None

        # Define an internal helper to handle multiple date formats gracefully
        def parse_date_safe(date_str):
            """
            Convert various date formats to datetime.date safely.
            Returns None if parsing fails.
            """
            if not date_str:
                return None
            for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d/%m/%y"):
                try:
                    return datetime.strptime(date_str.strip(), fmt).date()
                except Exception:
                    continue
            return None

        # Parse the detected raw header date strings
        statement_start = parse_date_safe(statement_start_raw)
        statement_end   = parse_date_safe(statement_end_raw)

        # Guard clause — skip if header dates can’t be read
        if not statement_start or not statement_end:
            print("   ⚠ Could not extract statement period from PDF header → skipping file.")
            continue

        # ---------------------------------------------------------------------------------------------
        # STEP 4.3 – Extract header-level summary metrics for validation
        # ---------------------------------------------------------------------------------------------
        # Purpose:
        #   - Capture top-line figures printed in the PDF header for later comparison
        #     against our parsed totals (sanity check).
        #   - Includes:
        #         • Number of Orders
        #         • Total Sales
        #         • “You will receive” payout amount
        #         • Payment date
        # ---------------------------------------------------------------------------------------------
        orders_count_pat  = re.compile(r"Number\s+of\s+orders\s+([\d,]+)", re.I)
        total_sales_pat   = re.compile(r"Total\s+sales.*?£\s*([\d,]+\.\d{2})", re.I | re.S)
        you_receive_pat   = re.compile(r"You\s+will\s+receive.*?£\s*([\d,]+\.\d{2})", re.I | re.S)
        payment_date_pat  = re.compile(r"paid\s+on\s+(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})", re.I)

        # Run regex searches over the flattened text
        m_orders  = orders_count_pat.search(full_text)
        m_sales   = total_sales_pat.search(full_text)
        m_recv    = you_receive_pat.search(full_text)
        m_payment = payment_date_pat.search(full_text)

        # Extract matched values, applying safe type conversions
        reported_order_count = int(m_orders.group(1).replace(",", "")) if m_orders else None
        reported_total_sales   = float(m_sales.group(1).replace(",", "")) if m_sales else None
        reported_you_receive   = float(m_recv.group(1).replace(",", "")) if m_recv else None
        payment_date_raw       = m_payment.group(1) if m_payment else None

        # Attempt to parse payment date; tolerate missing or malformed formats
        try:
            payment_date = datetime.strptime(payment_date_raw, "%d %b %Y").date() if payment_date_raw else None
        except Exception:
            payment_date = None

        # ---------------------------------------------------------------------------------------------
        # STEP 4.4 – Final guard: skip statements that fall entirely outside the GUI range
        # ---------------------------------------------------------------------------------------------
        # Purpose:
        #   - This is a more robust check using the *header dates* from within the PDF.
        #   - Prevents parsing PDFs that lie completely outside the accounting
        #     window selected in the GUI (e.g., if GUI is Oct, skip PDF for 2025-09-01).
        # ---------------------------------------------------------------------------------------------
        if gui_start and gui_end:
            # Check for non-overlap: (End is before GUI start) OR (Start is after GUI end)
            overlaps = not (statement_end < gui_start or statement_start > gui_end)
            if not overlaps:
                print(f"   ⏭ Skipped (statement {statement_start} → {statement_end} is outside selected range).")
                continue

        # =================================================================================================
        # STEP 5: Extract individual ORDER lines
        # =================================================================================================
        # Purpose:
        #   - Identify each individual order entry from the tabular section of the PDF.
        #   - Each line includes date, order ID, type (e.g. “Order” or “Refund”), and £ value.
        #   - This forms the foundation for order-level reconciliation with DWH data.
        # -------------------------------------------------------------------------------------------------
        line_prefix  = re.compile(r"^\s*\d+\s+(\d{2}/\d{2}/\d{2})\s+(\d+)\s+([A-Za-z/&\-]+)\s+(.*)$", re.M)
        money_finder = re.compile(r"[£]\s*([\d.,]+)")

        orders_data  = []  # Temporary list to hold all order dictionaries before DataFrame conversion

        for m in line_prefix.finditer(full_text):
            # Extract components of each order line
            date, order_id, order_type, tail = m.groups()

            # Identify all £ amounts that appear on the same line
            amts = money_finder.findall(tail)
            if not amts:
                continue  # Skip lines with no valid monetary values

            # The last £ value is typically the total for that order
            total = float(amts[-1].replace(",", ""))

            # Append structured order entry to list
            orders_data.append({
                "order_id": order_id,
                "date": date,
                "order_type": order_type,
                "total_incl_vat": total,
                "refund_amount": 0.0,
                "type": "Order",
                "source_file": pdf_path.name,
                "statement_start": statement_start,
                "statement_end": statement_end,
                "payment_date": payment_date,
            })

        # Convert the list of dicts → pandas DataFrame
        orders_df            = pd.DataFrame(orders_data)
        parsed_order_count = len(orders_df)
        parsed_total_sales = round(orders_df["total_incl_vat"].sum(), 2)

        # =================================================================================================
        # STEP 6: Extract Refund, Commission and Marketing details
        # =================================================================================================
        # Purpose:
        #   - Parse and structure the “Commission to Just Eat” section beneath the table.
        #   - This section contains refunds, commission, and marketing deductions.
        # -------------------------------------------------------------------------------------------------
        seg          = get_segment_text(pdf_path)        # Extract text block between “Commission” and “Subtotal”
        descriptions = extract_descriptions(seg)            # Clean multi-line refund/commission descriptions
        amounts      = extract_amounts(seg)                 # Extract all £ amounts within that section
        df_full      = build_dataframe(descriptions, amounts) # Combine into structured tabular format

        # -------------------------------------------------------------------------------------------------
        # STEP 6.1 – Derive grouped totals for Commission and Marketing
        # -------------------------------------------------------------------------------------------------
        # Identify text entries related to commission and marketing.
        # Commission lines contain the word “Commission”; marketing are other untitled deductions.
        commission_sum = df_full[
            df_full["description"].str.contains("Commission", case=False, na=False)
        ]["amount"].sum()

        marketing_sum = df_full[
            (~df_full["description"].str.contains("Commission", case=False, na=False)) &
            (df_full["reason"].eq(""))  # Assumes marketing lines have no parsed 'reason'
        ]["amount"].sum()

        # Apply 20% VAT uplift and negative sign (to treat as cost deductions)
        commission_incl_vat = round(commission_sum * 1.20 * -1, 2)
        marketing_incl_vat  = round(marketing_sum  * 1.20 * -1, 2)

        # -------------------------------------------------------------------------------------------------
        # STEP 6.2 – Save per-statement refund-detail file (for audit / debugging)
        # -------------------------------------------------------------------------------------------------
        # Purpose:
        #   - Each processed PDF generates its own RefundDetails.csv
        #   - Provides full transparency of parsed refund/commission/marketing data.
        # -------------------------------------------------------------------------------------------------
        if not df_full.empty:
            refund_csv_path = REFUND_FOLDER / f"{pdf_path.stem}_RefundDetails.csv"

            # Attach metadata columns before export
            (
                df_full
                .assign(
                    source_file=pdf_path.name,
                    statement_start=statement_start,
                    statement_end=statement_end,
                    payment_date=payment_date
                )
                .to_csv(refund_csv_path, index=False)
            )

            print(f"   💾 Saved refund detail file → {refund_csv_path.name}")

        # =================================================================================================
        # STEP 7: Aggregate refunds by order (for later joining to order lines)
        # =================================================================================================
        # Filter for "Outside the scope of VAT" (which are true refunds) and group by order ID
        if not df_full.empty:
            df_refunds_by_order = (
                df_full[df_full["outside_scope"] & df_full["order_number"].ne("")]
                .groupby("order_number", as_index=False)["amount"]
                .sum()
                .rename(columns={"order_number": "order_id"})
            )
        else:
            df_refunds_by_order = pd.DataFrame(columns=["order_id", "amount"])

        # =================================================================================================
        # STEP 8: Combine Orders + Refunds + Commission + Marketing
        # =================================================================================================
        # Build a unified DataFrame for the current PDF by concatenating multiple components.
        # Each “type” (Order / Refund / Commission / Marketing) represents one row category.
        order_rows    = orders_df.copy()
        combined_rows = [order_rows]  # Start list of DataFrames to concatenate later

        # ---------------------------------------------------------------------------------------------
        # STEP 8.1 – Add Refund rows if they exist
        # ---------------------------------------------------------------------------------------------
        if not df_refunds_by_order.empty:
            refund_rows = df_refunds_by_order.copy()

            # Refunds are stored as positive in the statement but must be negative for netting logic.
            refund_rows["refund_amount"] = refund_rows["amount"].apply(lambda x: -x)
            refund_rows["total_incl_vat"] = 0.0
            refund_rows["type"] = "Refund"
            refund_rows["date"] = statement_start
            refund_rows["order_type"] = "Refund"
            refund_rows["source_file"] = pdf_path.name
            refund_rows["statement_start"] = statement_start
            refund_rows["statement_end"] = statement_end
            refund_rows["payment_date"] = payment_date
            refund_rows.drop(columns=["amount"], inplace=True)
            combined_rows.append(refund_rows)

        # ---------------------------------------------------------------------------------------------
        # STEP 8.2 – Add Commission summary row
        # ---------------------------------------------------------------------------------------------
        # A single aggregated line ensures the weekly deduction is captured in the dataset.
        if commission_sum != 0:
            combined_rows.append(pd.DataFrame([{
                "order_id": "",
                "date": statement_start,
                "order_type": "Commission",
                "refund_amount": 0.0,
                "type": "Commission",
                "total_incl_vat": commission_incl_vat,
                "source_file": pdf_path.name,
                "statement_start": statement_start,
                "statement_end": statement_end,
                "payment_date": payment_date
            }]))

        # ---------------------------------------------------------------------------------------------
        # STEP 8.3 – Add Marketing summary row
        # ---------------------------------------------------------------------------------------------
        # A single aggregated line ensures the weekly deduction is captured in the dataset.
        if marketing_sum != 0:
            combined_rows.append(pd.DataFrame([{
                "order_id": "",
                "date": statement_start,
                "order_type": "Marketing",
                "refund_amount": 0.0,
                "type": "Marketing",
                "total_incl_vat": marketing_incl_vat,
                "source_file": pdf_path.name,
                "statement_start": statement_start,
                "statement_end": statement_end,
                "payment_date": payment_date
            }]))

        # Combine all per-statement components into a single DataFrame
        combined_df = pd.concat(combined_rows, ignore_index=True)
        all_rows.append(combined_df)

        # =================================================================================================
        # STEP 9: Per-statement validation summary
        # =================================================================================================
        # Purpose:
        #   - Cross-check parsed totals (orders, refunds, commission, marketing)
        #     against the official summary values printed in the statement header.
        #   - Highlights discrepancies between parsed and reported amounts to help
        #     identify OCR or parsing issues before consolidation.
        # -------------------------------------------------------------------------------------------------
        refund_sum_lines        = df_refunds_by_order["amount"].sum() if not df_refunds_by_order.empty else 0.0
        subtotal_all            = df_full["amount"].sum() if not df_full.empty else 0.0
        vat_deductions          = df_full.loc[~df_full["outside_scope"], "amount"].sum() if not df_full.empty else 0.0
        refund_total_calc       = subtotal_all - vat_deductions # This is the "Subtotal" minus VAT-able items
        refund_sum_lines_signed = -refund_sum_lines  # Flip sign for reconciliation logic

        # Derive “You will receive” figure by summing all parsed components
        derived_receive = None
        diff_receive    = None
        if reported_total_sales is not None and reported_you_receive is not None:
            derived_receive = (
                reported_total_sales
                + refund_sum_lines_signed  # This is a negative value
                + commission_incl_vat      # This is a negative value
                + marketing_incl_vat       # This is a negative value
            )
            diff_receive = round(derived_receive - reported_you_receive, 2)

        # Console output for quick validation of statement accuracy
        print(f"   Header Orders: {reported_order_count:,} | Parsed Orders: {parsed_order_count:,} → Variance: {parsed_order_count - (reported_order_count or 0):+}")
        print(f"   Header Total Sales: £{reported_total_sales:,.2f} | Parsed Total Sales: £{parsed_total_sales:,.2f} → Variance: £{parsed_total_sales - (reported_total_sales or 0):+.2f}")
        print(f"   Header Refunds: £{refund_total_calc:,.2f} | Parsed Refunds: £{refund_sum_lines_signed:,.2f} → Variance: £{refund_sum_lines_signed + refund_total_calc:+.2f}")
        print(f"   Header Payout: £{reported_you_receive:,.2f} | Parsed Payout: £{derived_receive:,.2f} → Variance: £{diff_receive:+.2f}")
        print(f"   Commission + VAT uplift: £{commission_incl_vat:,.2f}")
        print(f"   Marketing + VAT uplift:  £{marketing_incl_vat:,.2f}")
        if reported_you_receive is not None:
            print(f"   GoPuff will receive: £{reported_you_receive:,.2f}")
        if payment_date:
            print(f"   💰 Payment Date: {payment_date.strftime('%d %b %Y')}")

    # =================================================================================================
    # STEP 10: Final merge and save consolidated output
    # =================================================================================================
    # Purpose:
    #   - Combine all per-PDF DataFrames into one consolidated “Order Level Detail” CSV.
    #   - Applies consistent field naming, date sorting, and file naming conventions.
    # -------------------------------------------------------------------------------------------------
    if not all_rows:
        # This check is now redundant due to the check in Step 3.2, but kept as a final safeguard.
        print("⚠ No PDFs were processed (all_rows list is empty).")
        return "⚠ No matching PDF statements found for this date range. Please check your selected period."

    # Merge all DataFrames and sort chronologically by statement week and order ID
    merged_all = pd.concat(all_rows, ignore_index=True)
    merged_all = merged_all.sort_values(by=["statement_start", "order_id", "type"]).reset_index(drop=True)

    # ---------------------------------------------------------------------------------------------
    # STEP 10.1 – Create dynamic filename based on actual statement coverage
    # ---------------------------------------------------------------------------------------------
    # The start and end Mondays are derived from the processed data itself,
    # ensuring filenames always reflect true date coverage.
    first_monday = pd.to_datetime(merged_all["statement_start"]).dt.date.min()
    last_monday  = pd.to_datetime(merged_all["statement_start"]).dt.date.max()

    if first_monday and last_monday:
        file_name = f"{first_monday:%y.%m.%d} - {last_monday:%y.%m.%d} - JE Order Level Detail.csv"
    else:
        file_name = "JE_Order_Level_Detail.csv" # Fallback name

    orders_csv = OUTPUT_FOLDER / file_name

    # ---------------------------------------------------------------------------------------------
    # STEP 10.2 – Apply consistent column naming and cleanup
    # ---------------------------------------------------------------------------------------------
    # Maps Just Eat columns to standard internal naming conventions (JET_COLUMN_RENAME_MAP)
    merged_all.rename(columns=JET_COLUMN_RENAME_MAP, inplace=True, errors="ignore")

    # Standardise JE order ID:
    #   - Convert to string type
    #   - Remove “.0” artifacts from float conversions
    #   - Strip out all non-numeric characters
    merged_all["je_order_id"] = (
        merged_all["je_order_id"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"[^0-9]", "", regex=True)
    )

    # ---------------------------------------------------------------------------------------------
    # STEP 10.3 – Save consolidated CSV output
    # ---------------------------------------------------------------------------------------------
    merged_all.to_csv(orders_csv, index=False)
    print(f"\n💾 Saved consolidated file → {orders_csv}")

    # =================================================================================================
    # STEP 11: Global summary printed after all PDFs are processed
    # =================================================================================================
    # Purpose:
    #   - Provide an at-a-glance overview of the combined dataset for QA and reconciliation readiness.
    #   - Acts as a final validation checkpoint before Step 3 (Reconciliation) is executed.
    #   - Summarises:
    #         • Count of PDFs processed
    #         • Order / Refund row totals
    #         • Aggregate £ values for sales, refunds, and net
    # -------------------------------------------------------------------------------------------------
    print("\n=================== GLOBAL SUMMARY ===================")

    # Compute global metrics for the entire merged dataset
    total_orders       = (merged_all["transaction_type"] == "Order").sum()
    total_refunds      = (merged_all["transaction_type"] == "Refund").sum()
    total_sales        = merged_all["je_total"].sum()
    total_refund_value = merged_all["je_refund"].sum() # Note: refunds are stored as negative
    net_after_refunds  = total_sales + total_refund_value

    # Print a clean, human-readable summary
    print(f"Total PDFs:       {len(pdf_files)}")
    print(f"Orders rows:      {total_orders:,}")
    print(f"Refund rows:      {total_refunds:,}")
    print(f"Total sales:      £{total_sales:,.2f}")
    print(f"Total refunds:    £{total_refund_value:,.2f}")
    print(f"Net after refund: £{net_after_refunds:,.2f}")
    print("======================================================")

    # Return the path to the consolidated output for downstream modules or GUI use
    return orders_csv


# ====================================================================================================
# 6. MAIN EXECUTION BLOCK
# ====================================================================================================
# Purpose:
#   - Allows the module to run independently for direct testing outside the GUI framework.
# ----------------------------------------------------------------------------------------------------
# This allows the script to be run directly (e.g., `python M02_process_mp_data.py`)
# for development and testing, using the default folder paths defined in Section 3.
# ----------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        run_je_parser(PDF_FOLDER, OUTPUT_FOLDER)
    except Exception as e:
        print(f"\n--- SCRIPT FAILED ---")
        print(f"Error: {e}")
        # In a real-world scenario, you might add logging here.