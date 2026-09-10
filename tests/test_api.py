# tests/test_api.py
from fastapi.testclient import TestClient  # test client for exercising FastAPI routes without a real server
import app.main as main_module  # import the main module itself so we can monkeypatch its extract_report_data reference
from app.main import app  # import the FastAPI app instance under test
from app.extraction.schema import ReportData, ChartSeries  # schema models used to build fake extraction results

client = TestClient(app)  # construct a test client bound to the app instance


def test_show_form_returns_html():  # verify GET / serves the upload form
    response = client.get("/")  # request the root page
    assert response.status_code == 200  # expect a successful response
    assert "Company name" in response.text  # expect the form label text to be present


def test_generate_report_returns_pdf(monkeypatch):  # verify POST /generate returns a PDF on the happy path
    fake_report = ReportData(  # build a minimal but valid ReportData with chart data present
        company_name="Test Co",  # company name field
        highlights=["Revenue grew 10%"],  # one highlight bullet
        chart_series=[ChartSeries(label="Revenue", categories=["Q1"], values=[100.0])],  # one chart series so the pipeline proceeds
    )
    monkeypatch.setattr(main_module, "extract_report_data", lambda text, name: fake_report)  # stub out the Claude-backed extraction call

    response = client.post(  # submit the generate form
        "/generate",  # target route
        data={"company_name": "Test Co"},  # form field
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},  # uploaded txt file
    )

    assert response.status_code == 200  # expect success
    assert response.headers["content-type"] == "application/pdf"  # expect a PDF content type
    assert response.content[:4] == b"%PDF"  # expect the response body to start with the PDF magic bytes


def test_generate_report_with_no_chart_data_shows_error(monkeypatch):  # verify missing chart data yields a 400 with an inline error
    fake_report = ReportData(company_name="Test Co")  # ReportData with no chart_series at all
    monkeypatch.setattr(main_module, "extract_report_data", lambda text, name: fake_report)  # stub out the Claude-backed extraction call

    response = client.post(  # submit the generate form
        "/generate",  # target route
        data={"company_name": "Test Co"},  # form field
        files={"file": ("notes.txt", b"No numbers here.", "text/plain")},  # uploaded txt file with no numeric trend data
    )

    assert response.status_code == 400  # expect a client error status
    assert "trend data" in response.text  # expect the inline error message to mention trend data
