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


def test_generate_report_with_non_ascii_company_name(monkeypatch):  # verify a non-latin-1 company name doesn't blow up header encoding
    fake_report = ReportData(  # minimal valid ReportData with chart data present
        company_name="टेस्ट कंपनी",  # non-ASCII (Devanagari) company name, which latin-1 headers cannot encode
        chart_series=[ChartSeries(label="Revenue", categories=["Q1"], values=[100.0])],  # one chart series so the pipeline proceeds
    )
    monkeypatch.setattr(main_module, "extract_report_data", lambda text, name: fake_report)  # stub out the Claude-backed extraction call

    response = client.post(  # submit the generate form with a non-ASCII company name
        "/generate",  # target route
        data={"company_name": "टेस्ट कंपनी"},  # non-ASCII form field
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},  # uploaded txt file
    )

    assert response.status_code == 200  # expect success, not an unhandled 500 from header encoding
    assert response.headers["content-disposition"] == 'attachment; filename="report_report.pdf"'  # non-ASCII stripped, generic fallback used


def test_generate_report_caps_the_number_of_charts(monkeypatch):  # verify the chart-count cap is applied before rendering
    fake_report = ReportData(  # ReportData carrying far more chart series than the cap allows
        company_name="Test Co",  # company name field
        chart_series=[ChartSeries(label=f"Series {index}", categories=["Q1"], values=[1.0]) for index in range(10)],  # 10 series
    )
    monkeypatch.setattr(main_module, "extract_report_data", lambda text, name: fake_report)  # stub out the Claude-backed extraction call
    rendered_counts = []  # accumulator recording how many series reached the chart builder
    monkeypatch.setattr(  # replace build_charts with a spy that records its input size
        main_module,  # patch the reference the route actually calls
        "build_charts",  # the chart-building function
        lambda series: rendered_counts.append(len(series)) or ["data:image/png;base64,abc"],  # record then return one dummy image
    )

    client.post(  # submit the generate form
        "/generate",  # target route
        data={"company_name": "Test Co"},  # form field
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},  # uploaded txt file
    )

    assert rendered_counts == [main_module.MAX_CHART_SERIES]  # only the first MAX_CHART_SERIES series were rendered


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


def test_generate_report_accepts_optional_ticker_field(monkeypatch):  # test the new form field is accepted and used
    """The new ticker field is optional and, when provided, is passed
    through to get_market_data."""
    fake_report = ReportData(  # minimal valid ReportData with chart data present
        company_name="Test Co",
        chart_series=[ChartSeries(label="Revenue", categories=["Q1"], values=[100.0])],
    )
    monkeypatch.setattr(main_module, "extract_report_data", lambda text, name: fake_report)  # stub out the Claude-backed extraction call
    captured_args = []  # accumulator recording what get_market_data was called with
    monkeypatch.setattr(  # replace get_market_data with a spy that records its arguments
        main_module, "get_market_data",
        lambda company_name, ticker: captured_args.append((company_name, ticker)) or main_module.MarketDataResult(found=False),
    )

    response = client.post(  # submit the generate form with a ticker value
        "/generate",
        data={"company_name": "Test Co", "ticker": "JSWENERGY.NS"},  # includes the new field
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},
    )

    assert response.status_code == 200  # pipeline still succeeds
    assert captured_args == [("Test Co", "JSWENERGY.NS")]  # the typed ticker reached get_market_data unchanged


def test_generate_report_without_ticker_field_still_works(monkeypatch):  # test the pre-existing 2-field form submission (no ticker) still works
    """Every pre-existing caller of this route omits the ticker field
    entirely - the route must still work exactly as before."""
    fake_report = ReportData(  # minimal valid ReportData with chart data present
        company_name="Test Co",
        chart_series=[ChartSeries(label="Revenue", categories=["Q1"], values=[100.0])],
    )
    monkeypatch.setattr(main_module, "extract_report_data", lambda text, name: fake_report)  # stub out the Claude-backed extraction call
    monkeypatch.setattr(main_module, "get_market_data", lambda company_name, ticker: main_module.MarketDataResult(found=False))  # stub the new market-data step

    response = client.post(  # submit the generate form WITHOUT a ticker field, exactly as every pre-existing test does
        "/generate",
        data={"company_name": "Test Co"},
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},
    )

    assert response.status_code == 200  # still succeeds with the default empty ticker


def test_generate_report_survives_market_data_failure(monkeypatch):  # THE end-to-end test proving the core report is never broken by a market-data failure, even if get_market_data's own never-raise contract is somehow violated
    """get_market_data is contracted to never raise (Task 3's own tests
    prove this for every real failure mode). This test simulates the
    contract being violated anyway, to prove main.py's OWN local
    try/except (added in Step 3 below) is real defense-in-depth, not
    just a restated assumption - the report must still generate
    successfully even in this worst case, because that's what
    constraint #1 actually requires: unconditional, not
    every-case-we-thought-of."""
    fake_report = ReportData(  # minimal valid ReportData with chart data present
        company_name="Test Co",
        chart_series=[ChartSeries(label="Revenue", categories=["Q1"], values=[100.0])],
    )
    monkeypatch.setattr(main_module, "extract_report_data", lambda text, name: fake_report)  # stub out the Claude-backed extraction call
    def _raise(*args, **kwargs):  # simulates get_market_data somehow raising, despite its own contract never to
        raise RuntimeError("simulated total market-data failure")
    monkeypatch.setattr(main_module, "get_market_data", _raise)  # force the worst-case failure mode

    response = client.post(  # submit the generate form normally
        "/generate",
        data={"company_name": "Test Co"},
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},
    )

    assert response.status_code == 200  # the report still generates - main.py's own local defense-in-depth caught the simulated failure
    assert response.headers["content-type"] == "application/pdf"  # a real, working PDF, not a degraded response
