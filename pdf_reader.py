import argparse
import pdfplumber
import pandas as pd
import re
from tqdm import tqdm

headers = ["DATE", "MODE**", "PARTICULARS", "DEPOSITS", "WITHDRAWLS", "BALANCE"]  # manually define correct header

# Try table extraction without relying on drawn lines
settings = {
    "vertical_strategy": "text",      # use text alignment
    "horizontal_strategy": "lines",    # use text alignment
    "intersection_tolerance": 5,
    "snap_tolerance": 3,
    "join_tolerance": 5,
}
# Regex patterns
date_pattern = r"(\d{2}-\d{2}-\d{4})"  # matches dd-mm-yyyy
header_pattern = r"^DATE"            # matches 'DATE' at the start

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


def extract_tables_from_pdf(pdf_path, password=None):
    """
    Opens the PDF and extracts tables page by page into a list of DataFrames.
    Returns a list of DataFrames.
    """
    page_num = 0
    df = pd.DataFrame(columns=headers)
    # Set max_colwidth to None
    pd.set_option('display.max_colwidth', None)
    try:
        with pdfplumber.open(pdf_path, password=password) as pdf:
            print(f"Opened {pdf_path} successfully!\n")
            for page_num, page in enumerate(tqdm(pdf.pages, desc="Extracting transactions", unit="page"), start=1):
                table = page.extract_tables(table_settings=settings)
                #print(table[0][0:-1])
                for i in table[0]:
                    cell_value = next((c for c in i if c not in [None, ""]), "")  # safely extract string
                    # check if it matches date or starts with 'DATE'
                    if re.match(date_pattern, cell_value):# or re.match(header_pattern, cell_value):
                        #print(i)
                        # 1. Strip blanks and remove empty strings
                        i = [str(cell).strip() for cell in i if str(cell).strip() != ""]
                        #print(i)
                        # Extract only the date and store in the same column
                        df["DATE"] = df["DATE"].str.extract(date_pattern)
                        # Check if transaction has less than 3 elements AND second element is 'B/F'
                        if len(i) <= 3 and i[1] == "B/F":
                            last_row_total = parse_number(i[2])
                            #print("Leaving Opening balance entry:", i)
                        else:
                            if (last_row_total-parse_number(i[3])) > 0.0:
                               df.loc[len(df)]=[i[0],"",i[1],"",i[2],i[3]]
                            else:
                               df.loc[len(df)]=[i[0],"",i[1],i[2],"",i[3]] 
                            last_row_total = parse_number(i[3])
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
    page_num, final_df = extract_tables_from_pdf(pdf_path, password)
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

