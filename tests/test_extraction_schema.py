import pytest
from pydantic import ValidationError
from app.extraction.schema import ReportData, CompanyData, FinancialRow, ChartSeries

def test_report_data_defaults_to_empty_and_none():
    data = ReportData(company_name="Test Co")
    assert data.company_data.sector is None
    assert data.business_summary is None
    assert data.highlights == []
    assert data.chart_series == []

def test_financial_row_period_values_default_empty_dict():
    row = FinancialRow(metric_label="Revenue")
    assert row.period_values == {}
    assert row.yoy_growth is None

def test_chart_series_requires_label():
    with pytest.raises(ValidationError):
        ChartSeries()

def test_full_report_data_round_trip_from_dict():
    payload = {
        "company_name": "Eternal Ltd",
        "company_data": {"sector": "Internet & Catalogue Retail", "rating": "HOLD"},
        "highlights": ["Revenue up 70% YoY"],
        "chart_series": [
            {"label": "Revenue", "categories": ["Q1", "Q2"], "values": [100.0, 120.0]}
        ],
    }
    data = ReportData.model_validate(payload)
    assert data.company_data.sector == "Internet & Catalogue Retail"
    assert data.chart_series[0].values == [100.0, 120.0]
