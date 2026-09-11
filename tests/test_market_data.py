"""Test suite for the market-data schema and formatting helpers."""
from app.market_data.schema import MarketDataResult  # model under test
from app.market_data.formatting import format_price, format_large_number, map_rating  # functions under test


def test_market_data_result_defaults_to_not_found():  # test that an empty MarketDataResult is a safe "not found" sentinel
    """A MarketDataResult constructed with no arguments must default to
    found=False and every other field None - this is the value mapper.py
    uses when no market_data argument is passed at all."""
    result = MarketDataResult()  # construct with zero arguments
    assert result.found is False  # must default to not-found
    assert result.matched_ticker is None  # every other field defaults to None
    assert result.cmp is None  # every other field defaults to None
    assert result.rating is None  # every other field defaults to None


def test_format_price_with_inr():  # test INR price formatting with the rupee symbol
    """A price with currency INR renders with the rupee symbol and two decimals."""
    assert format_price(526.45, "INR") == "₹526.45"  # verify exact rupee formatting


def test_format_price_with_usd():  # test USD price formatting with the dollar symbol
    """A price with currency USD renders with the dollar symbol."""
    assert format_price(123.4, "USD") == "$123.40"  # verify exact dollar formatting, padded to two decimals


def test_format_price_with_none_value():  # test that a missing price returns None, not a crash
    """A None value must return None - the caller renders the missing marker."""
    assert format_price(None, "INR") is None  # verify None passthrough


def test_format_price_with_unrecognized_currency():  # test the fallback for a currency code not in the known symbol map
    """An unrecognized currency code prints as its raw code with a
    trailing space, never a guessed symbol."""
    assert format_price(100.0, "JPY") == "JPY 100.00"  # verify raw-code fallback, not a wrong symbol


def test_format_large_number_inr_uses_crore():  # test the Indian Crore convention for market cap
    """INR market cap divides by 1e7 and appends 'Cr' - verified during
    the design spike against JSW Energy's real market cap."""
    assert format_large_number(964652761088, "INR") == "₹96,465 Cr"  # matches the real spike value exactly


def test_format_large_number_usd_uses_billions():  # test the billions convention for a large non-INR market cap
    """A non-INR value >= 1e9 formats in billions."""
    assert format_large_number(1_230_000_000, "USD") == "$1.23B"  # verify billions formatting


def test_format_large_number_usd_uses_millions_below_a_billion():  # test the millions convention for a smaller non-INR market cap
    """A non-INR value below 1e9 formats in millions, not billions."""
    assert format_large_number(450_000_000, "USD") == "$450.00M"  # verify millions formatting


def test_format_large_number_with_none_value():  # test that a missing market cap returns None, not a crash
    """A None value must return None - the caller renders the missing marker."""
    assert format_large_number(None, "INR") is None  # verify None passthrough


def test_map_rating_known_values():  # test the full rating mapping table
    """Every known recommendationKey value maps to its display string."""
    assert map_rating("strong_buy") == "STRONG BUY"  # highest-conviction positive
    assert map_rating("buy") == "BUY"  # positive
    assert map_rating("hold") == "HOLD"  # neutral
    assert map_rating("sell") == "SELL"  # negative
    assert map_rating("strong_sell") == "STRONG SELL"  # highest-conviction negative


def test_map_rating_none_string_is_not_available():  # test the real POCL.NS case found during the design spike
    """yfinance's literal string "none" (not Python None) must map to
    Python None, not be displayed as the literal text "none" - this is a
    real case, verified against POCL.NS during the design spike, not
    hypothetical."""
    assert map_rating("none") is None  # verify the literal string "none" is treated as missing


def test_map_rating_missing_key_is_not_available():  # test the case where recommendationKey is absent entirely
    """A None input (key missing from .info) also maps to None."""
    assert map_rating(None) is None  # verify None passthrough


def test_map_rating_unrecognized_value_is_not_available():  # test defensive handling of an unexpected future yfinance value
    """Any string not in the known mapping table falls through to None
    rather than displaying a raw, unrecognized value in the report."""
    assert map_rating("some_future_value") is None  # verify unrecognized values never leak through raw
