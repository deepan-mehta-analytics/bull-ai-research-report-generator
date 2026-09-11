"""Pydantic model for the live market-data enrichment result. Every field
is Optional so a partial or total lookup failure never raises - same
missing-field philosophy as app/extraction/schema.py, applied to a second,
independent data source."""
from typing import Optional  # standard library type hints for optional fields
from pydantic import BaseModel  # pydantic base model


class MarketDataResult(BaseModel):  # everything the market-data step can produce for one report
    """Result of a best-effort live market-data lookup. found=True means a
    ticker was resolved and at least the basic quote succeeded - individual
    fields can still be None (e.g. a real small-cap with no analyst
    coverage), matching the per-field missing-data pattern used elsewhere
    in this codebase."""

    found: bool = False  # True if a ticker was resolved and the fetch didn't hard-fail
    matched_ticker: Optional[str] = None  # e.g. "JSWENERGY.NS", None if not found
    matched_company_name: Optional[str] = None  # Yahoo's own name for the matched ticker, for the caption
    was_auto_matched: bool = False  # True if resolved via search (not user-typed) - drives caption wording
    cmp: Optional[str] = None  # formatted current price, e.g. "₹526.45"
    market_cap: Optional[str] = None  # formatted market cap, e.g. "₹96,465 Cr" or "$1.23B"
    target_price: Optional[str] = None  # formatted analyst target price, e.g. "₹614.00"
    rating: Optional[str] = None  # mapped rating string, e.g. "BUY", None if uncovered/"none"
    sector: Optional[str] = None  # Yahoo's sector classification, e.g. "Utilities"
    fetched_at_utc: Optional[str] = None  # ISO 8601 UTC timestamp string - the STORED value; mapper.py derives a separate human-readable display string from this, they are deliberately not the same string
