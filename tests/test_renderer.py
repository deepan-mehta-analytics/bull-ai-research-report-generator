# tests/test_renderer.py
from app.render.renderer import render_html, render_pdf  # functions under test: HTML render and PDF render
from app.mapping.mapper import MISSING_TEXT, MARKET_DATA_MISSING_TEXT  # shared missing-field marker constants used in fixture and assertions


def _sample_context():  # helper building a minimal valid context dict matching mapper's output shape
    return {  # return the sample context dict
        "company_name": "Test Co",  # simple company name value
        "company_data_rows": [{"label": "Sector", "value": "Banking"}],  # one populated company data row
        "business_summary": MISSING_TEXT,  # exercise the missing-field marker path
        "highlights": ["Revenue grew 10%"],  # one populated highlight
        "outlook": MISSING_TEXT,  # exercise the missing-field marker path
        "financial_period_labels": [],  # no period columns in the quarterly table
        "full_financials_period_labels": [],  # no period columns in the full-financials table
        "financial_table_rows": [],  # empty financial table
        "full_financials_rows": [],  # empty full financials table
        "charts": [],  # no chart images
        "historical_ratings": [MISSING_TEXT],  # exercise the missing-field marker path
        "missing_text": MISSING_TEXT,  # marker constant passed through to template
        "market_data": {"found": False, "caption": None},  # NEW - default to the not-found path
        "market_data_rows": [],  # NEW - no rows when not found
        "market_missing_text": MARKET_DATA_MISSING_TEXT,  # NEW - marker constant passed through to template
    }


def test_render_html_includes_company_name_and_missing_marker():  # test HTML render contains expected content
    html = render_html(_sample_context())  # render the template with the sample context
    assert "Test Co" in html  # company name should appear in rendered HTML
    assert MISSING_TEXT in html  # missing marker text should appear in rendered HTML


def test_render_html_spans_a_marker_only_row_across_the_period_columns():  # test C2's colspan on an empty financial row
    context = _sample_context()  # start from the minimal valid context
    context["financial_period_labels"] = ["Q2FY26", "Q2FY25"]  # two period columns in the header
    context["financial_table_rows"] = [  # one populated row and one row with no period data at all
        {  # populated row aligned to both header columns
            "metric_label": "Revenue",  # metric label
            "period_labels": ["Q2FY26", "Q2FY25"],  # header labels this row aligns to
            "values": ["100", "90"],  # one value per header column
            "yoy_growth": "11%",  # populated growth figure
            "qoq_growth": MISSING_TEXT,  # exercise the missing-field marker path
        },
        {  # row the source document supplied no period figures for
            "metric_label": "EBITDA",  # metric label
            "period_labels": ["Q2FY26", "Q2FY25"],  # header labels this row would align to
            "values": [MISSING_TEXT],  # single marker cell standing in for the whole row
            "yoy_growth": MISSING_TEXT,  # exercise the missing-field marker path
            "qoq_growth": MISSING_TEXT,  # exercise the missing-field marker path
        },
    ]
    html = render_html(context)  # render the template with this context
    assert "<th>Q2FY26</th>" in html  # header labels come from financial_period_labels, not row 0
    assert 'colspan="2"' in html  # the marker-only row spans both period columns instead of leaving one blank


def test_render_html_marks_an_empty_charts_section():  # test the defense-in-depth empty-charts marker
    context = _sample_context()  # sample context already has charts == []
    html = render_html(context)  # render the template with no chart images
    assert '<p class="missing">' in html  # the Charts section shows the marker rather than a bare heading


def test_render_pdf_returns_pdf_bytes():  # test PDF render produces a real PDF
    pdf_bytes = render_pdf(_sample_context())  # render the template straight to PDF bytes
    assert pdf_bytes[:4] == b"%PDF"  # PDF files start with this magic header
    assert len(pdf_bytes) > 500  # sanity check that the PDF has real content, not an empty stub


def test_render_html_shows_live_market_data_section_when_found():  # test the populated-section rendering path
    """A found market_data result renders the caption and all 5 rows."""
    context = _sample_context()  # start from the minimal valid context
    context["market_data"] = {"found": True, "caption": "Live market data (Yahoo Finance) for JSWENERGY.NS, fetched 2026-09-11 09:02 UTC — not from the uploaded document."}  # populated caption
    context["market_data_rows"] = [  # one populated row and one uncovered row
        {"label": "CMP", "value": "₹526.45"},
        {"label": "Rating", "value": MARKET_DATA_MISSING_TEXT},  # exercises the market-specific missing marker, not the document one
    ]
    html = render_html(context)  # render the template with this context
    assert "Live market data (Yahoo Finance)" in html  # caption present
    assert "₹526.45" in html  # populated field present
    assert MARKET_DATA_MISSING_TEXT in html  # market-specific marker present
    live_market_data_section = html.split("Live Market Data")[1].split("Business Summary")[0]  # isolate just this section's HTML, not everything after it (Business Summary legitimately uses MISSING_TEXT for its own, real document-extraction gap)
    assert "Not available in source document" not in live_market_data_section  # THE regression assertion: the document-extraction marker must never appear inside the Live Market Data section itself


def test_render_html_shows_not_available_line_when_market_data_not_found():  # test the not-found path shows one line, not an empty grid
    """A not-found market_data result renders a single explanatory line,
    no table, no 5 redundant "not available" rows."""
    context = _sample_context()  # default context already has market_data.found == False
    html = render_html(context)  # render the template with this context
    assert "Live market data: not available" in html  # single explanatory line present
    assert "not from the uploaded document" in html  # provenance disclosure still present even in the not-found case


def test_render_pdf_renders_rupee_symbol_correctly():  # regression test for the currency-glyph rendering verified manually during the design's rendering pre-mortem
    """Regression test: the ₹ symbol was verified to round-trip correctly
    through WeasyPrint with this project's exact font stack during the
    design's rendering pre-mortem (rendered a real PDF, extracted the
    text back out via pdfplumber, confirmed the character survived).
    Without this test, a future WeasyPrint or font-stack change could
    silently start dropping the glyph with nothing in CI to catch it."""
    import pdfplumber  # PDF text extraction, already a project dependency (used by app/ingestion)
    import io  # in-memory buffer for the PDF bytes

    context = _sample_context()  # start from the minimal valid context
    context["market_data"] = {"found": True, "caption": "Live market data (Yahoo Finance) for JSWENERGY.NS, fetched 2026-09-11 09:02 UTC — not from the uploaded document."}  # populated caption
    context["market_data_rows"] = [{"label": "CMP", "value": "₹526.45"}]  # the field carrying the glyph under test
    pdf_bytes = render_pdf(context)  # render all the way to PDF bytes, not just HTML

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:  # open the rendered PDF from memory
        extracted_text = pdf.pages[0].extract_text()  # extract real text from the rendered page

    assert "₹526.45" in extracted_text  # the rupee symbol survived the full HTML-to-PDF round-trip as a real character
