# ====================================================================================================
# M02_process_pdfs.py
# ----------------------------------------------------------------------------------------------------
# Step 2 – Parse all Just Eat Statement PDFs and extract Orders, Refunds, Commission & Marketing
# ----------------------------------------------------------------------------------------------------
# Purpose:
# - Reads all statement PDFs (e.g. "25.09.01 - JE Statement.pdf") for a selected date range.
# - Extracts detailed transaction data and creates a single, standardised CSV output.
# - Builds per-statement refund detail CSVs and a consolidated “Order Level Detail” file.
# ----------------------------------------------------------------------------------------------------
# Inputs:
#   - All PDFs matching "*JE Statement*.pdf" in provider_pdf_unprocessed_folder
#   - Optional date range (start_date, end_date) passed via GUI
# Outputs:
#   - One “RefundDetails.csv” per PDF processed
#   - A consolidated "<yy.mm.dd> - <yy.mm.dd> - JE Order Level Detail.csv" in provider_output_folder
# ----------------------------------------------------------------------------------------------------
# Notes:
#   - Keeps all financial amounts positive; signs are applied at refund aggregation stage.
#   - Commission/Marketing totals are adjusted to include VAT (20% uplift).
#   - Filename date is treated as start of statement week (Monday → Sunday, +6 days).
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
from processes.P01_set_file_paths import provider_pdf_folder, provider_pdf_unprocessed_folder, provider_output_folder, provider_refund_folder
from processes.P03_shared_functions import statement_overlaps_file, get_je_statement_coverage
from processes.P04_static_lists import JET_COLUMN_RENAME_MAP

# ====================================================================================================
# CONFIGURATION
# ====================================================================================================
PDF_FOLDER = provider_pdf_unprocessed_folder
OUTPUT_FOLDER = provider_output_folder
REFUND_FOLDER = provider_refund_folder

# ====================================================================================================
# Helper Functions – Extract and Clean PDF Text
# ====================================================================================================

def get_segment_text(pdf_path: Path) -> str:
    """
    Extract the section text between the markers 'Commission to Just Eat' and 'Subtotal' within a PDF file.

    Args:
        pdf_path (Path): Full file path to the Just Eat PDF statement.

    Returns:
        str: Text segment found between 'Commission to Just Eat' and 'Subtotal'.
             Returns an empty string if either marker is missing.

    Notes:
        - Uses pdfminer.six's `extract_text()` to read full text content.
        - Ensures robustness by checking marker presence before slicing.
        - Helps isolate commission-related data for further parsing or reconciliation.
    """

    # Extract full text content from the given PDF file
    txt = extract_text(str(pdf_path))

    # Find the starting index of the "Commission to Just Eat" section
    start = txt.find("Commission to Just Eat")

    # Find the ending index marked by "Subtotal", starting the search after 'start'
    end = txt.find("Subtotal", start)

    # If either marker is not found, return an empty string safely
    if start == -1 or end == -1:
        return ""

    # Return only the text between the start and end markers
    return txt[start:end]

def extract_descriptions(segment_text: str):
    """
    Clean and consolidate multi-line description entries within the Commission/Refund section of a Just Eat statement.

    Args:
        segment_text (str): Raw text segment extracted from the PDF between
                            'Commission to Just Eat' and 'Subtotal'.

    Returns:
        list[str]: A cleaned list of text lines, where multi-line descriptions
                   are merged into single coherent entries.

    Notes:
        - Removes empty lines and excessive whitespace.
        - Strips standalone monetary values (£xx.xx) that appear on their own lines.
        - Merges continuation lines that start with lowercase letters,
          typical when text wraps across multiple lines in the PDF.
        - Provides consistent, cleaned data for downstream regex parsing
          or structured extraction of individual commission/refund items.
    """

    # Guard clause — if the input text is empty, return an empty list
    if not segment_text:
        return []

    # Normalize text:
    # - Replace multiple whitespace characters (spaces, tabs, etc.) with single spaces
    # - Strip leading/trailing spaces
    # - Remove empty lines created by PDF formatting
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in segment_text.splitlines()]
    lines = [ln for ln in lines if ln]

    # Identify monetary patterns like "£123.45" or "– £1,234.56"
    # and remove any lines containing only those amounts.
    money_re = re.compile(r'[–\-]?\s*£\s*[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}')
    lines = [money_re.sub('', ln).strip() for ln in lines if not money_re.fullmatch(ln)]

    # Merge continuation lines:
    # - If a line starts with an uppercase letter, it’s a new description.
    # - If it starts lowercase, it’s a continuation of the previous line.
    # This accounts for wrapped lines caused by narrow PDF layouts.
    merged = []
    for ln in lines:
        if not merged:
            merged.append(ln)
            continue
        if ln[0].isupper():
            merged.append(ln)
        else:
            merged[-1] += " " + ln

    # Final cleanup — collapse any remaining double spaces and trim entries
    merged = [re.sub(r'\s{2,}', ' ', s).strip() for s in merged]

    # Return only non-empty, fully cleaned description strings
    return [s for s in merged if s]

def extract_amounts(segment_text: str):
    """
    Extract all monetary amounts (£) from the provided text segment, correctly
    handling negatives, en-dashes, and line-break formatting irregularities.

    Args:
        segment_text (str): Raw text segment extracted from the Commission/Refund
                            section of the Just Eat PDF statement.

    Returns:
        list[float]: A list of numeric values (positive or negative) representing
                     all detected £ amounts within the text.

    Notes:
        - Handles en-dash characters (–) commonly used in PDFs instead of hyphens.
        - Corrects for broken line breaks (e.g., '- \n£12.34' → '-£12.34').
        - Recognizes thousands separators (commas) and converts to float.
        - Returns signed numeric values suitable for arithmetic reconciliation.
    """

    # Guard clause — return an empty list if there’s no text to parse
    if not segment_text:
        return []

    # Normalise text for reliable regex matching:
    # - Replace en-dashes (–) with regular hyphens (-)
    # - Fix split patterns where a dash and pound sign are separated by a newline
    segment_text = (
        segment_text
        .replace('–', '-')       # en dash → standard hyphen
        .replace('- \n£', '-£')  # handle split line between dash and pound sign
        .replace('-\n£', '-£')   # handle tighter variant
    )

    # List to collect all parsed monetary values
    results = []

    # Regex pattern explanation:
    # ([\-]?)          → optional minus sign (hyphen)
    # \s*£\s*          → pound sign with optional spaces
    # ([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})
    #                  → number with optional thousands separators and two decimals
    for m in re.finditer(r'([\-]?)\s*£\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})', segment_text):
        # Determine sign based on presence of '-' before the £
        sign = -1 if m.group(1) == '-' else 1

        # Convert numeric portion to float, removing commas
        val = float(m.group(2).replace(",", "")) * sign

        # Append the signed value to the results list
        results.append(val)

    # Return the list of extracted amounts
    return results

def parse_reason_and_order(desc: str):
    """
    Parse a single description line to extract the refund reason and corresponding order number.

    Args:
        desc (str): Description text extracted from the Just Eat Commission/Refund section.
                    Each line typically describes a compensation, refund, or cancellation reason.

    Returns:
        tuple[str, str]: A tuple containing:
            - reason (str): Parsed refund or compensation reason.
            - order (str): Extracted Just Eat order number (if available).

    Notes:
        - Supports multiple known statement formats, including:
            1️⃣ "Customer compensation for X query 123456"
            2️⃣ "Restaurant Comp – Cancelled Order – 123456"
            3️⃣ "Order ID: 123456 - Partner Compensation Recook (Outside the scope of VAT)"
        - Returns empty strings if no pattern matches.
        - Designed to be easily extended as new refund formats are introduced by Just Eat.
    """

    # Initialize default values
    reason, order = "", ""

    # 1️⃣ Customer Compensation format
    # Example: "Customer compensation for Missing Item query 123456"
    # Captures:
    #   - Reason: text between 'for' and 'query'
    #   - Order: numeric string after 'query'
    m1 = re.search(r"Customer compensation for (.*?) query (\d+)", desc, re.IGNORECASE)
    if m1:
        return m1.group(1).strip(), m1.group(2).strip()

    # 2️⃣ Restaurant Compensation – Cancelled Order format
    # Example: "Restaurant Comp – Cancelled Order – 123456"
    # Captures:
    #   - Reason: fixed string "Restaurant Comp - Cancelled Order"
    #   - Order: numeric ID after the final dash
    m2 = re.search(r"Restaurant\s+Comp\s*[-–]?\s*Cancelled\s+Order\s*[-–\s]*?(\d+)", desc, re.IGNORECASE)
    if m2:
        return "Restaurant Comp - Cancelled Order", m2.group(1).strip()

    # 3️⃣ Partner Compensation Recook format
    # Example: "Order ID: 123456 - Partner Compensation Recook (Outside the scope of VAT)"
    # Captures:
    #   - Reason: fixed string "Partner Compensation Recook"
    #   - Order: numeric ID after "Order ID:"
    m3 = re.search(r"Order\s*ID[:\s]*([0-9]+)\s*[-–]\s*Partner\s+Compensation\s+Recook", desc, re.IGNORECASE)
    if m3:
        return "Partner Compensation Recook", m3.group(1).strip()

    # If no pattern matched, return empty defaults
    # This allows safe unpacking by caller functions (e.g., reason, order = parse_reason_and_order(x))
    return reason, order

def build_dataframe(descriptions, amounts):
    """
    Combine parsed description and amount lists into a structured pandas DataFrame.

    Args:
        descriptions (list[str]): Cleaned list of text descriptions extracted
                                  from the Commission/Refund section of the PDF.
        amounts (list[float]): Corresponding list of £ amounts extracted from the same section.

    Returns:
        pandas.DataFrame: A DataFrame containing one row per parsed entry with the following columns:
            - description (str): Original cleaned description text.
            - amount (float): Monetary amount (£), positive or negative.
            - reason (str): Parsed refund/compensation reason (from `parse_reason_and_order`).
            - order_number (str): Extracted order ID associated with the entry, if present.
            - outside_scope (bool): True if the description includes "Outside the scope of VAT".

    Notes:
        - Only pairs up to the shorter of the two lists are included (safe handling of mismatched counts).
        - Uses helper function `parse_reason_and_order()` for semantic enrichment.
        - Produces a structured dataset for reconciliation and downstream financial analysis.
    """

    # Limit to the smaller of the two lists to prevent index errors
    n = min(len(descriptions), len(amounts))

    # Initialize an empty list to accumulate structured row dictionaries
    data = []

    # Iterate through paired description/amount entries
    for i in range(n):
        desc = descriptions[i]
        amt = amounts[i]

        # Extract detailed reason and order number from the description
        reason, order = parse_reason_and_order(desc)

        # Build a structured record dictionary for each entry
        data.append({
            "description": desc,                       # Original text entry
            "amount": amt,                             # Monetary value
            "reason": reason,                          # Parsed refund reason
            "order_number": order,                     # Associated Just Eat order ID
            "outside_scope": "Outside the scope of VAT" in desc  # VAT exclusion flag
        })

    # Convert accumulated records into a DataFrame
    return pd.DataFrame(data)

# ====================================================================================================
# Main Parser Function
# ====================================================================================================

def run_je_parser(pdf_folder: Path, output_folder: Path, start_date: str = None, end_date: str = None):
    """
    Parse all Just Eat (JE) weekly PDF statements and produce a consolidated CSV output.

    Args:
        pdf_folder (Path): Folder containing weekly JE PDF statements.
        output_folder (Path): Destination folder for the consolidated CSV output.
        start_date (str, optional): Inclusive start date (YYYY-MM-DD) for filtering statements.
        end_date (str, optional): Inclusive end date (YYYY-MM-DD) for filtering statements.

    Returns:
        str or Path: Returns a message string if no PDFs were processed,
                     otherwise returns the path to the consolidated CSV file.

    Purpose:
        This master function acts as the orchestrator for Step 2 of the Orders-to-Cash workflow.
        It automates the end-to-end parsing of all Just Eat PDF statements within a selected
        date range and converts them into a structured, analysis-ready CSV.

    High-level flow:
        1️⃣ Find all matching PDFs inside the JE Statements folder.
        2️⃣ Filter to only those overlapping the GUI-selected start/end date range.
        3️⃣ Extract orders, refunds, commission and marketing data from each PDF.
        4️⃣ Validate extracted figures against header totals printed on the PDF.
        5️⃣ Merge everything into a single consolidated “JE Order Level Detail.csv”.
    """

    # --- STEP 0: Print a banner for readability in the console ---
    print("\n=================== JustEat PARSER ===================")

    # ---------------------------------------------------------------------------------------------
    # STEP 1: Convert GUI date-picker strings (YYYY-MM-DD) to Python date objects
    # ---------------------------------------------------------------------------------------------
    # These will be used to compare against each statement’s internal period to decide
    # which PDFs should be processed.
    gui_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    gui_end   = datetime.strptime(end_date, "%Y-%m-%d").date()   if end_date   else None
    print(f"🧭 Running JE Parser for range: {start_date} → {end_date}")

    # ---------------------------------------------------------------------------------------------
    # STEP 2: Locate all files that look like JE Statements
    # ---------------------------------------------------------------------------------------------
    # The naming convention is consistent (“YY.MM.DD – JE Statement.pdf”)
    # so a simple wildcard search is reliable.
    pdf_files = sorted(pdf_folder.glob("*JE Statement*.pdf"))
    if not pdf_files:
        # If the folder is empty or mis-selected, fail early to alert the user.
        raise FileNotFoundError(f"No matching PDFs found in: {pdf_folder}")

    print(f"📂 Found {len(pdf_files)} PDF(s) to process.")
    if gui_start and gui_end:
        print(f"📅 Restricting to PDFs overlapping {gui_start} → {gui_end}")

    # ---------------------------------------------------------------------------------------------
    # STEP 3: Determine JE coverage within the GUI-selected accounting window
    # ---------------------------------------------------------------------------------------------
    first_monday, last_monday = get_je_statement_coverage(
        pdf_folder,
        gui_start,
        gui_end
    )

    if not first_monday or not last_monday:
        raise FileNotFoundError(f"No JE statements overlap {gui_start} → {gui_end} in {pdf_folder}")

    print(f"📅 JE statements within selected range: {first_monday} → {last_monday}")

    # Apply GUI filtering (optional – user might limit by accounting range)
    if gui_start and gui_end:
        print(f"🧭 Limiting to PDFs overlapping {gui_start} → {gui_end}")

    valid_files = []
    for pdf_path in sorted(pdf_folder.glob("*JE Statement*.pdf")):
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", pdf_path.name)
        if not m:
            continue
        start = datetime.strptime(f"20{m.group(1)}-{m.group(2)}-{m.group(3)}", "%Y-%m-%d").date()
        end = start + timedelta(days=6)  # Mon→Sun

        if statement_overlaps_file(str(start), str(end), str(gui_start), str(gui_end)):
            valid_files.append(pdf_path)
        else:
            print(f"⏭ Skipped {pdf_path.name} (covers {start} → {end}, outside selected range)")

    pdf_files = valid_files
    print(f"📄 {len(pdf_files)} PDF(s) selected for processing.")

    # =================================================================================================
    # STEP 4: Loop through each valid PDF and extract all required details
    # =================================================================================================
    all_rows = []   # Collects one combined DataFrame per PDF before merging

    for pdf_path in pdf_files:
        print(f"\n📄 Processing: {pdf_path.name}")

        # ---------------------------------------------------------------------------------------------
        # STEP 4.1 – Read and flatten all text content from the PDF
        # ---------------------------------------------------------------------------------------------
        # pdfplumber allows page-by-page text extraction; we join everything into one long string
        # because some patterns (e.g. “Total sales ... You will receive ...”) may span pages.
        with pdfplumber.open(pdf_path) as pdf:
            full_text_pages = [p.extract_text() or "" for p in pdf.pages]
        full_text = "\n".join(full_text_pages)

        # ---------------------------------------------------------------------------------------------
        # STEP 4.2 – Detect the statement period (start and end dates) printed in the header
        # ---------------------------------------------------------------------------------------------
        # JE uses two possible formats (textual or numeric), so we try both.
        period_patterns = [
            re.compile(r"(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})\s*[-–to]+\s*(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})", re.I),
            re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–to]+\s*(\d{1,2}/\d{1,2}/\d{2,4})", re.I),
        ]
        m_period = None
        # Search each page until we find a date range line.
        for page_text in full_text_pages:
            for pat in period_patterns:
                m_period = pat.search(page_text)
                if m_period:
                    break
            if m_period:
                break

        # Capture the raw text matches (if found)
        statement_start_raw = m_period.group(1) if m_period else None
        statement_end_raw   = m_period.group(2) if m_period else None

        # --- Inner helper to parse arbitrary date formats safely ---
        def parse_date_safe(date_str):
            """Return a date object from mixed formats or None if parsing fails."""
            if not date_str:
                return None
            for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d/%m/%y"):
                try:
                    return datetime.strptime(date_str.strip(), fmt).date()
                except Exception:
                    continue
            return None

        statement_start = parse_date_safe(statement_start_raw)
        statement_end   = parse_date_safe(statement_end_raw)
        if not statement_start or not statement_end:
            # If we can’t read the date range, the file can’t be tied to a week → skip gracefully.
            print("   ⚠ Could not extract statement period → skipping file.")
            continue

        # ---------------------------------------------------------------------------------------------
        # STEP 4.3 – Extract header-level summary metrics for validation
        # ---------------------------------------------------------------------------------------------
        # These fields let us cross-check our parsed totals later for data integrity.
        orders_count_pat  = re.compile(r"Number\s+of\s+orders\s+([\d,]+)", re.I)
        total_sales_pat   = re.compile(r"Total\s+sales.*?£\s*([\d,]+\.\d{2})", re.I | re.S)
        you_receive_pat   = re.compile(r"You\s+will\s+receive.*?£\s*([\d,]+\.\d{2})", re.I | re.S)
        payment_date_pat  = re.compile(r"paid\s+on\s+(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})", re.I)

        # Run regex extractions
        m_orders  = orders_count_pat.search(full_text)
        m_sales   = total_sales_pat.search(full_text)
        m_recv    = you_receive_pat.search(full_text)
        m_payment = payment_date_pat.search(full_text)

        reported_order_count = int(m_orders.group(1).replace(",", "")) if m_orders else None
        reported_total_sales  = float(m_sales.group(1).replace(",", "")) if m_sales else None
        reported_you_receive  = float(m_recv.group(1).replace(",", "")) if m_recv else None
        payment_date_raw      = m_payment.group(1) if m_payment else None

        # Parse payment date (tolerant of missing / malformed values)
        try:
            payment_date = datetime.strptime(payment_date_raw, "%d %b %Y").date() if payment_date_raw else None
        except Exception:
            payment_date = None

        # ---------------------------------------------------------------------------------------------
        # STEP 4.4 – Extra guard: skip statements that fall entirely outside selected GUI range
        # ---------------------------------------------------------------------------------------------
        if gui_start and gui_end:
            overlaps = not (statement_end < gui_start or statement_start > gui_end)
            if not overlaps:
                print(f"   ⏭ Skipped (statement {statement_start} → {statement_end} outside selected range).")
                continue

        # =================================================================================================
        # STEP 5: Extract individual ORDER lines
        # =================================================================================================
        # Each order line begins with a running index, then a date, order ID, type and £ value.
        line_prefix  = re.compile(r"^\s*\d+\s+(\d{2}/\d{2}/\d{2})\s+(\d+)\s+([A-Za-z/&\-]+)\s+(.*)$", re.M)
        money_finder = re.compile(r"[£]\s*([\d.,]+)")
        orders_data  = []   # Temporary storage before converting to DataFrame

        for m in line_prefix.finditer(full_text):
            # Split components of each order line
            date, order_id, order_type, tail = m.groups()
            # Extract all £-amounts that appear on that line
            amts = money_finder.findall(tail)
            if not amts:
                continue  # Skip if no money value found
            total = float(amts[-1].replace(",", ""))  # Usually the last number is the gross total

            # Record a structured dictionary for this order
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

        # Convert list of dicts → DataFrame for easier aggregation
        orders_df          = pd.DataFrame(orders_data)
        parsed_order_count = len(orders_df)
        parsed_total_sales = round(orders_df["total_incl_vat"].sum(), 2)

        # =================================================================================================
        # STEP 6: Extract Refund, Commission and Marketing details
        # =================================================================================================
        # This section of the PDF (below “Commission to Just Eat ... Subtotal”) is handled by helper
        # functions that isolate, clean and structure the text before combining.
        seg          = get_segment_text(pdf_path)          # Raw text segment isolation
        descriptions = extract_descriptions(seg)           # Clean multi-line refund descriptions
        amounts      = extract_amounts(seg)                # Match all £ values
        df_full      = build_dataframe(descriptions, amounts)  # Combine into tabular structure

        # --- Derive grouped totals by content type ---
        commission_sum = df_full[df_full["description"].str.contains("Commission", case=False, na=False)]["amount"].sum()
        marketing_sum  = df_full[
            (~df_full["description"].str.contains("Commission", case=False, na=False)) &
            (df_full["reason"].eq(""))
        ]["amount"].sum()

        # Apply 20 % VAT uplift and flip sign so commission/marketing show as deductions
        commission_incl_vat = round(commission_sum * 1.20 * -1, 2)
        marketing_incl_vat  = round(marketing_sum  * 1.20 * -1, 2)

        # ---------------------------------------------------------------------------------------------
        # STEP 6.1 – Save per-statement refund-detail file (for audit / debugging)
        # ---------------------------------------------------------------------------------------------
        if not df_full.empty:
            refund_csv_path = REFUND_FOLDER / f"{pdf_path.stem}_RefundDetails.csv"
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
            print(f"   💾 Saved refund detail file → {refund_csv_path}")

        # =================================================================================================
        # STEP 7: Aggregate refunds by order (for later joining to order lines)
        # =================================================================================================
        # Only rows marked “outside_scope” with a valid order number are treated as true refunds.
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
        # STEP 8: Combine Orders + Refunds + Commission + Marketing for this statement
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
        # The purpose is to confirm that parsed totals align with the summary values
        # printed on the PDF (as a sanity check before merging).
        refund_sum_lines        = df_refunds_by_order["amount"].sum() if not df_refunds_by_order.empty else 0.0
        subtotal_all            = df_full["amount"].sum() if not df_full.empty else 0.0
        vat_deductions          = df_full.loc[~df_full["outside_scope"], "amount"].sum() if not df_full.empty else 0.0
        refund_total_calc       = subtotal_all - vat_deductions
        refund_sum_lines_signed = -refund_sum_lines

        # Compute a derived “You will receive” figure based on parsed components
        derived_receive = None
        diff_receive    = None
        if reported_total_sales is not None and reported_you_receive is not None:
            derived_receive = (
                reported_total_sales
                + refund_sum_lines_signed
                + commission_incl_vat
                + marketing_incl_vat
            )
            diff_receive = round(derived_receive - reported_you_receive, 2)

        # --- Console output for validation checks ---
        print(f"   Header Orders: {reported_order_count:,} | Parsed Orders: {parsed_order_count:,} → Variance: {parsed_order_count - reported_order_count:+}")
        print(f"   Header Total Sales: £{reported_total_sales:,.2f} | Parsed Total Sales: £{parsed_total_sales:,.2f} → Variance: £{parsed_total_sales - reported_total_sales:+.2f}")
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
    # After all individual PDFs have been parsed, merge them into one master DataFrame.
    if not all_rows:
        # No matching files → return early with a friendly message.
        print("⚠ No PDFs were processed (no matching statements found for the selected period).")
        return "⚠ No matching PDF statements found for this date range. Please check your selected period."

    # Concatenate all DataFrames from the “all_rows” list and order them chronologically.
    merged_all = pd.concat(all_rows, ignore_index=True)
    merged_all = merged_all.sort_values(by=["statement_start", "order_id", "type"]).reset_index(drop=True)

    # ---------------------------------------------------------------------------------------------
    # STEP 10.1 – Create dynamic filename using the statements we actually processed
    # ---------------------------------------------------------------------------------------------
    # Derive Mondays from the merged data (statement_start is the Monday of each week)
    first_monday = pd.to_datetime(merged_all["statement_start"]).dt.date.min()
    last_monday  = pd.to_datetime(merged_all["statement_start"]).dt.date.max()

    if first_monday and last_monday:
        file_name = f"{first_monday:%y.%m.%d} - {last_monday:%y.%m.%d} - JE Order Level Detail.csv"
    else:
        file_name = "JE_Order_Level_Detail.csv"

    orders_csv = OUTPUT_FOLDER / file_name

    # ---------------------------------------------------------------------------------------------
    # STEP 10.2 – Apply consistent column naming and field cleanup
    # ---------------------------------------------------------------------------------------------
    merged_all.rename(columns=JET_COLUMN_RENAME_MAP, inplace=True, errors="ignore")

    # Clean JE order ID column:
    #   - Ensure it’s string typed
    #   - Strip trailing “.0” artifacts
    #   - Remove any stray punctuation / non-numeric symbols
    merged_all["je_order_id"] = (
        merged_all["je_order_id"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"[^0-9]", "", regex=True)
    )

    # ---------------------------------------------------------------------------------------------
    # STEP 10.4 – Save final consolidated CSV
    # ---------------------------------------------------------------------------------------------
    merged_all.to_csv(orders_csv, index=False)
    print(f"\n💾 Saved consolidated file → {orders_csv}")

    # =================================================================================================
    # STEP 11: Global summary printed after all PDFs are processed
    # =================================================================================================
    # Provides at-a-glance totals for QA before proceeding to reconciliation (Step 3).
    print("\n=================== GLOBAL SUMMARY ===================")
    total_orders        = (merged_all["transaction_type"] == "Order").sum()
    total_refunds       = (merged_all["transaction_type"] == "Refund").sum()
    total_sales         = merged_all["je_total"].sum()
    total_refund_value  = merged_all["je_refund"].sum()
    net_after_refunds   = total_sales + total_refund_value
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
# MAIN EXECUTION BLOCK
# ====================================================================================================
if __name__ == "__main__":
    # Allows standalone execution without GUI
    run_je_parser(PDF_FOLDER, OUTPUT_FOLDER)