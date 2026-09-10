"""Normalize an uploaded file (pdf, csv, txt) into a single plain-text
string, which is the only input the extraction step ever sees."""
import io  # load io module for BytesIO wrapper around file_bytes
import pdfplumber  # load pdfplumber library for PDF text extraction
import pandas as pd  # load pandas library for CSV parsing and markdown rendering

SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".txt"}  # define set of file extensions this module can handle


def _get_extension(filename: str) -> str:  # helper to extract recognized extension from filename for dispatching
    """Return the recognized extension from filename, or '' if none match."""
    lower_name = filename.lower()  # convert filename to lowercase for case-insensitive comparison
    for ext in SUPPORTED_EXTENSIONS:  # iterate through each supported extension in the set
        if lower_name.endswith(ext):  # check if filename ends with this extension
            return ext  # return the matching extension immediately
    return ""  # return empty string if no supported extension matched


def load_pdf(file_bytes: bytes) -> str:  # loader function to extract text from PDF bytes
    """Extract text page by page with pdfplumber and join with blank lines."""
    text_parts = []  # initialize empty list to accumulate text from each page
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:  # open PDF from bytes stream and auto-close after block
        for page in pdf.pages:  # iterate through each page in the PDF document
            page_text = page.extract_text()  # extract plain text from this page
            if page_text:  # only add non-empty page text to avoid blank-line buildup
                text_parts.append(page_text)  # append this page's text to the accumulated list
    return "\n\n".join(text_parts)  # join all pages' text with double newlines for readability


def load_csv(file_bytes: bytes) -> str:  # loader function to convert CSV bytes to markdown table format
    """Render the CSV as a markdown table so Claude sees row/column
    structure instead of a flat comma-separated blob."""
    dataframe = pd.read_csv(io.BytesIO(file_bytes))  # parse CSV bytes into pandas DataFrame
    return dataframe.to_markdown(index=False)  # convert DataFrame to markdown table string without row numbers


def load_txt(file_bytes: bytes) -> str:  # loader function to decode UTF-8 text bytes to string
    """Decode as UTF-8, replacing any undecodable bytes rather than raising."""
    return file_bytes.decode("utf-8", errors="replace")  # decode bytes to UTF-8, replacing undecodable bytes with replacement char


def load_document(file_bytes: bytes, filename: str) -> str:  # main dispatcher function to route to correct loader based on extension
    """Dispatch to the right loader based on filename extension."""
    extension = _get_extension(filename)  # normalize filename to a recognized extension for dispatching
    if extension == ".pdf":  # check if extension indicates a PDF file
        return load_pdf(file_bytes)  # delegate to PDF loader
    if extension == ".csv":  # check if extension indicates a CSV file
        return load_csv(file_bytes)  # delegate to CSV loader
    if extension == ".txt":  # check if extension indicates a text file
        return load_txt(file_bytes)  # delegate to text loader
    raise ValueError(  # raise error if extension is not recognized
        f"Unsupported file type '{extension or filename}'. Supported types: PDF, CSV, TXT."  # include extension or filename in error message for clarity
    )
