"""Test suite for field mapping module - validates null-safety and field rendering."""
from app.extraction.schema import ReportData, CompanyData, FinancialRow, PeriodValue  # import schema models for testing
from app.mapping.mapper import map_to_template_context, MISSING_TEXT, MARKET_DATA_MISSING_TEXT  # import mapper function and constants
from app.market_data.schema import MarketDataResult  # market-data result model for the new tests below


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


def test_market_data_missing_text_is_distinct_from_document_missing_text():  # THE regression test for the rendering contradiction bug found during spec review
    """Regression test for a real bug found during the spec's rendering
    pre-mortem: if these two constants were ever collapsed back into one
    (e.g. by someone "simplifying" the code later), a field inside a
    section explicitly captioned "not from the uploaded document" would
    literally say "Not available in source document" - a direct,
    reader-visible contradiction. This assertion is the permanent guard
    against that regression."""
    assert MARKET_DATA_MISSING_TEXT != MISSING_TEXT  # the two missing-field markers must never be the same string


def test_map_to_template_context_without_market_data_defaults_to_not_found():  # test full backward compatibility with every pre-existing call site
    """Every existing call site in this codebase calls
    map_to_template_context with exactly two arguments - the new third
    parameter must default to a safe "not found" result so none of them
    need to change."""
    data = ReportData(company_name="Test Co")  # minimal valid report data
    context = map_to_template_context(data, chart_images=[])  # called exactly as every pre-existing test already calls it, no market_data argument
    assert context["market_data"]["found"] is False  # defaults to not-found
    assert context["market_data_rows"] == []  # no rows when not found
    assert context["market_missing_text"] == MARKET_DATA_MISSING_TEXT  # constant is always present in the context


def test_map_to_template_context_with_found_market_data_manual_ticker():  # test the manually-typed-ticker caption and full row set
    """A found result from a manually-typed ticker produces the correct
    caption wording and all 5 rows, independently null-safe."""
    data = ReportData(company_name="Test Co")  # minimal valid report data
    market_data = MarketDataResult(  # a fully populated, manually-resolved result
        found=True, matched_ticker="JSWENERGY.NS", was_auto_matched=False,
        cmp="₹526.45", market_cap="₹96,465 Cr", target_price="₹614.00", rating="BUY", sector="Utilities",
        fetched_at_utc="2026-09-11T09:02:05+00:00",
    )
    context = map_to_template_context(data, chart_images=[], market_data=market_data)  # pass the market_data argument
    assert context["market_data"]["found"] is True  # found flag carried through
    assert "JSWENERGY.NS" in context["market_data"]["caption"]  # ticker present in caption
    assert "auto-matched" not in context["market_data"]["caption"]  # manual-ticker wording, not auto-match wording
    assert "not from the uploaded document" in context["market_data"]["caption"]  # required provenance disclosure
    assert "2026-09-11 09:02 UTC" in context["market_data"]["caption"]  # human-readable display timestamp, not the raw ISO string
    rows_by_label = {row["label"]: row["value"] for row in context["market_data_rows"]}  # index rows by label for easy assertion
    assert rows_by_label["CMP"] == "₹526.45"  # each field passed through as-is
    assert rows_by_label["Rating"] == "BUY"  # each field passed through as-is


def test_map_to_template_context_with_found_market_data_auto_matched():  # test the auto-match caption wording specifically
    """A found result from auto-match produces the auto-matched caption
    wording, including the matched company name."""
    data = ReportData(company_name="Test Co")  # minimal valid report data
    market_data = MarketDataResult(  # a result resolved via auto-match
        found=True, matched_ticker="JSWENERGY.NS", matched_company_name="JSW ENERGY LIMITED", was_auto_matched=True,
        cmp="₹526.45", fetched_at_utc="2026-09-11T09:02:05+00:00",
    )
    context = map_to_template_context(data, chart_images=[], market_data=market_data)  # pass the market_data argument
    assert "auto-matched" in context["market_data"]["caption"]  # auto-match wording present
    assert "JSW ENERGY LIMITED" in context["market_data"]["caption"]  # matched company name shown for verification


def test_map_to_template_context_with_partial_market_data_uses_market_missing_text():  # THE test proving the two missing-text markers are used correctly, not swapped
    """A field the market-data source doesn't cover (e.g. rating="none"
    from a real small-cap) must use MARKET_DATA_MISSING_TEXT, never the
    document-extraction MISSING_TEXT - this is what makes the caption's
    "not from the uploaded document" claim actually true for every value
    in the section, not just most of them."""
    data = ReportData(company_name="Test Co")  # minimal valid report data
    market_data = MarketDataResult(found=True, matched_ticker="POCL.NS", cmp="₹454.15", rating=None, fetched_at_utc="2026-09-11T09:02:05+00:00")  # rating genuinely uncovered
    context = map_to_template_context(data, chart_images=[], market_data=market_data)  # pass the market_data argument
    rows_by_label = {row["label"]: row["value"] for row in context["market_data_rows"]}  # index rows by label
    assert rows_by_label["Rating"] == MARKET_DATA_MISSING_TEXT  # uses the market-data-specific marker
    assert rows_by_label["Rating"] != MISSING_TEXT  # explicitly NOT the document-extraction marker
    assert rows_by_label["CMP"] == "₹454.15"  # the populated field is unaffected


def test_map_to_template_context_market_data_not_found_produces_no_rows():  # test the not-found path produces an empty row list, no caption
    """When market_data.found is False, no rows and no caption are
    built - the template shows a single line instead of an empty grid."""
    data = ReportData(company_name="Test Co")  # minimal valid report data
    market_data = MarketDataResult(found=False)  # explicit not-found result
    context = map_to_template_context(data, chart_images=[], market_data=market_data)  # pass the market_data argument
    assert context["market_data"]["found"] is False  # not-found flag carried through
    assert context["market_data"]["caption"] is None  # no caption to build when nothing was found
    assert context["market_data_rows"] == []  # no rows to render
