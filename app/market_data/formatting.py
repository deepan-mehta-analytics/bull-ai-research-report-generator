"""Formatting helpers for live market-data fields - each function returns
None on a None/unrecognized input rather than raising, so callers never
need their own null-checks beyond what these already guarantee."""
from typing import Optional  # standard library type hints for optional fields

_CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}  # known currency codes mapped to their display symbol

_RATING_DISPLAY = {  # yfinance's recommendationKey values mapped to the report's display string
    "strong_buy": "STRONG BUY",  # highest-conviction positive rating
    "buy": "BUY",  # positive rating
    "hold": "HOLD",  # neutral rating
    "sell": "SELL",  # negative rating
    "strong_sell": "STRONG SELL",  # highest-conviction negative rating
}


def _currency_symbol(currency: str) -> str:  # look up a currency code's display symbol, falling back to the raw code
    if not currency:  # no currency info at all
        return ""  # no prefix rather than a guessed symbol
    return _CURRENCY_SYMBOLS.get(currency, f"{currency} ")  # unrecognized code prints as-is with a trailing space


def format_price(value: Optional[float], currency: str) -> Optional[str]:  # format a single price-like number (CMP, target price)
    if value is None:  # nothing to format
        return None  # missing, caller renders the not-available marker
    symbol = _currency_symbol(currency)  # resolve the currency's display symbol
    return f"{symbol}{value:,.2f}"  # e.g. "₹526.45"


def format_large_number(value: Optional[float], currency: str) -> Optional[str]:  # format a large number (market cap) using the currency's own convention
    if value is None:  # nothing to format
        return None  # missing, caller renders the not-available marker
    if currency == "INR":  # Indian Crore convention (1 Cr = 1e7)
        return f"₹{value / 1e7:,.0f} Cr"  # e.g. "₹96,465 Cr"
    symbol = _currency_symbol(currency)  # resolve the currency's display symbol for the billions/millions cases
    if value >= 1e9:  # large enough to show in billions
        return f"{symbol}{value / 1e9:.2f}B"  # e.g. "$1.23B"
    return f"{symbol}{value / 1e6:.2f}M"  # otherwise show in millions, e.g. "$450.00M"


def map_rating(recommendation_key: Optional[str]) -> Optional[str]:  # map yfinance's recommendationKey to the report's display rating
    if recommendation_key is None:  # key absent from the info dict
        return None  # missing, caller renders the not-available marker
    return _RATING_DISPLAY.get(recommendation_key)  # "none" and any unrecognized string both fall through to None via .get()'s default
