# tests/test_renderer.py
from app.render.renderer import render_html, render_pdf  # functions under test: HTML render and PDF render
from app.mapping.mapper import MISSING_TEXT  # shared missing-field marker constant used in fixture and assertions


def _sample_context():  # helper building a minimal valid context dict matching mapper's output shape
    return {  # return the sample context dict
        "company_name": "Test Co",  # simple company name value
        "company_data_rows": [{"label": "Sector", "value": "Banking"}],  # one populated company data row
        "business_summary": MISSING_TEXT,  # exercise the missing-field marker path
        "highlights": ["Revenue grew 10%"],  # one populated highlight
        "outlook": MISSING_TEXT,  # exercise the missing-field marker path
        "financial_table_rows": [],  # empty financial table
        "full_financials_rows": [],  # empty full financials table
        "charts": [],  # no chart images
        "historical_ratings": [MISSING_TEXT],  # exercise the missing-field marker path
        "missing_text": MISSING_TEXT,  # marker constant passed through to template
    }


def test_render_html_includes_company_name_and_missing_marker():  # test HTML render contains expected content
    html = render_html(_sample_context())  # render the template with the sample context
    assert "Test Co" in html  # company name should appear in rendered HTML
    assert MISSING_TEXT in html  # missing marker text should appear in rendered HTML


def test_render_pdf_returns_pdf_bytes():  # test PDF render produces a real PDF
    pdf_bytes = render_pdf(_sample_context())  # render the template straight to PDF bytes
    assert pdf_bytes[:4] == b"%PDF"  # PDF files start with this magic header
    assert len(pdf_bytes) > 500  # sanity check that the PDF has real content, not an empty stub
