# tests/test_api.py
import base64  # decode the data: URI download link embedded in the success page
import httpx2  # build minimal request/response objects to construct real anthropic SDK exceptions
import anthropic  # exception types the friendly-error mapping must recognize
import pydantic  # ValidationError, the other exception type the friendly-error mapping must recognize
from fastapi.testclient import TestClient  # test client for exercising FastAPI routes without a real server
import app.main as main_module  # import the main module itself so we can monkeypatch its extract_report_data reference
from app.main import app  # import the FastAPI app instance under test
from app.extraction.schema import ReportData, ChartSeries  # schema models used to build fake extraction results

client = TestClient(app)  # construct a test client bound to the app instance


def _extract_data_uri_pdf_bytes(html: str) -> bytes:  # helper: pull the base64 PDF payload out of a success page's download link
    marker = "data:application/pdf;base64,"  # the fixed prefix every data-URI download link starts with
    start = html.index(marker) + len(marker)  # position right after the prefix
    end = html.index('"', start)  # the closing quote of the href attribute
    return base64.b64decode(html[start:end])  # decode back to raw PDF bytes for assertions


def test_show_form_returns_html():  # verify GET / serves the upload form
    response = client.get("/")  # request the root page
    assert response.status_code == 200  # expect a successful response
    assert "Company name" in response.text  # expect the form label text to be present


def test_generate_report_returns_success_page_with_embedded_download(monkeypatch):  # verify POST /generate returns a success page with a working download link on the happy path
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
    assert "text/html" in response.headers["content-type"]  # a real confirmation page, not a raw file response
    assert "Test Co" in response.text  # the success page names the company the report was generated for
    assert _extract_data_uri_pdf_bytes(response.text)[:4] == b"%PDF"  # the embedded download link decodes to a real PDF
    assert "/" in response.text  # a way back to the form ("Generate another report") is present


def test_generate_report_success_page_links_back_to_form(monkeypatch):  # verify the success page offers a way to generate another report
    fake_report = ReportData(  # minimal valid ReportData with chart data present
        company_name="Test Co",
        chart_series=[ChartSeries(label="Revenue", categories=["Q1"], values=[100.0])],
    )
    monkeypatch.setattr(main_module, "extract_report_data", lambda text, name: fake_report)  # stub out the Claude-backed extraction call

    response = client.post(  # submit the generate form
        "/generate",
        data={"company_name": "Test Co"},
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},
    )

    assert 'href="/"' in response.text  # a plain link back to the upload form, no JS navigation needed


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

    assert response.status_code == 200  # expect success, not an unhandled 500 from filename sanitization
    assert 'download="report_report.pdf"' in response.text  # non-ASCII stripped, generic fallback used as the download attribute


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
    assert "Couldn" in response.text  # expect the failure heading ("Couldn't generate your report") to be present


def test_generate_report_friendly_message_for_rate_limit_error(monkeypatch):  # verify a rate-limit error shows plain-language text instead of the raw SDK message
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")  # minimal request object the SDK exception needs
    response_obj = httpx2.Response(429, request=request)  # minimal 429 response object the SDK exception needs
    def _raise(text, name):  # stub raising the real anthropic SDK exception type
        raise anthropic.RateLimitError("rate limited internally", response=response_obj, body=None)
    monkeypatch.setattr(main_module, "extract_report_data", _raise)  # force the rate-limit failure mode

    response = client.post(  # submit the generate form
        "/generate",
        data={"company_name": "Test Co"},
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},
    )

    assert response.status_code == 400  # still a client-visible error
    assert "busy" in response.text.lower() or "try again" in response.text.lower()  # plain-language message shown
    assert "rate limited internally" not in response.text  # the raw SDK message text is not leaked to the user


def test_generate_report_friendly_message_for_connection_error(monkeypatch):  # verify a connection error shows plain-language text instead of the raw SDK message
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")  # minimal request object the SDK exception needs
    def _raise(text, name):  # stub raising the real anthropic SDK exception type
        raise anthropic.APIConnectionError(message="raw connection failure detail", request=request)
    monkeypatch.setattr(main_module, "extract_report_data", _raise)  # force the connection-failure mode

    response = client.post(  # submit the generate form
        "/generate",
        data={"company_name": "Test Co"},
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},
    )

    assert response.status_code == 400  # still a client-visible error
    assert "connect" in response.text.lower() or "reach" in response.text.lower()  # plain-language message shown
    assert "raw connection failure detail" not in response.text  # the raw SDK message text is not leaked to the user


def test_generate_report_friendly_message_for_schema_validation_error(monkeypatch):  # verify a pydantic validation error shows plain-language text instead of the raw error dump
    def _raise(text, name):  # stub raising a real pydantic ValidationError, as extraction schema mismatches do
        ReportData.model_validate({"chart_series": "not a list"})  # deliberately invalid shape triggers a real ValidationError
    monkeypatch.setattr(main_module, "extract_report_data", _raise)  # force the schema-validation failure mode

    response = client.post(  # submit the generate form
        "/generate",
        data={"company_name": "Test Co"},
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},
    )

    assert response.status_code == 400  # still a client-visible error
    assert "expected shape" in response.text.lower() or "try again" in response.text.lower()  # plain-language message shown
    assert "validation error" not in response.text.lower()  # the raw pydantic error dump is not leaked to the user


def test_generate_report_unanticipated_error_falls_back_to_raw_message(monkeypatch):  # verify the existing behavior is unchanged for any exception type without a specific mapping
    def _raise(text, name):  # stub raising an exception type with no specific friendly mapping
        raise RuntimeError("a totally unanticipated internal failure")
    monkeypatch.setattr(main_module, "extract_report_data", _raise)  # force an unmapped failure mode

    response = client.post(  # submit the generate form
        "/generate",
        data={"company_name": "Test Co"},
        files={"file": ("notes.txt", b"Revenue grew 10 percent.", "text/plain")},
    )

    assert response.status_code == 400  # still a client-visible error
    assert "a totally unanticipated internal failure" in response.text  # unmapped exceptions still show their real message, no regression


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
    assert _extract_data_uri_pdf_bytes(response.text)[:4] == b"%PDF"  # a real, working PDF is embedded, not a degraded response
