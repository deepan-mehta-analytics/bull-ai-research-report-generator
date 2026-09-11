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
        "financial_period_labels": [],  # no period columns in the quarterly table
        "full_financials_period_labels": [],  # no period columns in the full-financials table
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
