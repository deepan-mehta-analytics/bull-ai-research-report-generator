# app/main.py
"""FastAPI app: one page to submit company name + file, one route to run
the pipeline and return the PDF. No client JavaScript - see ADR-0003."""
import base64  # embed the generated PDF as a data: URI in the success page, per ADR-0003's zero-JS/no-extra-storage constraint
from pathlib import Path  # pathlib for building the templates directory path
from fastapi import FastAPI, Form, UploadFile, File  # FastAPI app class and request-parsing dependencies
from fastapi.responses import HTMLResponse  # response type for HTML pages (form, success, and error states)
from jinja2 import Environment, FileSystemLoader  # Jinja2 environment and filesystem template loader
import anthropic  # exception types recognized by the friendly-error mapping below
import pydantic  # ValidationError, the other exception type recognized by the friendly-error mapping below

from .ingestion.loaders import load_document  # Task 3: turn uploaded file bytes into plain text
from .extraction.extractor import extract_report_data  # Task 4: turn document text into a validated ReportData
from .charts.chart_builder import build_charts, MAX_CHART_SERIES  # Task 6: turn chart series into base64 PNG data URIs, plus the shared chart-count cap
from .mapping.mapper import map_to_template_context  # Task 5: turn ReportData + chart images into a template context dict
from .render.renderer import render_pdf  # Task 7: turn a template context dict into PDF bytes
from .market_data.lookup import get_market_data  # best-effort live market-data lookup
from .market_data.schema import MarketDataResult  # used both by the local try/except below and by tests via main_module.MarketDataResult

FORM_TEMPLATES_DIR = Path(__file__).parent / "render" / "templates"  # absolute path to the shared templates directory
_form_environment = Environment(loader=FileSystemLoader(str(FORM_TEMPLATES_DIR)), autoescape=True)  # Jinja2 environment scoped to that directory with HTML autoescaping on

app = FastAPI(title="Bull AI Research Report Generator")  # the FastAPI application instance uvicorn serves


def _render_form(error: str | None = None) -> str:  # render the upload form, optionally with an inline error
    """Render the upload form, optionally with an inline error message."""
    template = _form_environment.get_template("form.html")  # load form.html from the templates environment
    return template.render(error=error)  # render the template with the optional error message


def _render_success(company_name: str, filename: str, pdf_bytes: bytes) -> str:  # render the success page with the generated PDF embedded as a data: URI
    """Render the success page, embedding the PDF as a base64 data: URI
    so the download link works with zero extra server-side storage and
    zero client JavaScript (see ADR-0003)."""
    template = _form_environment.get_template("success.html")  # load success.html from the templates environment
    pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")  # encode the PDF bytes as base64 text for the data: URI
    return template.render(company_name=company_name, filename=f"{filename}_report.pdf", pdf_base64=pdf_base64)  # render with the company name, download filename, and embedded PDF


def _friendly_error(exc: Exception) -> str:  # map known exception types to plain-language, non-technical messages
    """Translate exception types a user could plausibly hit into
    actionable text. Anything not explicitly listed here keeps its
    original message unchanged - most exceptions raised in this
    pipeline (e.g. the "not enough trend data" ValueError) already
    carry a user-facing message written for this exact purpose."""
    if isinstance(exc, anthropic.RateLimitError):  # most specific first: RateLimitError is itself an APIStatusError
        return "The AI extraction service is busy right now - wait a moment and try again."
    if isinstance(exc, anthropic.APIConnectionError):  # network-level failure reaching the API
        return "Couldn't reach the AI extraction service - check your connection and try again."
    if isinstance(exc, anthropic.APIStatusError):  # any other API-side error (auth, bad request, server error)
        return "The AI extraction service had a problem processing this document - try again in a moment."
    if isinstance(exc, pydantic.ValidationError):  # the extracted data didn't match the expected schema shape
        return "The document's extraction didn't come out in the expected shape - try again."
    return str(exc)  # no specific mapping - show the exception's own message, unchanged from today's behavior


def _safe_filename(company_name: str) -> str:  # sanitize a company name for use in a download filename
    """Strip everything except alphanumerics/space/dash/underscore so the
    company name is safe to use in a Content-Disposition filename."""
    cleaned = "".join(char for char in company_name if (char.isascii() and char.isalnum()) or char in (" ", "_", "-"))  # keep only latin-1-safe characters, since Starlette encodes headers as latin-1
    return cleaned.strip() or "report"  # fall back to a generic name if nothing safe remains


@app.get("/", response_class=HTMLResponse)  # register GET / to return an HTML response
def show_form():  # handler for the root page
    """Serve the upload form."""
    return _render_form()  # render the form with no error


@app.post("/generate")  # register POST /generate to accept the form submission
def generate_report(company_name: str = Form(...), ticker: str = Form(""), file: UploadFile = File(...)):  # plain def so FastAPI runs this blocking pipeline in its threadpool, not on the event loop; new optional ticker field defaults to empty string, not Form(...)
    """Run the full pipeline and return the PDF, or re-render the form
    with an inline error on any failure."""
    file_bytes = file.file.read()  # read the full uploaded file into memory via the synchronous underlying file object
    try:  # run the pipeline, catching any failure to show an inline error instead of a raw 500
        document_text = load_document(file_bytes, file.filename or "")  # normalize the uploaded file into plain text
        report_data = extract_report_data(document_text, company_name)  # call Claude to extract structured report data
        if not report_data.chart_series:  # guard against documents with no numeric trend data to chart
            raise ValueError(  # surface a specific, actionable error message
                "The uploaded document didn't contain enough numerical trend data to build a chart. "
                "Try a document with quarter-over-quarter or year-over-year figures."
            )
        report_data.chart_series = report_data.chart_series[:MAX_CHART_SERIES]  # cap the chart count; Claude returns series in its own relevance order, so the first N are the highest-value ones
        try:  # get_market_data is contracted to never raise (see its own tests), but this local wrap is a second, unconditional layer of defense-in-depth: the pipeline's core report must never depend on that contract holding forever, only on it holding for THIS call
            market_data = get_market_data(company_name, ticker)  # best-effort live market-data lookup
        except Exception:  # a genuine contract violation - degrade rather than fail the whole report
            market_data = MarketDataResult(found=False)  # same "not available" outcome as every other market-data failure mode
        chart_images = build_charts(report_data.chart_series)  # render each chart series to a base64 PNG data URI
        context = map_to_template_context(report_data, chart_images, market_data)  # build the missing-field-safe template context
        pdf_bytes = render_pdf(context)  # render the context to PDF bytes
    except Exception as exc:  # catch any pipeline failure (bad file type, extraction error, missing chart data, market-data failure if it somehow raises, etc.)
        return HTMLResponse(content=_render_form(error=_friendly_error(exc)), status_code=400)  # re-show the form with a plain-language error message and a 400 status

    filename = _safe_filename(company_name)  # sanitize the company name for the download filename
    return HTMLResponse(content=_render_success(company_name, filename, pdf_bytes))  # show a distinct success page with the PDF embedded as a downloadable data: URI
