import argparse
import pdfplumber
import pandas as pd
import re
from tqdm import tqdm
import time
import textwrap
import shutil
import math
headers = ["DATE", "MODE**", "PARTICULARS", "DEPOSITS", "WITHDRAWLS", "BALANCE"]  # manually define correct header


# Bank-specific regex configurations
BANK_CONFIG = {
    "HDFC": {
        "bank": "HDFC",
        "date_pattern": r"(\d{2}-\d{2}-\d{4})",      # e.g. 01-01-2024
        "amount_pattern": r"(\d{1,3}(?:,\d{3})*\.\d{2})",  # 1,234.56
        "balance_pattern": r"Balance\s*:\s*(\d+\.\d{2})",
        "start_of_transaction_mark": "?",
        "column_on_mark": 3,
        "settings": { "vertical_strategy": "text", "horizontal_strategy": "lines", "intersection_tolerance": 5, "snap_tolerance": 3, "join_tolerance": 5, },
        "empty_cell": ""
    },
    "ICICI": {
        "bank": "ICICI",
        "date_pattern": r"(\d{2}-\d{2}-\d{4})",      # e.g. 01-01-2024
        "amount_pattern": r"INR\s*(\d+\.\d{2})",     # INR 1234.56
        "balance_pattern": r"Closing\s*Balance\s*:\s*(\d+\.\d{2})",
        "start_of_transaction_mark": "B/F",
        "column_on_mark": 3,
        "settings": { "vertical_strategy": "text", "horizontal_strategy": "lines", "intersection_tolerance": 5, "snap_tolerance": 3, "join_tolerance": 5, },
        "empty_cell": [""]
    },
    "SBI": {
        "bank": "SBI",
        "date_pattern": r"(\d{2}-\d{2}-\d{2})",      # e.g. 01-01-25
        "amount_pattern": r"(\d+\.\d{2})",           # 1234.56
        "balance_pattern": r"Avail\. Balance\s*:\s*(\d+\.\d{2})",
        "start_of_transaction_mark": r"on\s+\d{2}-\d{2}-\d{2}",
        "column_on_mark": 7,
        "settings": { "vertical_strategy": "lines", "horizontal_strategy": "lines", "intersection_tolerance": 5, "snap_tolerance": 3, "join_tolerance": 5, },
        "empty_cell": ["-", "None", "null"]
    }
}

def print_alert(msg: str, title: str = "IMPORTANT:", width: int = 80):
    # Use terminal width if available
    term_width = shutil.get_terminal_size((width, 20)).columns
    width = min(width, term_width)

    sep_line = "=" * width

    BLUE = "\033[1;34m"
    YELLOW = "\033[1;33m"
    RESET = "\033[0m"

    # Top separator
    print(f"\n{BLUE}{sep_line}{RESET}")

    # Centered title
    print(f"{BLUE}{title.center(width)}{RESET}")

    # Message wrapped to width
    wrapped = textwrap.fill(msg, width=width)
    print(f"{YELLOW}{wrapped}{RESET}")

    # Bottom separator
    print(f"{BLUE}{sep_line}{RESET}\n")

    time.sleep(1)

def get_bank_config(bank_name):
    # Return regex config if bank is known, else None
    return BANK_CONFIG.get(bank_name, None)


# Regex patterns
header_pattern = r"^DATE"            # matches 'DATE' at the start

def detect_bank_from_pdf(pdf_path, password):
    # List of bank names you want to detect
    banks = list(BANK_CONFIG.keys())
    
    with pdfplumber.open(pdf_path, password=password) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()
        
        if text:  # Check if text is extracted
            for bank in banks:
                if bank.lower() in text.lower():
                    return bank
    
    return ""

def parse_number(s):
    if not s or s.strip() == "":
        return 0
    s_clean = s.replace(",", "").replace("₹", "").strip()
    try:
        return float(s_clean)
    except ValueError:
        return 0

def get_pdf_handle():
    """
    Parse CLI arguments and return PDF path, password, and output CSV path.
    """
    parser = argparse.ArgumentParser(description="Extract tables from a PDF using pdfplumber", 
                                     epilog="""Examples:
    python extract_tables.py statement.pdf
    python extract_tables.py statement.pdf --protected --password secret123 --output result.csv
    """,
                                     formatter_class=argparse.RawTextHelpFormatter,)
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--protected", action="store_true", help="Flag if the PDF is password protected")
    parser.add_argument("--password", help="Password for the PDF (if protected)")
    parser.add_argument("--output", default="tables.csv", help="CSV file to save extracted tables")
    
    args = parser.parse_args()
    
    password = args.password if args.protected else None
    return args.pdf_path, password, args.output


def extract_tables_from_pdf(pdf_path, bank_config, password=None):
    """
    Opens the PDF and extracts tables page by page into a list of DataFrames.
    Returns a list of DataFrames.
    """
    page_num = 0
    run_once = True
    # Set max_colwidth to None
    pd.set_option('display.max_colwidth', None)
    pd.set_option("display.max_rows", None)  # Show all rows
    # pd.set_option("display.max_columns", None)  # Show all columns
    df = pd.DataFrame(columns=headers)
    try:
        with pdfplumber.open(pdf_path, password=password) as pdf:
            print(f"Opened {pdf_path} successfully!\n")
            for page_num, page in enumerate(tqdm(pdf.pages, desc="Extracting transactions", unit="page"), start=1):
                table = page.extract_tables(table_settings=bank_config["settings"])
                
                if len(table) > 1:
                    table_with_transaction = 1
                else:
                    table_with_transaction = 0
                # print(table[table_with_transaction])
                for i in table[table_with_transaction]:
                    cell_value = next((c for c in i if c not in [None, ""]), "")  # safely extract string
                    # check if it matches date or starts with 'DATE'
                    if re.match(bank_config["date_pattern"], cell_value):# or re.match(header_pattern, cell_value):
                        # print(i[-2])
                        if i[-2] != "-" and bank_config["bank"] == "SBI" and run_once:
                            run_once = False
                            opening_balance = parse_number(i[-2]) + parse_number(i[-1])
                        # 1. Strip blanks and remove empty strings
                        i = [str(cell).strip() for cell in i if str(cell).strip() not in bank_config["empty_cell"]]
                        #print(i)
                        # Extract only the date and store in the same column
                        df["DATE"] = df["DATE"].str.extract(bank_config["date_pattern"])
                        # Check if transaction has less than 3 elements AND second element is 'B/F'
                        if len(i) <= bank_config["column_on_mark"] and re.search(bank_config["start_of_transaction_mark"], i[1]):
                            opening_balance = parse_number(i[2])
                            #print("Leaving Opening balance entry:", i)
                        else:
                            if (opening_balance-parse_number(i[3])) > 0.0:
                               df.loc[len(df)]=[i[0],"",i[1],"",i[2],i[3]]
                            else:
                               df.loc[len(df)]=[i[0],"",i[1],i[2],"",i[3]] 
                            opening_balance = parse_number(i[3])
            print_alert("--- Printing Complete Extracted Table ---")
            print(df)
    except FileNotFoundError:
        print(f"File not found: {pdf_path}. Please check the path and try again.")
    except pdfplumber.pdfminer.pdfdocument.PDFPasswordIncorrect:
        print("Incorrect password! Please re-run with the correct --password.")
    except Exception as e:
        print("Error opening PDF:", e)
    return page_num, df

def save_output(final_df, output_file):
    """
    Save the DataFrame to CSV and Excel formats.

    Args:
        final_df (pd.DataFrame): DataFrame containing all extracted tables.
        output_file (str): Base output filename (CSV by default).
    """
    print_alert("--- Saving Table ---")
    try:
        # Save as CSV
        final_df.to_csv(output_file, index=False)
        print(f"CSV saved to {output_file}")

        # Save as Excel
        excel_file = output_file.replace(".csv", ".xlsx")
        final_df.to_excel(excel_file, index=False)
        print(f"Excel saved to {excel_file}")

    except Exception as e:
        print("Error saving output:", e)

def verify_transactions(df: pd.DataFrame):
    """
    Verify that:
    1. No missing values exist.
    2. total[0] is the opening balance.
    3. For each row i > 0: total[i] = total[i-1] + deposits[i] - withdrawals[i].

    Returns:
        dict with:
          - "status": True/False
          - "errors": DataFrame of mismatches
          - "message": summary text
    """
    print_alert("Transaction Verification")
    # Convert using parse_number
    deposits = df.iloc[:, 3].apply(parse_number)
    withdrawals = df.iloc[:, 4].apply(parse_number)
    total = df.iloc[:, 5].apply(parse_number)

    # ---------- Check cumulative consistency ----------
    expected_total = total.copy()
    for i in tqdm(range(1, len(df)), desc="Verifying transactions correctness"):
        expected_total.iloc[i] = round(expected_total.iloc[i-1] + deposits.iloc[i] - withdrawals.iloc[i],2)
        time.sleep(0.01)

    mismatches = df[total != expected_total].copy()
    if not mismatches.empty:
        mismatches["expected_total"] = expected_total[total != expected_total]
        mismatches["actual_total"] = total[total != expected_total]
        print(mismatches)

    # ---------- Build report ----------
    status = mismatches.empty
    if status:
        print("All checks passed. Data looks consistent.")
    else:
        print(f"{len(mismatches)} mismatches found.")
        exit(0)

def edit1_descriptions_paginated(df: pd.DataFrame, page_size: int = 10) -> pd.DataFrame:
    """
    Paginated editor for the 2nd column (description) of a DataFrame.
    User can navigate pages and edit descriptions interactively.
    """
    col_name = df.columns[1]  # 2nd column
    n_rows = len(df)
    total_pages = math.ceil(n_rows / page_size)
    page = 0

    while True:
        start = page * page_size
        end = min(start + page_size, n_rows)
        print(f"\nShowing rows {start} to {end-1} (Page {page+1}/{total_pages}):\n")
        print(df.iloc[start:end])  # show ID and description

        # Edit rows in this page
        for idx in range(start, end):
            current_desc = df.at[idx, col_name]
            new_desc = input(f"Row {idx} - Current description: {current_desc}\nNew description (Enter to keep): ")
            if new_desc.strip():
                df.at[idx, col_name] = new_desc.strip()

        # Navigation options
        nav = input("\nOptions: [N]ext page, [P]revious page, [Q]uit editing: ").strip().lower()
        if nav == 'n':
            if page < total_pages - 1:
                page += 1
            else:
                print("Already at last page.")
        elif nav == 'p':
            if page > 0:
                page -= 1
            else:
                print("Already at first page.")
        elif nav == 'q':
            print("\nFinished editing.")
            break
        else:
            print("Invalid option. Please type N, P, or Q.")

    return df

def edit_descriptions_paginated(df: pd.DataFrame, page_size: int = 10) -> pd.DataFrame:
    """
    Paginated editor for the 2nd column (description) of a DataFrame.
    Shows all columns and lets the user edit the description column.
    Updates are immediately reflected, and the updated page is displayed after edits.
    """
    col_name = df.columns[2]  # 2nd column
    n_rows = len(df)
    total_pages = math.ceil(n_rows / page_size)
    page = 0

    while True:
        start = page * page_size
        end = min(start + page_size, n_rows)
        print(f"\nShowing rows {start} to {end-1} (Page {page+1}/{total_pages}):\n")
        print(df.iloc[start:end])  # show all columns

        # Edit rows in this page
        for idx in range(start, end):
            current_desc = df.at[idx, col_name]
            new_desc = input(f"\nRow {idx} - Current description: {current_desc}\nNew description (Enter to keep): ")
            if new_desc.strip():
                df.at[idx, col_name] = new_desc.strip()

        # Show updated page
        print("\nUpdated page:")
        print(df.iloc[start:end])

        # Navigation options
        nav = input("\nOptions: [N]ext page, [P]revious page, [Q]uit editing: ").strip().lower()
        if nav == 'n':
            if page < total_pages - 1:
                page += 1
            else:
                print("Already at last page.")
        elif nav == 'p':
            if page > 0:
                page -= 1
            else:
                print("Already at first page.")
        elif nav == 'q':
            print("\nFinished editing.")
            break
        else:
            print("Invalid option. Please type N, P, or Q.")

    return df

def main():
    pdf_path, password, output_csv = get_pdf_handle()
    bank_name = detect_bank_from_pdf(pdf_path, password)
    if(bank_name == ""):
        print("Unknown Bank!")
        exit(0)
    else:
        print("Detected Bank:", bank_name)

    config = get_bank_config(bank_name)

    page_num, final_df = extract_tables_from_pdf(pdf_path, config, password)
    verify_transactions(final_df)

    print_alert("Editing description for the transactions")
     # Ask user if they want to edit the description
    choice = input("Do you want to edit the descriptions? (Y/N): ").strip().lower()
    if choice == 'y':
        final_df = edit_descriptions_paginated(final_df, page_size=5)
    else:
        print("Skipping description editing.")
    print_alert("Final Transaction Table")
    print(final_df)
    if not final_df.empty:
        save_output(final_df, output_csv)
        # Summary
        print_alert("--- Summary ---")
        print(f"File processed: {pdf_path}")
        print(f"Total pages processed: {page_num}")
        #print(f"Pages with tables: {pdf_path}")
        print(f"Total transactions extracted: {len(final_df)}")
    else:
        print("\nNo tables extracted, please check if you are passing the correct bank statement!")
   
if __name__ == "__main__":
    main()

