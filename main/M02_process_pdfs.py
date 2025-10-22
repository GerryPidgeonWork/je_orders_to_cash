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
from processes.P01_set_file_paths import provider_pdf_folder, provider_pdf_unprocessed_folder, provider_output_folder
from processes.P04_static_lists import JET_COLUMN_RENAME_MAP

# ====================================================================================================
# CONFIGURATION
# ====================================================================================================
PDF_FOLDER = provider_pdf_unprocessed_folder
OUTPUT_FOLDER = provider_output_folder

# ====================================================================================================
# Helper Functions – Extract and Clean PDF Text
# ====================================================================================================

def get_segment_text(pdf_path: Path) -> str:
    """Extract section text between 'Commission to Just Eat' and 'Subtotal'."""
    txt = extract_text(str(pdf_path))
    start = txt.find("Commission to Just Eat")
    end = txt.find("Subtotal", start)
    if start == -1 or end == -1:
        return ""
    return txt[start:end]


def extract_descriptions(segment_text: str):
    """Clean and merge multi-line entries inside the Commission/Refund section."""
    if not segment_text:
        return []
    # Flatten whitespace and remove empty lines
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in segment_text.splitlines()]
    lines = [ln for ln in lines if ln]

    # Remove any standalone £ amount lines
    money_re = re.compile(r'[–\-]?\s*£\s*[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}')
    lines = [money_re.sub('', ln).strip() for ln in lines if not money_re.fullmatch(ln)]

    # Merge wrapped lines where continuation begins lowercase
    merged = []
    for ln in lines:
        if not merged:
            merged.append(ln)
            continue
        if ln[0].isupper():
            merged.append(ln)
        else:
            merged[-1] += " " + ln

    # Remove excess spacing and return list
    merged = [re.sub(r'\s{2,}', ' ', s).strip() for s in merged]
    return [s for s in merged if s]


def extract_amounts(segment_text: str):
    """Extract all £ amounts (handles negatives, line breaks, and dash formats)."""
    if not segment_text:
        return []

    # Normalise en-dashes and line breaks for cleaner regex matches
    segment_text = (
        segment_text
        .replace('–', '-')       # en dash → hyphen
        .replace('- \n£', '-£')  # fix when dash and £ are separated
        .replace('-\n£', '-£')
    )

    results = []
    for m in re.finditer(r'([\-]?)\s*£\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})', segment_text):
        sign = -1 if m.group(1) == '-' else 1
        val = float(m.group(2).replace(",", "")) * sign
        results.append(val)
    return results


def parse_reason_and_order(desc: str):
    """Extract refund reason and order number (supports multiple known patterns)."""
    reason, order = "", ""
    m1 = re.search(r"Customer compensation for (.*?) query (\d+)", desc, re.IGNORECASE)
    if m1:
        return m1.group(1).strip(), m1.group(2).strip()
    m2 = re.search(
        r"Restaurant\s+Comp\s*[-–]?\s*Cancelled\s+Order\s*[-–\s]*?(\d+)",
        desc, re.IGNORECASE
    )
    if m2:
        return "Restaurant Comp - Cancelled Order", m2.group(1).strip()
    return reason, order


def build_dataframe(descriptions, amounts):
    """Combine descriptions and amounts into a structured DataFrame."""
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
# Main Parser Function
# ====================================================================================================

def run_je_parser(pdf_folder: Path, output_folder: Path, start_date: str = None, end_date: str = None):
    """
    Parse all JE PDF statements; if start_date/end_date (YYYY-MM-DD) are provided,
    only PDFs whose statement period overlaps that range will be processed.
    """
    print("\n=================== JustEat PARSER ===================")

    # Convert GUI string inputs to date objects
    gui_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    gui_end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    print(f"🧭 Running JE Parser for range: {start_date} → {end_date}")

    # Find all JE PDFs in folder
    pdf_files = sorted(pdf_folder.glob("*JE Statement*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No matching PDFs found in: {pdf_folder}")

    print(f"📂 Found {len(pdf_files)} PDF(s) to process.")
    if gui_start and gui_end:
        print(f"📅 Restricting to PDFs overlapping {gui_start} → {gui_end}")

    # ------------------------------------------------------------------------------------------------
    # ⚡ Fast Filename Filter – identify PDFs overlapping the GUI range
    # ------------------------------------------------------------------------------------------------
    from datetime import timedelta
    filename_pattern = re.compile(r"(\d{2})\.(\d{2})\.(\d{2})", re.I)
    valid_files = []

    for pdf_path in pdf_files:
        m = filename_pattern.search(pdf_path.name)
        if not m:
            print(f"⚠ Could not parse start date from filename: {pdf_path.name}")
            continue

        start = datetime.strptime(f"20{m.group(1)}-{m.group(2)}-{m.group(3)}", "%Y-%m-%d").date()
        end = start + timedelta(days=6)  # Each statement covers 1 week (Mon–Sun)

        overlaps = not (end < gui_start or start > gui_end)
        if overlaps:
            valid_files.append(pdf_path)
        else:
            print(f"⏭ Skipped {pdf_path.name} (covers {start} → {end}, outside {gui_start} → {gui_end})")

    pdf_files = valid_files
    print(f"📄 {len(pdf_files)} PDF(s) remain after filename filter.")

    # =================================================================================================
    # PDF Parsing Loop
    # =================================================================================================
    all_rows = []

    for pdf_path in pdf_files:
        print(f"\n📄 Processing: {pdf_path.name}")

        # Extract text from all pages using pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            full_text_pages = [p.extract_text() or "" for p in pdf.pages]
        full_text = "\n".join(full_text_pages)

        # Detect statement period (multiple date formats supported)
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
        statement_end_raw = m_period.group(2) if m_period else None

        # Safely parse statement dates using multiple formats
        def parse_date_safe(date_str):
            if not date_str:
                return None
            for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d/%m/%y"):
                try:
                    return datetime.strptime(date_str.strip(), fmt).date()
                except Exception:
                    continue
            return None

        statement_start = parse_date_safe(statement_start_raw)
        statement_end = parse_date_safe(statement_end_raw)
        if not statement_start or not statement_end:
            print("   ⚠ Could not extract statement period → skipping file.")
            continue

        # Extract header-level values for validation
        orders_count_pat = re.compile(r"Number\s+of\s+orders\s+([\d,]+)", re.I)
        total_sales_pat = re.compile(r"Total\s+sales.*?£\s*([\d,]+\.\d{2})", re.I | re.S)
        you_receive_pat = re.compile(r"You\s+will\s+receive.*?£\s*([\d,]+\.\d{2})", re.I | re.S)
        payment_date_pat = re.compile(r"paid\s+on\s+(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})", re.I)

        m_orders = orders_count_pat.search(full_text)
        reported_order_count = int(m_orders.group(1).replace(",", "")) if m_orders else None
        m_sales = total_sales_pat.search(full_text)
        reported_total_sales = float(m_sales.group(1).replace(",", "")) if m_sales else None
        m_recv = you_receive_pat.search(full_text)
        reported_you_receive = float(m_recv.group(1).replace(",", "")) if m_recv else None
        m_payment = payment_date_pat.search(full_text)
        payment_date_raw = m_payment.group(1) if m_payment else None

        try:
            payment_date = datetime.strptime(payment_date_raw, "%d %b %Y").date() if payment_date_raw else None
        except Exception:
            payment_date = None

        # Skip non-overlapping statements (extra safety)
        if gui_start and gui_end:
            overlaps = not (statement_end < gui_start or statement_start > gui_end)
            if not overlaps:
                print(f"   ⏭ Skipped (statement {statement_start} → {statement_end} outside selected range).")
                continue

        # =================================================================================================
        # Extract Orders
        # =================================================================================================
        line_prefix = re.compile(r"^\s*\d+\s+(\d{2}/\d{2}/\d{2})\s+(\d+)\s+([A-Za-z/&\-]+)\s+(.*)$", re.M)
        money_finder = re.compile(r"[£]\s*([\d.,]+)")
        orders_data = []

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

        orders_df = pd.DataFrame(orders_data)
        parsed_order_count = len(orders_df)
        parsed_total_sales = round(orders_df["total_incl_vat"].sum(), 2)

        # =================================================================================================
        # Extract Refund, Commission, and Marketing Details
        # =================================================================================================
        seg = get_segment_text(pdf_path)
        descriptions = extract_descriptions(seg)
        amounts = extract_amounts(seg)
        df_full = build_dataframe(descriptions, amounts)

        # Separate totals by description type
        commission_sum = df_full[df_full["description"].str.contains("Commission", case=False, na=False)]["amount"].sum()
        marketing_sum = df_full[
            (~df_full["description"].str.contains("Commission", case=False, na=False)) &
            (df_full["reason"].eq(""))
        ]["amount"].sum()

        # Apply VAT uplift (20%) and reverse sign to match JE payout logic
        commission_incl_vat = round(commission_sum * 1.20 * -1, 2)
        marketing_incl_vat = round(marketing_sum * 1.20 * -1, 2)

        # Save per-statement refund detail file
        if not df_full.empty:
            refund_csv_path = OUTPUT_FOLDER / f"{pdf_path.stem}_RefundDetails.csv"
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
        # Refund Aggregation
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
        # Combine Orders + Refunds + Commission + Marketing
        # =================================================================================================
        order_rows = orders_df.copy()
        combined_rows = [order_rows]

        if not df_refunds_by_order.empty:
            refund_rows = df_refunds_by_order.copy()
            refund_rows["refund_amount"] = refund_rows["amount"].apply(lambda x: -x)  # invert once
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

        # Add commission and marketing summary lines
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

        combined_df = pd.concat(combined_rows, ignore_index=True)
        all_rows.append(combined_df)

        # =================================================================================================
        # Print Validation Summary
        # =================================================================================================
        refund_sum_lines = df_refunds_by_order["amount"].sum() if not df_refunds_by_order.empty else 0.0
        subtotal_all = df_full["amount"].sum() if not df_full.empty else 0.0
        vat_deductions = df_full.loc[~df_full["outside_scope"], "amount"].sum() if not df_full.empty else 0.0
        refund_total_calc = subtotal_all - vat_deductions
        refund_sum_lines_signed = -refund_sum_lines

        # Derived "You will receive" comparison from parsed values
        derived_receive = None
        diff_receive = None
        if reported_total_sales is not None and reported_you_receive is not None:
            derived_receive = reported_total_sales + refund_sum_lines_signed + commission_incl_vat + marketing_incl_vat
            diff_receive = round(derived_receive - reported_you_receive, 2)

        # --- PRINT VALIDATION WITH DELTAS ---
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
    # Final Merge + Save
    # =================================================================================================
    if not all_rows:
        print("⚠ No PDFs were processed (no matching statements found for the selected period).")
        return "⚠ No matching PDF statements found for this date range. Please check your selected period."

    merged_all = pd.concat(all_rows, ignore_index=True)
    merged_all = merged_all.sort_values(by=["statement_start", "order_id", "type"]).reset_index(drop=True)

    # Save with filename based on earliest and latest statement dates
    earliest_start = merged_all["statement_start"].min()
    latest_end = merged_all["statement_end"].max()

    if pd.notna(earliest_start) and pd.notna(latest_end):
        start_str = earliest_start.strftime("%y.%m.%d")
        end_str = latest_end.strftime("%y.%m.%d")
        file_name = f"{start_str} - {end_str} - JE Order Level Detail.csv"
    else:
        file_name = "JE_Order_Level_Detail.csv"

    orders_csv = OUTPUT_FOLDER / file_name
    merged_all.rename(columns=JET_COLUMN_RENAME_MAP, inplace=True, errors="ignore")

    # Clean JE order ID field (remove decimals and symbols)
    merged_all['je_order_id'] = (
        merged_all['je_order_id']
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"[^0-9]", "", regex=True)
    )

    # Save final consolidated output
    merged_all.to_csv(orders_csv, index=False)
    print(f"\n💾 Saved consolidated file → {orders_csv}")

    # =================================================================================================
    # Global Summary
    # =================================================================================================
    print("\n=================== GLOBAL SUMMARY ===================")
    total_orders = (merged_all["transaction_type"] == "Order").sum()
    total_refunds = (merged_all["transaction_type"] == "Refund").sum()
    total_sales = merged_all["je_total"].sum()
    total_refund_value = merged_all["je_refund"].sum()
    net_after_refunds = total_sales + total_refund_value
    print(f"Total PDFs:       {len(pdf_files)}")
    print(f"Orders rows:      {total_orders:,}")
    print(f"Refund rows:      {total_refunds:,}")
    print(f"Total sales:      £{total_sales:,.2f}")
    print(f"Total refunds:    £{total_refund_value:,.2f}")
    print(f"Net after refund: £{net_after_refunds:,.2f}")
    print("======================================================")

    return orders_csv

# ====================================================================================================
# MAIN EXECUTION BLOCK
# ====================================================================================================
if __name__ == "__main__":
    # Allows standalone execution without GUI
    run_je_parser(PDF_FOLDER, OUTPUT_FOLDER)
