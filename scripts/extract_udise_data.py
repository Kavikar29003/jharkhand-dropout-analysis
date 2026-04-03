"""
UDISE+ District PDF Extractor
===============================
Kajal Kumari — Jharkhand School Dropout Analysis Project

HOW TO USE:
1. Place ALL 24 district PDF files in the same folder as this script
   (or update PDF_FOLDER path below)
2. Run: python extract_udise_data.py
3. Output: jharkhand_master_data.csv  (ready for Python EDA + Tableau)

NAMING: Your PDF files should follow the UDISE+ naming pattern:
   JHARKHAND___BOKARO_fact_sheet_data.pdf
   JHARKHAND___CHATRA_fact_sheet_data.pdf
   ... etc.
"""

import os
import re
import csv
import subprocess

# ── CONFIG ──────────────────────────────────────────────────────────────────
PDF_FOLDER = "."          # folder containing all district PDFs
OUTPUT_CSV = "jharkhand_master_data.csv"
STATE_FILE_KEYWORD = "JHARKHAND_fact_sheet_data.pdf"  # exact state-level filename to skip
# ────────────────────────────────────────────────────────────────────────────


def extract_text_from_pdf(pdf_path):
    """Use pdftotext (poppler) for reliable layout-aware extraction."""
    result = subprocess.run(
        [r"C:\poppler-25.12.0\Library\bin\pdftotext.exe", "-layout", pdf_path, "-"],
        capture_output=True, text=True
    )
    return result.stdout


def clean_number(raw):
    """Strip commas, spaces, handle '/' as missing."""
    if not raw:
        return ""
    raw = raw.strip().replace(",", "").replace(" ", "")
    if raw in ["/", "-", "--", "N/A", ""]:
        return ""
    try:
        return float(raw)
    except ValueError:
        return raw


def extract_value(text, pattern, group=1, default=""):
    """Regex extract with fallback."""
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return clean_number(match.group(group))
    return default


def extract_district_name(text, filename):
    """Pull district name from Region: line or filename."""
    match = re.search(r"Region:\s*JHARKHAND\s*/\s*([A-Z\s\-]+)", text)
    if match:
        return match.group(1).strip().title()
    # fallback: parse from filename
    # handles both formats:
    #   JHARKHAND_BOKARO_fact_sheet_data.pdf   (single underscore)
    #   JHARKHAND___BOKARO_fact_sheet_data.pdf (triple underscore)
    base = os.path.basename(filename)
    base = re.sub(r"^JHARKHAND_+", "", base)
    base = base.replace("_fact_sheet_data.pdf", "").replace(".pdf", "")
    return base.replace("_", " ").strip().title()


def parse_district_pdf(pdf_path):
    """Extract all key indicators from one district PDF."""
    text = extract_text_from_pdf(pdf_path)

    district = extract_district_name(text, pdf_path)

    row = {"District": district}

    # ── SCHOOLS ──────────────────────────────────────────────────────────────
    row["Total_Schools"] = extract_value(
        text, r"Total Number of Schools\s+([\d,]+)")
    row["Govt_Schools"] = extract_value(
        text, r"Total Government Schools\s+([\d,]+)")
    row["Private_Schools"] = extract_value(
        text, r"Total Private Unaided Recognized Schools\s+([\d,]+)")

    # ── ENROLMENTS ───────────────────────────────────────────────────────────
    row["Total_Enrolment"] = extract_value(
        text, r"Total Number of Enrolments \(Foundational to Secondary\)\s+([\d,]+)")
    row["Enrolment_Middle"] = extract_value(
        text, r"Enrolment in Middle\s+([\d,]+)")
    row["Enrolment_Secondary"] = extract_value(
        text, r"Enrolment in Secondary\s+([\d,]+)")

    row["SC_Students"] = extract_value(
        text, r"Number of SC Students \(Foundational to Secondary\)\s+([\d,]+)")
    row["ST_Students"] = extract_value(
        text, r"Number of ST Students \(Foundational to Secondary\)\s+([\d,]+)")
    row["OBC_Students"] = extract_value(
        text, r"Number of OBC students \(Foundational to Secondary\)\s+([\d,]+)")

    # ── TEACHERS ─────────────────────────────────────────────────────────────
    row["Total_Teachers"] = extract_value(
        text, r"Total Number of teachers\s+([\d,]+)")
    row["Govt_Teachers"] = extract_value(
        text, r"Government Schools\s+([\d,]+)", default="")

    # ── PTR ──────────────────────────────────────────────────────────────────
    row["PTR_Foundational"] = extract_value(
        text, r"PTR at Foundational level\s+([\d.]+)")
    row["PTR_Preparatory"] = extract_value(
        text, r"PTR at Preparatory level\s+([\d.]+)")
    row["PTR_Middle"] = extract_value(
        text, r"PTR at Middle level\s+([\d.]+)")
    row["PTR_Secondary"] = extract_value(
        text, r"PTR at Secondary level\s+([\d.]+)")

    # ── GER ──────────────────────────────────────────────────────────────────
    row["GER_Foundational"] = extract_value(
        text, r"GER\)[\s\–\-]+Foundational\s+([\d./]+)")
    row["GER_Preparatory"] = extract_value(
        text, r"GER\)[\s\–\-]+Preparatory\s+([\d./]+)")
    row["GER_Middle"] = extract_value(
        text, r"GER\)[\s\–\-]+Middle\s+([\d./]+)")

    # ── DROPOUT RATES ────────────────────────────────────────────────────────
    row["Dropout_Preparatory"] = extract_value(
        text, r"Dropout Rates\s*-\s*Preparatory\s+([\d.]+)")
    row["Dropout_Middle"] = extract_value(
        text, r"Dropout.*?Middle.*?([\d.]+)")
    row["Dropout_Secondary"] = extract_value(
        text, r"Dropout Rates\s*-\s*Secondary\s+([\d.]+)")

    # ── TRANSITION RATES ─────────────────────────────────────────────────────
    row["Trans_Found_to_Prep"] = extract_value(
        text, r"Transition Rates Foundational to Preparatory\s+([\d.]+)")
    row["Trans_Prep_to_Mid"] = extract_value(
        text, r"Transition Rates Preparatory to Middle\s+([\d.]+)")
    row["Trans_Mid_to_Sec"] = extract_value(
        text, r"Transition Rates Middle to Secondary\s+([\d.]+)")

    # ── INFRASTRUCTURE ───────────────────────────────────────────────────────
    row["Pct_Electricity"] = extract_value(
        text, r"schools having electricity connection\s+([\d.]+)")
    row["Pct_Drinking_Water"] = extract_value(
        text, r"schools having drinking water facility\s+([\d.]+)")
    row["Pct_Girls_Toilet"] = extract_value(
        text, r"schools having girls' toilet facility\s+([\d.]+)")
    row["Pct_Computer"] = extract_value(
        text, r"schools having computer facility\s+([\d.]+)")
    row["Pct_Internet"] = extract_value(
        text, r"schools having internet facility\s+([\d.]+)")
    row["Pct_Smart_Classrooms"] = extract_value(
        text, r"schools having functional smart classrooms\s+([\d.]+)")
    row["Pct_Functional_Computer"] = extract_value(
        text, r"schools having functional computer facility\s+([\d.]+)")
    row["Pct_Playground"] = extract_value(
        text, r"schools having playground facility\s+([\d.]+)")

    # ── PERFORMANCE GRADING INDEX ─────────────────────────────────────────────
    row["PGI_Score"] = extract_value(
        text, r"Overall Score\s+([\d.]+)")
    pgi_grade = re.search(r"Overall Grade\s+([A-Z\-0-9]+)", text)
    row["PGI_Grade"] = pgi_grade.group(1).strip() if pgi_grade else ""

    # ── DERIVED METRICS (calculated here for convenience) ────────────────────
    # ST proportion — tribal vulnerability index
    try:
        st = float(row["ST_Students"]) if row["ST_Students"] != "" else None
        total = float(row["Total_Enrolment"]) if row["Total_Enrolment"] != "" else None
        row["ST_Proportion_Pct"] = round((st / total) * 100, 2) if st and total else ""
    except Exception:
        row["ST_Proportion_Pct"] = ""

    # Hidden dropout = students lost at Middle→Secondary transition
    try:
        trans = float(row["Trans_Mid_to_Sec"]) if row["Trans_Mid_to_Sec"] != "" else None
        row["Hidden_Dropout_Mid_to_Sec_Pct"] = round(100 - trans, 2) if trans else ""
    except Exception:
        row["Hidden_Dropout_Mid_to_Sec_Pct"] = ""

    return row


def main():
    # Find all district PDFs (exclude state-level file)
    pdf_files = []
    for f in sorted(os.listdir(PDF_FOLDER)):
        if f.endswith(".pdf") and "fact_sheet" in f.lower():
            # skip exact state-level file (no district name after JHARKHAND_)
            if f.strip() == STATE_FILE_KEYWORD:
                continue
            # skip if it looks like state file: JHARKHAND_fact_sheet... pattern
            if re.match(r"JHARKHAND_fact_sheet", f):
                continue
            pdf_files.append(os.path.join(PDF_FOLDER, f))

    if not pdf_files:
        print("No district PDFs found. Check PDF_FOLDER path.")
        return

    print(f"Found {len(pdf_files)} district PDF(s). Extracting...\n")

    all_rows = []
    for pdf_path in pdf_files:
        try:
            row = parse_district_pdf(pdf_path)
            all_rows.append(row)
            print(f"  ✓ {row['District']:25s} | Dropout Mid: {row['Dropout_Middle']} | PTR Sec: {row['PTR_Secondary']} | Trans Mid→Sec: {row['Trans_Mid_to_Sec']}")
        except Exception as e:
            print(f"  ✗ ERROR on {pdf_path}: {e}")

    if not all_rows:
        print("No data extracted. Check your PDF files.")
        return

    # Write master CSV
    fieldnames = list(all_rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n✓ Master CSV saved: {OUTPUT_CSV}")
    print(f"  {len(all_rows)} districts | {len(fieldnames)} columns")
    print(f"\nColumns extracted:")
    for col in fieldnames:
        print(f"  - {col}")


if __name__ == "__main__":
    main()
