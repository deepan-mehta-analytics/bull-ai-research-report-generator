import pytest  # pytest framework for test discovery and execution
from pydantic import ValidationError  # pydantic exception for validation failures
from app.extraction.schema import ReportData, CompanyData, FinancialRow, ChartSeries  # import schema models under test

def test_report_data_defaults_to_empty_and_none():  # verify ReportData field defaults when only company_name is provided
    data = ReportData(company_name="Test Co")  # create minimal ReportData instance
    assert data.company_data.sector is None  # sector defaults to None (missing field policy)
    assert data.business_summary is None  # business_summary defaults to None
    assert data.highlights == []  # highlights list defaults to empty
    assert data.chart_series == []  # chart_series list defaults to empty

def test_financial_row_period_values_default_empty_dict():  # verify FinancialRow dict field initializes empty
    row = FinancialRow(metric_label="Revenue")  # create minimal FinancialRow with required metric_label
    assert row.period_values == {}  # period_values defaults to empty dict (no extracted periods)
    assert row.yoy_growth is None  # yoy_growth defaults to None

def test_chart_series_requires_label():  # verify ChartSeries.label is a required field
    with pytest.raises(ValidationError):  # expect pydantic to raise ValidationError
        ChartSeries()  # attempt to create ChartSeries without required label field

def test_full_report_data_round_trip_from_dict():  # verify model_validate can parse nested dict structure into models
    payload = {  # complex nested payload with all field types
        "company_name": "Eternal Ltd",  # required company name
        "company_data": {"sector": "Internet & Catalogue Retail", "rating": "HOLD"},  # nested CompanyData object
        "highlights": ["Revenue up 70% YoY"],  # list of string highlights
        "chart_series": [  # list containing one chart
            {"label": "Revenue", "categories": ["Q1", "Q2"], "values": [100.0, 120.0]}  # ChartSeries with label, categories, values
        ],
    }
    data = ReportData.model_validate(payload)  # parse dict into ReportData instance via pydantic validation
    assert data.company_data.sector == "Internet & Catalogue Retail"  # verify nested CompanyData was parsed correctly
    assert data.chart_series[0].values == [100.0, 120.0]  # verify nested ChartSeries values were parsed as floats
