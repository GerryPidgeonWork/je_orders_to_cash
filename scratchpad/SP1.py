# ====================================================================================================
# M02_process_mp_data.py
# ----------------------------------------------------------------------------------------------------
# Step 2 – Parse all Just Eat Statement PDFs and extract Orders, Refunds, Commission & Marketing
# ----------------------------------------------------------------------------------------------------
# Purpose:
#   - Reads all statement PDFs (e.g. "25.09.01 - JE Statement.pdf") for a selected date range.
#   - Extracts detailed transaction data and creates a single, standardised CSV output.
#   - Builds per-statement refund detail CSVs and a consolidated “Order Level Detail” file.
#
# Inputs:
#   • All PDFs matching "*JE Statement*.pdf" in provider_pdf_unprocessed_folder
#   • Optional date range (start_date, end_date) passed via GUI
# Outputs:
#   • One “RefundDetails.csv” per PDF processed
#   • A consolidated "<yy.mm.dd> - <yy.mm.dd> - JE Order Level Detail.csv" in provider_output_folder
#
# Notes:
#   - Keeps all financial amounts positive; signs applied at refund aggregation stage.
#   - Commission/Marketing totals are adjusted to include VAT (20% uplift).
#   - Filename date is treated as start of statement week (Monday → Sunday).
# ----------------------------------------------------------------------------------------------------
# Author:        Gerry Pidgeon
# Created:       2025-11-05
# Project:       Just Eat Orders-to-Cash Reconciliation
# ====================================================================================================


# ====================================================================================================
# 1. SYSTEM IMPORTS
# ----------------------------------------------------------------------------------------------------
# Add parent directory to sys.path so this module can import other “processes” packages.
# ====================================================================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True  # Prevents __pycache__ folders from being created


# ====================================================================================================
# 2. PROJECT IMPORTS
# ----------------------------------------------------------------------------------------------------
# Bring in shared functions, constants, and file paths.
# ====================================================================================================
from processes.P00_set_packages import *
from processes.P01_set_file_paths import (
    provider_pdf_folder,
    provider_pdf_unprocessed_folder,
    provider_output_folder,
    provider_refund_folder,
)
from processes.P03_shared_functions import statement_overlaps_file, get_je_statement_coverage
from processes.P04_static_lists import JET_COLUMN_RENAME_MAP


# ====================================================================================================
# 3. CONFIGURATION
# ----------------------------------------------------------------------------------------------------
# Define working directories for Step 2.
# ====================================================================================================
PDF_FOLDER = provider_pdf_unprocessed_folder
OUTPUT_FOLDER = provider_output_folder
REFUND_FOLDER = provider_refund_folder


# ====================================================================================================
# 4. HELPER FUNCTIONS – PDF EXTRACTION AND CLEANING
# ----------------------------------------------------------------------------------------------------
# Extract text, clean descriptions, parse monetary values, and build structured DataFrames.
# ====================================================================================================

def get_segment_text(pdf_path: Path) -> str:
    """
    Extract the section of a Just Eat PDF statement between
    “Commission to Just Eat” and “Subtotal”.

    Args:
        pdf_path (Path): Full path to the Just Eat PDF statement.

    Returns:
        str: Extracted text segment between the two markers.
             Returns an empty string if either marker is missing.

    Notes:
        • Uses `pdfminer.six.extract_text()` for accurate text extraction.
        • Gracefully handles missing markers to avoid breaking the pipeline.
        • Isolates Commission/Marketing/Refund area for later structured parsing.
    """
    txt = extract_text(str(pdf_path))
    start = txt.find("Commission to Just Eat")
    end = txt.find("Subtotal", start)
    return "" if start == -1 or end == -1 else txt[start:end]


def extract_descriptions(segment_text: str) -> list[str]:
    """
    Clean and consolidate multi-line description entries found in the
    Commission/Refund section of a statement.

    Args:
        segment_text (str): Raw text extracted between 'Commission to Just Eat' and 'Subtotal'.

    Returns:
        list[str]: Cleaned description lines (merged multi-line entries, no extraneous symbols).

    Notes:
        • Removes empty lines, isolated £-amount lines, and redundant whitespace.  
        • Merges wrapped lines starting with lower-case letters (PDF word-wrap artefacts).  
        • Provides consistent input for regex refund-reason parsing.
    """
    if not segment_text:
        return []
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in segment_text.splitlines() if ln.strip()]
    money_re = re.compile(r"[–\-]?\s*£\s*[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}")
    lines = [money_re.sub("", ln).strip() for ln in lines if not money_re.fullmatch(ln)]
    merged = []
    for ln in lines:
        if not merged:
            merged.append(ln)
        elif ln[0].isupper():
            merged.append(ln)
        else:
            merged[-1] += " " + ln
    return [re.sub(r"\s{2,}", " ", s).strip() for s in merged if s]


def extract_amounts(segment_text: str) -> list[float]:
    """
    Extract all monetary (£) amounts from a text segment, handling
    negative signs, en-dashes, and line-break irregularities.

    Args:
        segment_text (str): Raw text from the PDF section being processed.

    Returns:
        list[float]: Numeric list of positive/negative monetary values.

    Notes:
        • Converts en-dashes (–) to standard hyphens.  
        • Fixes split patterns (“- \n£12.34”).  
        • Supports thousands separators and converts to float.
    """
    if not segment_text:
        return []
    segment_text = (
        segment_text.replace("–", "-")
        .replace("- \n£", "-£")
        .replace("-\n£", "-£")
    )
    results = []
    pattern = re.compile(r"([\-]?)\s*£\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})")
    for m in pattern.finditer(segment_text):
        sign = -1 if m.group(1) == "-" else 1
        value = float(m.group(2).replace(",", "")) * sign
        results.append(value)
    return results


def parse_reason_and_order(desc: str) -> tuple[str, str]:
    """
    Identify refund/compensation reasons and corresponding order IDs
    within a single description line.

    Args:
        desc (str): Description text from the statement (e.g. refund line).

    Returns:
        tuple[str, str]: (reason, order_id)
            • reason – Parsed refund or compensation label.  
            • order_id – Extracted numeric Just Eat order ID (if found).

    Notes:
        Handles known JE formats:
            1️⃣ "Customer compensation for X query 123456"  
            2️⃣ "Restaurant Comp – Cancelled Order – 123456"  
            3️⃣ "Order ID: 123456 - Partner Compensation Recook"
        Returns ("", "") if no pattern matches.
    """
    reason, order = "", ""
    m1 = re.search(r"Customer compensation for (.*?) query (\d+)", desc, re.IGNORECASE)
    if m1:
        return m1.group(1).strip(), m1.group(2).strip()
    m2 = re.search(r"Restaurant\s+Comp\s*[-–]?\s*Cancelled\s+Order\s*[-–\s]*?(\d+)", desc, re.IGNORECASE)
    if m2:
        return "Restaurant Comp - Cancelled Order", m2.group(1).strip()
    m3 = re.search(r"Order\s*ID[:\s]*([0-9]+)\s*[-–]\s*Partner\s+Compensation\s+Recook", desc, re.IGNORECASE)
    if m3:
        return "Partner Compensation Recook", m3.group(1).strip()
    return reason, order


def build_dataframe(descriptions: list[str], amounts: list[float]) -> pd.DataFrame:
    """
    Combine descriptions and monetary amounts into a structured DataFrame.

    Args:
        descriptions (list[str]): Cleaned text descriptions.  
        amounts (list[float]): Parsed numeric £ amounts.

    Returns:
        pandas.DataFrame with columns:  
            • description (str)  
            • amount (float)  
            • reason (str)  
            • order_number (str)  
            • outside_scope (bool)

    Notes:
        • Pairs items up to the shorter list length.  
        • Flags “Outside the scope of VAT”.  
        • Forms the core refund and commission extraction table.
    """
    n = min(len(descriptions), len(amounts))
    data = []
    for i in range(n):
        desc = descriptions[i]
        amt = amounts[i]
        reason, order = parse_reason_and_order(desc)
        data.append({
            "description": desc,
            "amount": amt,
            "reason": reason,
            "order_number": order,
            "outside_scope": "Outside the scope of VAT" in desc
        })
    return pd.DataFrame(data)

# ====================================================================================================
# 5. MAIN PARSER FUNCTION
# ----------------------------------------------------------------------------------------------------
# Step 2 – Core orchestration of PDF parsing, extraction, and consolidation.
# ====================================================================================================

def run_je_parser(pdf_folder: Path, output_folder: Path, start_date: str = None, end_date: str = None):
    """
    Parse all weekly Just Eat Statement PDFs and produce a consolidated CSV.

    Args:
        pdf_folder (Path): Folder containing weekly JE Statement PDFs.  
        output_folder (Path): Destination for the consolidated output CSV.  
        start_date (str, optional): Inclusive start date (YYYY-MM-DD).  
        end_date (str, optional): Inclusive end date (YYYY-MM-DD).

    Returns:
        str | Path: Returns a message if no PDFs processed, else the output CSV path.

    Workflow:
        1️⃣ Find all statement PDFs.  
        2️⃣ Filter by accounting period (GUI dates).  
        3️⃣ Extract orders, refunds, commission & marketing.  
        4️⃣ Validate parsed totals against PDF headers.  
        5️⃣ Merge everything into one “JE Order Level Detail.csv”.

    Notes:
        • Handles missing or malformed PDFs gracefully.  
        • Applies VAT uplift (20 %) to commission & marketing.  
        • Writes per-PDF refund CSV and a master merged output.
    """

    # ---------------------------------------------------------------------------------------------
    # STEP 0: Console banner
    # ---------------------------------------------------------------------------------------------
    print("\n=================== JustEat PARSER ===================")

    # ---------------------------------------------------------------------------------------------
    # STEP 1: Convert GUI dates → Python date objects
    # ---------------------------------------------------------------------------------------------
    gui_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    gui_end   = datetime.strptime(end_date, "%Y-%m-%d").date()   if end_date   else None
    print(f"🧭 Running JE Parser for range: {start_date} → {end_date}")

    # ---------------------------------------------------------------------------------------------
    # STEP 2: Locate all JE Statement PDFs
    # ---------------------------------------------------------------------------------------------
    pdf_files = sorted(pdf_folder.glob("*JE Statement*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No matching PDFs found in: {pdf_folder}")

    print(f"📂 Found {len(pdf_files)} PDF(s).")
    if gui_start and gui_end:
        print(f"📅 Restricting to PDFs overlapping {gui_start} → {gui_end}")

    # ---------------------------------------------------------------------------------------------
    # STEP 3: Determine JE coverage window
    # ---------------------------------------------------------------------------------------------
    first_monday, last_monday = get_je_statement_coverage(pdf_folder, gui_start, gui_end)
    if not first_monday or not last_monday:
        raise FileNotFoundError(f"No JE statements overlap {gui_start} → {gui_end} in {pdf_folder}")
    print(f"📅 JE statements within selected range: {first_monday} → {last_monday}")

    # ---------------------------------------------------------------------------------------------
    # STEP 4: Filter PDFs by date range (overlap check)
    # ---------------------------------------------------------------------------------------------
    valid_files = []
    for pdf_path in sorted(pdf_folder.glob("*JE Statement*.pdf")):
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", pdf_path.name)
        if not m:
            continue
        start = datetime.strptime(f"20{m.group(1)}-{m.group(2)}-{m.group(3)}", "%Y-%m-%d").date()
        end = start + timedelta(days=6)
        if statement_overlaps_file(str(start), str(end), str(gui_start), str(gui_end)):
            valid_files.append(pdf_path)
        else:
            print(f"⏭ Skipped {pdf_path.name} (covers {start} → {end})")
    pdf_files = valid_files
    print(f"📄 {len(pdf_files)} PDF(s) selected for processing.")

    # =================================================================================================
    # STEP 5: Iterate through each PDF
    # =================================================================================================
    all_rows = []

    for pdf_path in pdf_files:
        print(f"\n📄 Processing: {pdf_path.name}")

        # Extract full text
        with pdfplumber.open(pdf_path) as pdf:
            full_text_pages = [p.extract_text() or "" for p in pdf.pages]
        full_text = "\n".join(full_text_pages)

        # Detect statement period
        period_patterns = [
            re.compile(r"(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})\s*[-–to]+\s*(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})", re.I),
            re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–to]+\s*(\d{1,2}/\d{1,2}/\d{2,4})", re.I),
        ]
        m_period = None
        for page_text in full_text_pages:
            for pat in period_patterns:
                m_period = pat.search(page_text)
                if m_period:
                    break
            if m_period:
                break
        statement_start_raw = m_period.group(1) if m_period else None
        statement_end_raw   = m_period.group(2) if m_period else None

        def parse_date_safe(date_str):
            """Safely parse varied date formats to datetime.date or None."""
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
            print("  ⚠ Could not extract statement period → skipping.")
            continue

        # Header fields for validation
        orders_count_pat = re.compile(r"Number\s+of\s+orders\s+([\d,]+)", re.I)
        total_sales_pat = re.compile(r"Total\s+sales.*?£\s*([\d,]+\.\d{2})", re.I | re.S)
        you_receive_pat = re.compile(r"You\s+will\s+receive.*?£\s*([\d,]+\.\d{2})", re.I | re.S)
        payment_date_pat = re.compile(r"paid\s+on\s+(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})", re.I)

        m_orders = orders_count_pat.search(full_text)
        m_sales  = total_sales_pat.search(full_text)
        m_recv   = you_receive_pat.search(full_text)
        m_payment = payment_date_pat.search(full_text)

        reported_order_count = int(m_orders.group(1).replace(",", "")) if m_orders else None
        reported_total_sales = float(m_sales.group(1).replace(",", "")) if m_sales else None
        reported_you_receive = float(m_recv.group(1).replace(",", "")) if m_recv else None
        payment_date_raw     = m_payment.group(1) if m_payment else None

        try:
            payment_date = datetime.strptime(payment_date_raw, "%d %b %Y").date() if payment_date_raw else None
        except Exception:
            payment_date = None

        # Skip PDFs outside range
        if gui_start and gui_end:
            if statement_end < gui_start or statement_start > gui_end:
                print(f"  ⏭ Skipped ({statement_start} → {statement_end})")
                continue

        # Extract orders
        line_prefix  = re.compile(r"^\s*\d+\s+(\d{2}/\d{2}/\d{2})\s+(\d+)\s+([A-Za-z/&\-]+)\s+(.*)$", re.M)
        money_finder = re.compile(r"[£]\s*([\d.,]+)")
        orders_data  = []

        for m in line_prefix.finditer(full_text):
            date, order_id, order_type, tail = m.groups()
            amts = money_finder.findall(tail)
            if not amts:
                continue
            total = float(amts[-1].replace(",", ""))
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

        # Convert to DataFrame
        orders_df = pd.DataFrame(orders_data)
        parsed_order_count = len(orders_df)
        parsed_total_sales = round(orders_df["total_incl_vat"].sum(), 2)

        # =================================================================================================
        # STEP 6: Extract Refund, Commission, and Marketing Details
        # =================================================================================================
        seg = get_segment_text(pdf_path)
        descriptions = extract_descriptions(seg)
        amounts = extract_amounts(seg)
        df_full = build_dataframe(descriptions, amounts)

        commission_sum = df_full[df_full["description"].str.contains("Commission", case=False, na=False)]["amount"].sum()
        marketing_sum = df_full[
            (~df_full["description"].str.contains("Commission", case=False, na=False))
            & (df_full["reason"].eq(""))
        ]["amount"].sum()

        commission_incl_vat = round(commission_sum * 1.20 * -1, 2)
        marketing_incl_vat  = round(marketing_sum * 1.20 * -1, 2)

        # ---------------------------------------------------------------------------------------------
        # STEP 6.1 – Save per-statement refund detail CSV
        # ---------------------------------------------------------------------------------------------
        if not df_full.empty:
            refund_csv_path = REFUND_FOLDER / f"{pdf_path.stem}_RefundDetails.csv"
            (
                df_full.assign(
                    source_file=pdf_path.name,
                    statement_start=statement_start,
                    statement_end=statement_end,
                    payment_date=payment_date,
                )
                .to_csv(refund_csv_path, index=False)
            )
            print(f"   💾 Saved refund detail → {refund_csv_path}")

        # =================================================================================================
        # STEP 7: Aggregate Refunds by Order
        # =================================================================================================
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
        # STEP 8: Combine Orders, Refunds, Commission, and Marketing
        # =================================================================================================
        order_rows = orders_df.copy()
        combined_rows = [order_rows]

        # Add refund rows
        if not df_refunds_by_order.empty:
            refund_rows = df_refunds_by_order.copy()
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

        # Add commission
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
                "payment_date": payment_date,
            }]))

        # Add marketing
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
                "payment_date": payment_date,
            }]))

        combined_df = pd.concat(combined_rows, ignore_index=True)
        all_rows.append(combined_df)

        # =================================================================================================
        # STEP 9: Per-Statement Validation
        # =================================================================================================
        refund_sum_lines = df_refunds_by_order["amount"].sum() if not df_refunds_by_order.empty else 0.0
        subtotal_all = df_full["amount"].sum() if not df_full.empty else 0.0
        vat_deductions = df_full.loc[~df_full["outside_scope"], "amount"].sum() if not df_full.empty else 0.0
        refund_total_calc = subtotal_all - vat_deductions
        refund_sum_lines_signed = -refund_sum_lines

        derived_receive = diff_receive = None
        if reported_total_sales is not None and reported_you_receive is not None:
            derived_receive = (
                reported_total_sales
                + refund_sum_lines_signed
                + commission_incl_vat
                + marketing_incl_vat
            )
            diff_receive = round(derived_receive - reported_you_receive, 2)

        # Validation summary
        print(f"   Header Orders: {reported_order_count:,} | Parsed Orders: {parsed_order_count:,}")
        print(f"   Header Total Sales: £{reported_total_sales:,.2f} | Parsed: £{parsed_total_sales:,.2f}")
        print(f"   Refund variance: £{refund_sum_lines_signed + refund_total_calc:+.2f}")
        print(f"   Header Payout: £{reported_you_receive:,.2f} | Parsed: £{derived_receive:,.2f} → Δ £{diff_receive:+.2f}")
        print(f"   Commission + VAT: £{commission_incl_vat:,.2f} | Marketing + VAT: £{marketing_incl_vat:,.2f}")
        if payment_date:
            print(f"   💰 Payment Date: {payment_date.strftime('%d %b %Y')}")

    # =================================================================================================
    # STEP 10: Merge and Save Consolidated Output
    # =================================================================================================
    if not all_rows:
        msg = "⚠ No matching PDF statements found for this date range."
        print(msg)
        return msg

    merged_all = pd.concat(all_rows, ignore_index=True)
    merged_all = merged_all.sort_values(by=["statement_start", "order_id", "type"]).reset_index(drop=True)

    first_monday = pd.to_datetime(merged_all["statement_start"]).dt.date.min()
    last_monday = pd.to_datetime(merged_all["statement_start"]).dt.date.max()
    file_name = f"{first_monday:%y.%m.%d} - {last_monday:%y.%m.%d} - JE Order Level Detail.csv"
    orders_csv = OUTPUT_FOLDER / file_name

    merged_all.rename(columns=JET_COLUMN_RENAME_MAP, inplace=True, errors="ignore")
    merged_all["je_order_id"] = (
        merged_all["je_order_id"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"[^0-9]", "", regex=True)
    )

    merged_all.to_csv(orders_csv, index=False)
    print(f"\n💾 Saved consolidated file → {orders_csv}")

    # =================================================================================================
    # STEP 11: Global Summary
    # =================================================================================================
    total_orders = (merged_all["transaction_type"] == "Order").sum()
    total_refunds = (merged_all["transaction_type"] == "Refund").sum()
    total_sales = merged_all["je_total"].sum()
    total_refund_value = merged_all["je_refund"].sum()
    net_after_refunds = total_sales + total_refund_value

    print("\n=================== GLOBAL SUMMARY ===================")
    print(f"Total PDFs:       {len(pdf_files)}")
    print(f"Orders rows:      {total_orders:,}")
    print(f"Refund rows:      {total_refunds:,}")
    print(f"Total sales:      £{total_sales:,.2f}")
    print(f"Total refunds:    £{total_refund_value:,.2f}")
    print(f"Net after refund: £{net_after_refunds:,.2f}")
    print("======================================================")

    return orders_csv


# ====================================================================================================
# 6. MAIN EXECUTION BLOCK
# ----------------------------------------------------------------------------------------------------
# Allows the module to run independently for debugging or CLI testing.
# ====================================================================================================
if __name__ == "__main__":
    run_je_parser(PDF_FOLDER, OUTPUT_FOLDER)

