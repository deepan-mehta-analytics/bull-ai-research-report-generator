from unittest.mock import MagicMock  # mock library for creating fake Anthropic client
from app.extraction.extractor import extract_report_data  # function to test
from app.extraction.schema import ReportData  # schema class expected as output


def test_extract_report_data_returns_parsed_output():  # test that extraction client returns Claude's parsed ReportData
    """Verify extract_report_data calls Claude's parse API and returns ReportData unchanged."""
    fake_report = ReportData(company_name="Test Co", highlights=["Revenue grew"])  # create a ReportData instance with minimal fields
    fake_response = MagicMock()  # create mock response object
    fake_response.parsed_output = fake_report  # set the mock's parsed_output attribute to our test ReportData
    fake_client = MagicMock()  # create mock Anthropic client
    fake_client.messages.parse.return_value = fake_response  # set parse() method to return our mock response

    result = extract_report_data("some document text", "Test Co", client=fake_client)  # call extraction client with mocks

    assert result is fake_report  # verify the returned object is exactly the ReportData we created
    fake_client.messages.parse.assert_called_once()  # verify parse() was called exactly once
    call_kwargs = fake_client.messages.parse.call_args.kwargs  # extract keyword arguments from the parse() call
    assert call_kwargs["output_format"] is ReportData  # verify output_format parameter was set to ReportData class
    assert "Test Co" in call_kwargs["messages"][0]["content"]  # verify company name is in the prompt
    assert "some document text" in call_kwargs["messages"][0]["content"]  # verify document text is in the prompt
