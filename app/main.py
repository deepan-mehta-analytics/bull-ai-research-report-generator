# app/main.py
"""FastAPI app: one page to submit company name + file, one route to run
the pipeline and return the PDF. No client JavaScript - see ADR-0003."""
from pathlib import Path  # pathlib for building the templates directory path
from fastapi import FastAPI, Form, UploadFile, File  # FastAPI app class and request-parsing dependencies
from fastapi.responses import HTMLResponse, Response  # response types for HTML pages and raw binary (PDF) bodies
from jinja2 import Environment, FileSystemLoader  # Jinja2 environment and filesystem template loader

from .ingestion.loaders import load_document  # Task 3: turn uploaded file bytes into plain text
from .extraction.extractor import extract_report_data  # Task 4: turn document text into a validated ReportData
from .charts.chart_builder import build_charts, MAX_CHART_SERIES  # Task 6: turn chart series into base64 PNG data URIs, plus the shared chart-count cap
from .mapping.mapper import map_to_template_context  # Task 5: turn ReportData + chart images into a template context dict
from .render.renderer import render_pdf  # Task 7: turn a template context dict into PDF bytes

FORM_TEMPLATES_DIR = Path(__file__).parent / "render" / "templates"  # absolute path to the shared templates directory
_form_environment = Environment(loader=FileSystemLoader(str(FORM_TEMPLATES_DIR)), autoescape=True)  # Jinja2 environment scoped to that directory with HTML autoescaping on

app = FastAPI(title="Bull AI Research Report Generator")  # the FastAPI application instance uvicorn serves


def _render_form(error: str | None = None) -> str:  # render the upload form, optionally with an inline error
    """Render the upload form, optionally with an inline error message."""
    template = _form_environment.get_template("form.html")  # load form.html from the templates environment
    return template.render(error=error)  # render the template with the optional error message


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
def generate_report(company_name: str = Form(...), file: UploadFile = File(...)):  # plain def so FastAPI runs this blocking pipeline in its threadpool, not on the event loop
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
        chart_images = build_charts(report_data.chart_series)  # render each chart series to a base64 PNG data URI
        context = map_to_template_context(report_data, chart_images)  # build the missing-field-safe template context
        pdf_bytes = render_pdf(context)  # render the context to PDF bytes
    except Exception as exc:  # catch any pipeline failure (bad file type, extraction error, missing chart data, etc.)
        return HTMLResponse(content=_render_form(error=str(exc)), status_code=400)  # re-show the form with the error message and a 400 status

    filename = _safe_filename(company_name)  # sanitize the company name for the download filename
    return Response(  # build the raw PDF response
        content=pdf_bytes,  # the rendered PDF bytes
        media_type="application/pdf",  # tell the browser this is a PDF
        headers={"Content-Disposition": f'attachment; filename="{filename}_report.pdf"'},  # prompt a download with a friendly filename
    )
