import argparse
import pdfplumber
import pandas as pd
import re
from tqdm import tqdm

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
            print("\n--- Printing Complete Extracted Table ---")
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
    print("\n--- Saving Table ---")
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
    if not final_df.empty:
        save_output(final_df, output_csv)
        # Summary
        print("\n--- Summary ---")
        print(f"File processed: {pdf_path}")
        print(f"Total pages processed: {page_num}")
        #print(f"Pages with tables: {pdf_path}")
        print(f"Total transactions extracted: {len(final_df)}")
    else:
        print("\nNo tables extracted, please check if you are passing the correct bank statement!")
   
if __name__ == "__main__":
    main()

