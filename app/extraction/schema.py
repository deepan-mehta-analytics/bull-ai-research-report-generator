"""Pydantic models describing everything the extraction step can produce.

Every leaf field is Optional and every list defaults to empty - the model
must be able to represent "this document didn't say" without raising a
validation error, per the missing-field policy in the design spec.
"""
from typing import Optional
from pydantic import BaseModel, Field


class CompanyData(BaseModel):
    """Scalar header/data-box fields - the ones almost never present in an
    arbitrary uploaded document (rating, target price) as well as the ones
    that usually are (sector)."""

    sector: Optional[str] = None
    rating: Optional[str] = None
    target_price: Optional[str] = None
    cmp: Optional[str] = None
    market_cap: Optional[str] = None


class FinancialRow(BaseModel):
    """One row of a financial table - period_values keys are period labels
    (e.g. "Q1FY26") exactly as the source document labels them, since
    different sectors report on different calendars and cadences."""

    metric_label: str
    period_values: dict[str, Optional[str]] = Field(default_factory=dict)
    yoy_growth: Optional[str] = None
    qoq_growth: Optional[str] = None


class ChartSeries(BaseModel):
    """One chart's worth of data - the render layer produces exactly one
    chart per entry in ReportData.chart_series."""

    label: str
    categories: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)


class ReportData(BaseModel):
    """The full extraction output for one report."""

    company_name: str
    company_data: CompanyData = Field(default_factory=CompanyData)
    business_summary: Optional[str] = None
    highlights: list[str] = Field(default_factory=list)
    outlook: Optional[str] = None
    financial_table_rows: list[FinancialRow] = Field(default_factory=list)
    full_financials: list[FinancialRow] = Field(default_factory=list)
    chart_series: list[ChartSeries] = Field(default_factory=list)
    historical_ratings: list[str] = Field(default_factory=list)
