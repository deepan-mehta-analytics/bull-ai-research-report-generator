"""Test suite for field mapping module - validates null-safety and field rendering."""
from app.extraction.schema import ReportData, CompanyData, FinancialRow  # import schema models for testing
from app.mapping.mapper import map_to_template_context, MISSING_TEXT  # import mapper function and constant


def test_missing_company_data_field_marked_clearly():  # test that missing company fields render MISSING_TEXT
    """Verify that None/empty company data fields render as MISSING_TEXT."""
    data = ReportData(company_name="Test Co", company_data=CompanyData(sector="Banking"))  # create test data with sector but no rating
    context = map_to_template_context(data, chart_images=["data:image/png;base64,xyz"])  # call mapper with sample chart image
    rating_row = next(r for r in context["company_data_rows"] if r["label"] == "Rating")  # find Rating row in output
    assert rating_row["value"] == MISSING_TEXT  # verify missing rating renders as MISSING_TEXT
    sector_row = next(r for r in context["company_data_rows"] if r["label"] == "Sector")  # find Sector row in output
    assert sector_row["value"] == "Banking"  # verify present sector renders as-is


def test_empty_highlights_render_missing_placeholder():  # test that empty highlights list renders [MISSING_TEXT]
    """Verify that empty highlights list renders as [MISSING_TEXT]."""
    data = ReportData(company_name="Test Co")  # create test data with no highlights
    context = map_to_template_context(data, chart_images=[])  # call mapper with empty charts
    assert context["highlights"] == [MISSING_TEXT]  # verify empty highlights becomes [MISSING_TEXT]


def test_financial_row_missing_period_value_marked():  # test that None values in period_values render as MISSING_TEXT
    """Verify that None values in financial row period_values are marked."""
    row = FinancialRow(metric_label="Revenue", period_values={"Q1FY26": "100", "Q1FY25": None})  # create financial row with mixed values
    data = ReportData(company_name="Test Co", financial_table_rows=[row])  # create report with this row
    context = map_to_template_context(data, chart_images=[])  # call mapper with empty charts
    mapped_row = context["financial_table_rows"][0]  # extract first mapped financial row
    assert mapped_row["values"] == ["100", MISSING_TEXT]  # verify values list has MISSING_TEXT for None
    assert mapped_row["period_labels"] == ["Q1FY26", "Q1FY25"]  # verify period labels match insertion order


def test_charts_and_company_name_pass_through():  # test that charts and company_name are preserved as-is
    """Verify that charts and company_name pass through unchanged."""
    data = ReportData(company_name="Eternal Ltd")  # create test data with specific company name
    context = map_to_template_context(data, chart_images=["data:image/png;base64,abc"])  # call mapper with sample chart
    assert context["company_name"] == "Eternal Ltd"  # verify company_name is unchanged
    assert context["charts"] == ["data:image/png;base64,abc"]  # verify charts list is unchanged
