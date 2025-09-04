# PDF Transaction Extractor

A simple Python script to **extract transactions from PDF files** using [pdfplumber](https://github.com/jsvine/pdfplumber) and save them into **CSV** and **Excel** formats.  
Supports password-protected PDFs and works page by page with a progress bar.  

---

## Features
- Works with **normal and password-protected PDFs**  
- Exports tables to **CSV and Excel** (for easy use in Excel/Google Sheets)  
- Shows a **progress bar** when extracting from large PDFs  
- Keeps track of the **page number** for each extracted row  
- User-friendly **error handling** (missing file, wrong password, no tables, etc.)  
- Detailed **summary report** at the end  

---

## Requirements

Make sure you have **Python 3.8+** installed. Then install the dependencies:

```bash
pip install pdfplumber pandas tqdm openpyxl
```
---

## Usage

Run the script from the command line:
```bash
python pdf_reader.py yourfile.pdf
```

This will create:
tables.csv
tables.xlsx
in the same folder.

For password-protected PDFs
```bash
python pdf_reader.py yourfile.pdf --protected --password yourpassword
```

Save to a custom filename
```bash
python pdf_reader.py yourfile.pdf --output mydata.csv
```

This will create:
mydata.csv
mydata.xlsx

---

## Help menu

Run:
```bash
python pdf_reader.py -h
```

Output:
```bash
usage: pdf_reader.py [-h] [--protected] [--password PASSWORD] [--output OUTPUT] pdf_path

Extract tables from a PDF into CSV/Excel.

positional arguments:
  pdf_path              Path to the PDF file

optional arguments:
  -h, --help            show this help message and exit
  --protected           Flag if the PDF is password protected
  --password PASSWORD   Password for the PDF (if protected)
  --output OUTPUT       CSV file to save extracted tables

Examples:
  python pdf_reader.py statement.pdf
  python pdf_reader.py statement.pdf --protected --password secret123 --output result.csv
```
---

## Notes

Extraction accuracy depends on how the PDF is formatted.

If no tables are found, try opening the PDF in a viewer to confirm it contains selectable text (not just scanned images).

For scanned PDFs, you’ll need OCR (Haven't tested).
