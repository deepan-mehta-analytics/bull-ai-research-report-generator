# scripts/generate_samples.py
"""Manual integration script - NOT part of the pytest suite, since it
calls the real Claude API and costs real money per run. Run this by hand
against any source document to produce one example PDF:

    ANTHROPIC_API_KEY=... python scripts/generate_samples.py \\
        "Example Corp" local-input/document.pdf example_corp_report.pdf

Deliberately takes the company name, source path, and output filename
as CLI arguments rather than a hardcoded list: this script must never
name any specific document, company, or brokerage as a string literal,
so the exact contents of the gitignored local-input/ test-kit folder
are never committed to this public repo.
"""
import sys  # standard library, needed for argv parsing and sys.path mutation below
from pathlib import Path  # pathlib for building filesystem paths in an OS-independent way

sys.path.insert(0, str(Path(__file__).parent.parent))  # add project root to import path so `app.*` resolves when run as a script

from app.ingestion.loaders import load_document  # import the document-to-text loader (pdf/csv/txt dispatch)
from app.extraction.extractor import extract_report_data  # import the Claude-backed extraction call
from app.charts.chart_builder import build_charts, MAX_CHART_SERIES  # import the chart-series-to-PNG renderer and the shared chart-count cap
from app.mapping.mapper import map_to_template_context  # import the ReportData-to-template-context mapper
from app.render.renderer import render_pdf  # import the context-to-PDF-bytes renderer

PROJECT_ROOT = Path(__file__).parent.parent  # resolve the project root (parent of scripts/) for building other paths
EXAMPLES_DIR = PROJECT_ROOT / "examples"  # output directory where generated sample PDFs are written

USAGE = (  # multi-line usage string shown on argument errors
    "Usage: python scripts/generate_samples.py "  # first half of the usage line
    '"<Company Name>" <source_path> <output_filename>.pdf'  # second half showing the three required positional args
)


def generate_one(company_name: str, source_path: Path, output_filename: str) -> None:  # run the full pipeline for one source document
    """Run the full pipeline for one source document and write the PDF."""
    print(f"Generating report for {company_name} from {source_path.name}...")  # progress message naming the company and source file
    file_bytes = source_path.read_bytes()  # read the raw source document bytes from disk
    document_text = load_document(file_bytes, source_path.name)  # normalize the document into plain text via the ingestion loader
    report_data = extract_report_data(document_text, company_name)  # call Claude to extract structured ReportData from the text
    if not report_data.chart_series:  # guard: skip if extraction produced no chartable series
        print(f"  WARNING: no chart series extracted for {company_name}, skipping.")  # explain why this document was skipped
        return  # stop processing this document early
    report_data.chart_series = report_data.chart_series[:MAX_CHART_SERIES]  # apply the same chart cap the FastAPI route uses, so examples match served output
    chart_images = build_charts(report_data.chart_series)  # render each chart series into a base64 PNG data URI
    context = map_to_template_context(report_data, chart_images)  # map ReportData + chart images into the template's context dict
    pdf_bytes = render_pdf(context)  # render the Jinja2 template and convert it to PDF bytes via WeasyPrint
    EXAMPLES_DIR.mkdir(exist_ok=True)  # ensure the examples/ output directory exists before writing
    output_path = EXAMPLES_DIR / output_filename  # build the full output path for this company's PDF
    output_path.write_bytes(pdf_bytes)  # write the generated PDF bytes to disk
    print(f"  wrote {output_path}")  # confirm the output file location


def main() -> None:  # entry point that parses argv and generates one example PDF
    """Parse company name, source path, and output filename from argv,
    then generate exactly one example PDF (call this once per document
    you want to produce - the script keeps no document list of its own)."""
    if len(sys.argv) != 4:  # expect exactly 3 positional args after the script name
        print(USAGE)  # show the usage string so the caller knows the expected invocation
        sys.exit(1)  # exit non-zero to signal a usage error
    company_name = sys.argv[1]  # first positional arg: the company display name for the report
    source_path = Path(sys.argv[2])  # second positional arg: path to the source document to ingest
    output_filename = sys.argv[3]  # third positional arg: filename to write under examples/
    if not source_path.exists():  # guard: bail out clearly if the given source path doesn't exist
        print(f"  ERROR: {source_path} not found.")  # explain exactly which path was missing
        sys.exit(1)  # exit non-zero since no output can be produced
    if not source_path.is_file():  # guard: a directory path would fail obscurely inside read_bytes()
        print(f"  ERROR: {source_path} is a directory, not a file - pass a single source document.")  # explain the actual problem
        sys.exit(1)  # exit non-zero since no output can be produced
    generate_one(company_name, source_path, output_filename)  # run the pipeline for the single requested document


if __name__ == "__main__":  # only run main() when this file is executed directly, not when imported
    main()  # kick off sample generation for the document named on the command line
