"""Test suite for ticker resolution and market-data fetching. yfinance is
always mocked - this suite must never make a real network call, matching
the project's existing zero-network-in-CI guarantee."""
from unittest.mock import MagicMock, patch  # mock library for faking yfinance calls
from app.market_data.lookup import resolve_ticker  # function under test


def test_resolve_ticker_uses_provided_ticker_directly():  # test that an explicit ticker input skips search entirely
    """An explicit ticker input is trusted as-is, no search performed."""
    with patch("app.market_data.lookup.yf.Search") as mock_search:  # patch Search to prove it's never called
        result = resolve_ticker("JSW Energy", "JSWENERGY.NS")  # call with an explicit ticker
        assert result.symbol == "JSWENERGY.NS"  # the typed ticker is used verbatim
        assert result.auto_matched is False  # not resolved via search
        assert result.matched_name is None  # no search-derived name available
        mock_search.assert_not_called()  # search must never run when a ticker was provided


def test_resolve_ticker_strips_whitespace_from_provided_ticker():  # test that stray whitespace in the form field doesn't break the lookup
    """A ticker with leading/trailing whitespace (e.g. from a form field) is trimmed."""
    result = resolve_ticker("JSW Energy", "  JSWENERGY.NS  ")  # ticker with surrounding whitespace
    assert result.symbol == "JSWENERGY.NS"  # whitespace stripped


def test_resolve_ticker_auto_matches_single_unambiguous_ns_result():  # test the clean single-match auto-match path
    """A blank ticker triggers search; a single NSE match resolves cleanly."""
    mock_quotes = [  # simulates yf.Search("JSW Energy").quotes
        {"symbol": "JSWENERGY.NS", "shortname": "JSW ENERGY LIMITED", "quoteType": "EQUITY"},
        {"symbol": "JSWENERGY.BO", "shortname": "JSW ENERGY LTD", "quoteType": "EQUITY"},
    ]
    with patch("app.market_data.lookup.yf.Search") as mock_search_class:  # patch the Search class
        mock_search_class.return_value.quotes = mock_quotes  # configure the mocked instance's .quotes attribute
        result = resolve_ticker("JSW Energy", None)  # blank ticker triggers auto-match
        assert result.symbol == "JSWENERGY.NS"  # NSE preferred over BSE
        assert result.auto_matched is True  # resolved via search
        assert result.matched_name == "JSW ENERGY LIMITED"  # carried through for the caption
        mock_search_class.assert_called_once_with("JSW Energy", max_results=8, timeout=8)  # verify the native timeout param is used


def test_resolve_ticker_prefers_ns_over_higher_ranked_non_ns_result():  # test the real ICICI/IBN case found during the design spike
    """The NYSE ADR ranking first in raw search order must not win over
    the NSE listing - verified against real data during the design spike
    (searching "ICICI Bank" returns IBN before ICICIBANK.NS)."""
    mock_quotes = [  # mirrors the real search result order observed during the spike
        {"symbol": "IBN", "shortname": "ICICI Bank Limited", "quoteType": "EQUITY"},  # ranks first, wrong exchange
        {"symbol": "ICICIBANK.NS", "shortname": "ICICI BANK LTD.", "quoteType": "EQUITY"},  # ranks second, correct exchange
        {"symbol": "ICICIBANK.BO", "shortname": "ICICI BANK LTD.", "quoteType": "EQUITY"},
    ]
    with patch("app.market_data.lookup.yf.Search") as mock_search_class:  # patch the Search class
        mock_search_class.return_value.quotes = mock_quotes  # configure the mocked instance's .quotes attribute
        result = resolve_ticker("ICICI Bank", None)  # blank ticker triggers auto-match
        assert result.symbol == "ICICIBANK.NS"  # NSE preference wins despite ranking lower in raw search order


def test_resolve_ticker_returns_none_on_zero_search_results():  # test the real "Eternal Ltd" case found during the design spike
    """Zero search results must return None, never a guess - verified
    against this project's own placeholder test company name during the
    design spike (returns zero real results)."""
    with patch("app.market_data.lookup.yf.Search") as mock_search_class:  # patch the Search class
        mock_search_class.return_value.quotes = []  # simulates zero results
        result = resolve_ticker("Eternal Ltd", None)  # blank ticker triggers auto-match
        assert result is None  # never guess when nothing was found


def test_resolve_ticker_returns_none_on_ambiguous_candidates():  # test the real POCL case found during the design spike
    """Multiple candidates surviving the exchange filter but failing the
    name-overlap filter must return None, never guess between two
    unrelated real companies - verified against this project's own POCL
    test data during the design spike."""
    mock_quotes = [  # mirrors the real "POCL" search result set observed during the spike
        {"symbol": "POCL.NS", "shortname": "PONDY OXIDES & CHEM LTD", "quoteType": "EQUITY"},
        {"symbol": "POEL.NS", "shortname": "P O C L ENTERPRISES LTD.", "quoteType": "EQUITY"},
    ]
    with patch("app.market_data.lookup.yf.Search") as mock_search_class:  # patch the Search class
        mock_search_class.return_value.quotes = mock_quotes  # configure the mocked instance's .quotes attribute
        result = resolve_ticker("POCL", None)  # blank ticker triggers auto-match
        assert result is None  # neither candidate's name literally contains "pocl" as a word - correctly ambiguous/no-match


def test_resolve_ticker_filters_out_non_equity_quote_types():  # test that mutual funds etc. are excluded from candidates
    """A non-EQUITY quoteType (e.g. a mutual fund sharing a similar name)
    must never be treated as a candidate match."""
    mock_quotes = [  # simulates a mutual fund result alongside the real equity
        {"symbol": "LTTSX", "shortname": "MFS Lifetime Fund", "quoteType": "MUTUALFUND"},
        {"symbol": "LTTS.NS", "shortname": "L&T TECHNOLOGY SER. LTD.", "quoteType": "EQUITY"},
    ]
    with patch("app.market_data.lookup.yf.Search") as mock_search_class:  # patch the Search class
        mock_search_class.return_value.quotes = mock_quotes  # configure the mocked instance's .quotes attribute
        result = resolve_ticker("L&T Technology", None)  # blank ticker triggers auto-match, real company name (not the bare acronym)
        assert result.symbol == "LTTS.NS"  # the mutual fund never enters the candidate pool


def test_resolve_ticker_returns_none_on_search_exception():  # test that a network error during search degrades gracefully
    """Any exception from yf.Search (network error, malformed response)
    must return None, never propagate."""
    with patch("app.market_data.lookup.yf.Search", side_effect=ConnectionError("boom")):  # simulate a network failure
        result = resolve_ticker("JSW Energy", None)  # blank ticker triggers auto-match
        assert result is None  # never raises, never propagates the exception
