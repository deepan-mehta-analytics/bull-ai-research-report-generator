"""Turn a ReportData instance into the plain dict the Jinja2 template renders.

field_map.yaml is the single source of truth for which scalar
company-data fields exist and what they're labeled - see ADR-0004 for why
every value here is independently null-safe."""
from pathlib import Path  # pathlib for file path manipulation
import yaml  # yaml library for loading YAML configuration files
from ..extraction.schema import ReportData, FinancialRow  # import schema models from parent package

MISSING_TEXT = "Not available in source document"  # constant string for missing/null field values

FIELD_MAP_PATH = Path(__file__).parent / "field_map.yaml"  # path to field_map.yaml configuration file


def _load_field_map() -> dict:  # function to load field map from YAML file
    """Read field_map.yaml fresh on every call - it's a small file and this
    keeps the mapper stateless and simple to test."""
    with open(FIELD_MAP_PATH, "r", encoding="utf-8") as file_handle:  # open field_map.yaml in read mode
        return yaml.safe_load(file_handle)  # parse YAML and return as dict


def _display(value):  # function to render None/blank values as MISSING_TEXT
    """Render None or a blank string as the missing-field marker; pass
    everything else through unchanged."""
    if value is None or (isinstance(value, str) and not value.strip()):  # check if value is None or empty/whitespace string
        return MISSING_TEXT  # return missing text constant
    return value  # return value unchanged


def _map_company_data(report_data: ReportData, field_map: dict) -> list[dict]:  # function to map company data rows
    """Build the Company Data box rows from field_map.yaml's field list."""
    rows = []  # initialize empty list to hold mapped rows
    for entry in field_map["company_data_fields"]:  # iterate through each field definition in field_map
        raw_value = getattr(report_data.company_data, entry["source_attr"], None)  # get value from company_data using source_attr
        rows.append({"label": entry["label"], "value": _display(raw_value)})  # append row dict with label and displayed value
    return rows  # return list of mapped row dicts


def _union_period_labels(rows: list[FinancialRow]) -> list[str]:  # compute one ordered header list across all rows of a table
    """Build a single ordered union of every period label used by any row in
    the table, preserving first-seen order (dict.fromkeys keeps insertion
    order and de-duplicates without re-sorting)."""
    seen = []  # accumulator holding every period label in first-seen order, duplicates included
    for row in rows:  # iterate every FinancialRow belonging to this one table
        for period_value in row.period_values:  # iterate that row's ordered period/value pairs
            seen.append(period_value.period_label)  # record the label in the order it was encountered
    return list(dict.fromkeys(seen))  # de-duplicate while preserving insertion order


def _map_financial_rows(rows: list[FinancialRow], period_labels: list[str]) -> list[dict]:  # map rows onto one shared header list
    """Align every row against the table's shared period-label list: a row's
    values are emitted in header order, with MISSING_TEXT wherever that row
    has no entry for a given period. A row with no period data at all gets a
    single MISSING_TEXT cell, which the template spans across the columns."""
    mapped = []  # initialize empty list to hold mapped rows
    for row in rows:  # iterate through each FinancialRow
        by_label = {pv.period_label: pv.value for pv in row.period_values}  # index this row's values by their period label for O(1) lookup
        if not row.period_values:  # a row that reported no periods at all must still show the missing-field marker
            values = [MISSING_TEXT]  # single marker cell; the template gives it a colspan across the header columns
        else:  # the row has at least one period, so pad it out to the table's full header width
            values = [_display(by_label[label]) if label in by_label else MISSING_TEXT for label in period_labels]  # match by label, not position
        mapped.append(  # append mapped row to results list
            {  # create row dict with header-aligned period data
                "metric_label": row.metric_label,  # metric label from row
                "period_labels": period_labels,  # the table-wide header list this row's values are aligned to
                "values": values,  # header-aligned values, MISSING_TEXT filling any gap
                "yoy_growth": _display(row.yoy_growth),  # year-over-year growth with null-safety
                "qoq_growth": _display(row.qoq_growth),  # quarter-over-quarter growth with null-safety
            }  # end row dict
        )  # end append
    return mapped  # return list of mapped row dicts


def map_to_template_context(report_data: ReportData, chart_images: list[str]) -> dict:  # main function called by renderer
    """The one function the render layer calls - everything it needs is in
    the returned dict, already missing-field-safe."""
    field_map = _load_field_map()  # load field map from YAML
    financial_period_labels = _union_period_labels(report_data.financial_table_rows)  # one shared header list for the quarterly table
    full_financials_period_labels = _union_period_labels(report_data.full_financials)  # one shared header list for the full-financials table
    return {  # return context dict with all template data
        "company_name": report_data.company_name,  # company name pass-through
        "company_data_rows": _map_company_data(report_data, field_map),  # mapped company data rows
        "business_summary": _display(report_data.business_summary),  # business summary with null-safety
        "highlights": report_data.highlights if report_data.highlights else [MISSING_TEXT],  # highlights or [MISSING_TEXT] if empty
        "outlook": _display(report_data.outlook),  # outlook with null-safety
        "financial_period_labels": financial_period_labels,  # header labels the quarterly table's <th> loop reads
        "full_financials_period_labels": full_financials_period_labels,  # header labels the full-financials table's <th> loop reads
        "financial_table_rows": _map_financial_rows(report_data.financial_table_rows, financial_period_labels),  # mapped main financial rows
        "full_financials_rows": _map_financial_rows(report_data.full_financials, full_financials_period_labels),  # mapped extended financial rows
        "charts": chart_images,  # chart images pass-through; an empty list makes the template render MISSING_TEXT under the Charts heading
        "historical_ratings": report_data.historical_ratings  # historical ratings or [MISSING_TEXT] if empty
        if report_data.historical_ratings  # check if historical_ratings is non-empty
        else [MISSING_TEXT],  # use [MISSING_TEXT] if empty
        "missing_text": MISSING_TEXT,  # provide MISSING_TEXT constant to template
    }  # end context dict
