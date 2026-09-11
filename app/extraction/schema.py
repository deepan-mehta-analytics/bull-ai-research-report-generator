"""Pydantic models describing everything the extraction step can produce.

Every leaf field is Optional and every list defaults to empty - the model
must be able to represent "this document didn't say" without raising a
validation error, per the missing-field policy in the design spec.
"""
from typing import Optional  # standard library type hints for optional fields
from pydantic import BaseModel, Field  # pydantic base model and field configuration


class CompanyData(BaseModel):  # scalar header and data-box fields from document headers
    """Scalar header/data-box fields - the ones almost never present in an
    arbitrary uploaded document (rating, target price) as well as the ones
    that usually are (sector)."""

    sector: Optional[str] = None  # company's business sector/industry, None if not stated
    rating: Optional[str] = None  # analyst rating (BUY/HOLD/SELL), often missing from arbitrary docs
    target_price: Optional[str] = None  # target price per share as text, rarely present
    cmp: Optional[str] = None  # current market price as text, rarely present
    market_cap: Optional[str] = None  # market capitalization as text, rarely present


class PeriodValue(BaseModel):  # one period label paired with its reported value
    """One (period label, value) pair from a financial table row. Modelled as
    a closed object rather than an open-ended dict because structured output
    cannot express arbitrary dynamic keys, which silently yielded empty
    period data for every row."""

    period_label: str  # the exact period label as it appears in the source (e.g. "Q1FY26", "FY25")
    value: Optional[str] = None  # the reported value for that period, or None if not stated


class FinancialRow(BaseModel):  # single row in a financial metrics table
    """One row of a financial table - each PeriodValue's period_label is the
    period name (e.g. "Q1FY26") exactly as the source document labels it,
    since different sectors report on different calendars and cadences."""

    metric_label: str  # row header label (e.g., "Revenue", "Net Profit"), always present
    period_values: list[PeriodValue] = Field(default_factory=list)  # ordered period/value pairs for this row, empty if not extracted
    yoy_growth: Optional[str] = None  # year-over-year growth percentage as text, None if absent
    qoq_growth: Optional[str] = None  # quarter-over-quarter growth percentage as text, None if absent


class ChartSeries(BaseModel):  # single chart's data series
    """One chart's worth of data - the render layer produces exactly one
    chart per entry in ReportData.chart_series."""

    label: str  # chart title/legend (e.g., "Revenue", "Market Share"), required
    categories: list[str] = Field(default_factory=list)  # x-axis labels (Q1/Q2/etc), empty if not extracted
    values: list[float] = Field(default_factory=list)  # numeric y-axis values, empty if not extracted


class ReportData(BaseModel):  # complete extraction output for one report
    """The full extraction output for one report."""

    company_name: str  # report subject company name, always required
    company_data: CompanyData = Field(default_factory=CompanyData)  # nested scalar fields from header/data-box
    business_summary: Optional[str] = None  # executive summary or overview text, None if not present
    highlights: list[str] = Field(default_factory=list)  # bullet-point takeaways from the report, empty if none extracted
    outlook: Optional[str] = None  # forward guidance or future outlook text, None if not stated
    financial_table_rows: list[FinancialRow] = Field(default_factory=list)  # financial metrics rows from main tables, empty if none
    full_financials: list[FinancialRow] = Field(default_factory=list)  # extended financial metrics (additional tables), empty if none
    chart_series: list[ChartSeries] = Field(default_factory=list)  # chart data series for rendering, empty if no charts extracted
    historical_ratings: list[str] = Field(default_factory=list)  # historical analyst ratings timeline, empty if not present
