from unittest.mock import MagicMock  # mock library for creating fake Anthropic client
from app.extraction.extractor import extract_report_data  # function to test
from app.extraction.schema import ReportData  # schema class expected as output


def test_extract_report_data_returns_parsed_output():  # test that extraction client returns Claude's parsed ReportData
    """Verify extract_report_data streams the request and returns the final message's parsed ReportData unchanged."""
    fake_report = ReportData(company_name="Test Co", highlights=["Revenue grew"])  # create a ReportData instance with minimal fields
    fake_final_message = MagicMock()  # create mock for the stream's accumulated final message
    fake_final_message.parsed_output = fake_report  # set the mock's parsed_output attribute to our test ReportData
    fake_stream = MagicMock()  # create mock for the stream object yielded by the `with` block
    fake_stream.get_final_message.return_value = fake_final_message  # get_final_message() returns the mock final message
    fake_client = MagicMock()  # create mock Anthropic client
    fake_client.messages.stream.return_value.__enter__.return_value = fake_stream  # stream() is used as a context manager, so mock its __enter__ result

    result = extract_report_data("some document text", "Test Co", client=fake_client)  # call extraction client with mocks

    assert result is fake_report  # verify the returned object is exactly the ReportData we created
    fake_client.messages.stream.assert_called_once()  # verify stream() was called exactly once
    call_kwargs = fake_client.messages.stream.call_args.kwargs  # extract keyword arguments from the stream() call
    assert call_kwargs["output_format"] is ReportData  # verify output_format parameter was set to ReportData class
    assert "Test Co" in call_kwargs["messages"][0]["content"]  # verify company name is in the prompt
    assert "some document text" in call_kwargs["messages"][0]["content"]  # verify document text is in the prompt
