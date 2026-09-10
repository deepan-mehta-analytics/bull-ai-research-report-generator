import os  # load standard library os module for Windows DLL directory setup
import sys  # load standard library sys module to check platform type

if sys.platform == "win32" and os.environ.get("WEASYPRINT_DLL_DIRECTORY"):  # only on Windows, only if env var is set
    os.add_dll_directory(os.environ["WEASYPRINT_DLL_DIRECTORY"])  # register WeasyPrint's GTK3 DLL directory with Python 3.8+

import pytest  # load pytest testing framework for test decorators and assertions
from weasyprint import HTML  # load HTML converter from weasyprint to generate test PDF fixture
from app.ingestion.loaders import load_document, load_pdf, load_csv, load_txt  # import all loader functions from ingestion module

def test_load_txt_returns_decoded_text():  # test that txt loader correctly decodes bytes to UTF-8 string
    result = load_txt(b"Revenue grew 20% year over year.")  # call loader on sample bytes string
    assert "Revenue grew 20%" in result  # verify the expected text appears in the result

def test_load_csv_returns_markdown_table():  # test that CSV loader returns markdown-formatted table with column separators
    csv_bytes = b"Metric,Q1,Q2\nRevenue,100,120\nEBITDA,20,25\n"  # create sample CSV bytes with header and two data rows
    result = load_csv(csv_bytes)  # call loader to convert CSV to markdown
    assert "Revenue" in result  # verify first column value appears in markdown output
    assert "120" in result  # verify specific data cell appears in markdown output
    assert "|" in result  # verify markdown table pipe characters are present in output

def test_load_pdf_extracts_text():  # test that PDF loader extracts text content from PDF pages
    pdf_bytes = HTML(string="<html><body><p>Revenue grew 20 percent.</p></body></html>").write_pdf()  # generate test PDF from HTML string
    result = load_pdf(pdf_bytes)  # call loader to extract text from PDF bytes
    assert "Revenue grew 20 percent" in result  # verify extracted text matches expected content

def test_load_document_dispatches_by_extension():  # test that main dispatcher function routes txt files to txt loader
    assert "hello" in load_document(b"hello", "notes.txt")  # verify txt extension triggers correct loader

def test_load_document_rejects_unsupported_extension():  # test that dispatcher raises ValueError for unknown file type
    with pytest.raises(ValueError):  # expect ValueError to be raised
        load_document(b"data", "sheet.xlsx")  # call dispatcher with unsupported xlsx extension
