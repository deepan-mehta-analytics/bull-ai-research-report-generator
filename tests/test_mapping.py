"""Test suite for field mapping module - validates null-safety and field rendering."""
from app.extraction.schema import ReportData, CompanyData, FinancialRow, PeriodValue  # import schema models for testing
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
    row = FinancialRow(  # create financial row with one populated and one unstated period
        metric_label="Revenue",  # required metric label
        period_values=[  # ordered list of period/value objects
            PeriodValue(period_label="Q1FY26", value="100"),  # populated period
            PeriodValue(period_label="Q1FY25", value=None),  # period the document didn't state a value for
        ],
    )
    data = ReportData(company_name="Test Co", financial_table_rows=[row])  # create report with this row
    context = map_to_template_context(data, chart_images=[])  # call mapper with empty charts
    mapped_row = context["financial_table_rows"][0]  # extract first mapped financial row
    assert mapped_row["values"] == ["100", MISSING_TEXT]  # verify values list has MISSING_TEXT for None
    assert context["financial_period_labels"] == ["Q1FY26", "Q1FY25"]  # verify header labels match first-seen order


def test_financial_row_with_no_period_values_renders_single_marker():  # test the fully-empty-row fallback
    """A row that reported no periods at all must still render the
    missing-field marker, never blank whitespace."""
    row = FinancialRow(metric_label="Revenue")  # financial row with no period data whatsoever
    data = ReportData(company_name="Test Co", financial_table_rows=[row])  # create report with only that row
    context = map_to_template_context(data, chart_images=[])  # call mapper with empty charts
    assert context["financial_table_rows"][0]["values"] == [MISSING_TEXT]  # single marker cell stands in for the whole row


def test_period_labels_are_union_across_rows_and_values_align():  # test I2's union-header + per-row padding behavior
    """Rows with different period sets share one union header list, and each
    row's values are padded with MISSING_TEXT at the positions it lacks."""
    first_row = FinancialRow(  # row reporting two quarters
        metric_label="Revenue",  # required metric label
        period_values=[  # this row's periods
            PeriodValue(period_label="Q2FY26", value="100"),  # shared period
            PeriodValue(period_label="Q2FY25", value="90"),  # period unique to this row
        ],
    )
    second_row = FinancialRow(  # row reporting a partially overlapping period set
        metric_label="Net Worth",  # required metric label
        period_values=[  # this row's periods
            PeriodValue(period_label="Q2FY26", value="500"),  # shared period
            PeriodValue(period_label="FY25", value="480"),  # period unique to this row
        ],
    )
    data = ReportData(company_name="Test Co", financial_table_rows=[first_row, second_row])  # report containing both rows
    context = map_to_template_context(data, chart_images=[])  # call mapper with empty charts
    assert context["financial_period_labels"] == ["Q2FY26", "Q2FY25", "FY25"]  # union in first-seen order, de-duplicated
    assert context["financial_table_rows"][0]["values"] == ["100", "90", MISSING_TEXT]  # first row lacks FY25
    assert context["financial_table_rows"][1]["values"] == ["500", MISSING_TEXT, "480"]  # second row lacks Q2FY25, matched by label not position


def test_full_financials_has_its_own_independent_header_list():  # test that the two tables compute headers separately
    """The two tables must not share a header list - full_financials mixes
    P&L, balance-sheet, and ratio rows with different period sets."""
    quarterly_row = FinancialRow(metric_label="Revenue", period_values=[PeriodValue(period_label="Q2FY26", value="100")])  # quarterly table row
    full_row = FinancialRow(metric_label="Total Assets", period_values=[PeriodValue(period_label="FY25", value="900")])  # full-financials table row
    data = ReportData(company_name="Test Co", financial_table_rows=[quarterly_row], full_financials=[full_row])  # report with one row in each table
    context = map_to_template_context(data, chart_images=[])  # call mapper with empty charts
    assert context["financial_period_labels"] == ["Q2FY26"]  # quarterly header list holds only quarterly periods
    assert context["full_financials_period_labels"] == ["FY25"]  # full-financials header list is computed independently


def test_charts_and_company_name_pass_through():  # test that charts and company_name are preserved as-is
    """Verify that charts and company_name pass through unchanged."""
    data = ReportData(company_name="Example Corp")  # create test data with specific company name
    context = map_to_template_context(data, chart_images=["data:image/png;base64,abc"])  # call mapper with sample chart
    assert context["company_name"] == "Example Corp"  # verify company_name is unchanged
    assert context["charts"] == ["data:image/png;base64,abc"]  # verify charts list is unchanged
