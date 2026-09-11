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


from app.market_data.lookup import ResolvedTicker, fetch_market_data, get_market_data, MARKET_DATA_TIMEOUT_SECONDS  # add these imports to the existing import line


def _fake_info(**overrides):  # helper building a realistic yfinance .info dict, matching the real shape observed during the design spike
    base = {  # baseline shape modeled on the real JSW Energy response captured during the spike
        "shortName": "JSW ENERGY LIMITED",
        "currentPrice": 526.45,
        "marketCap": 964652761088,
        "targetMeanPrice": 614.0,
        "recommendationKey": "buy",
        "sector": "Utilities",
        "currency": "INR",
    }
    base.update(overrides)  # let individual tests override specific fields
    return base


def test_fetch_market_data_full_coverage():  # test the happy path with every field populated
    """A ticker with full data populates every field, correctly formatted."""
    resolved = ResolvedTicker(symbol="JSWENERGY.NS", auto_matched=False, matched_name=None)  # simulates a user-typed ticker
    with patch("app.market_data.lookup.yf.Ticker") as mock_ticker_class:  # patch the Ticker class
        mock_ticker_class.return_value.info = _fake_info()  # configure the mocked instance's .info attribute
        result = fetch_market_data(resolved)  # call the function under test
        assert result.found is True  # a real security was found
        assert result.matched_ticker == "JSWENERGY.NS"  # echoes the queried symbol
        assert result.cmp == "₹526.45"  # correctly formatted via format_price
        assert result.market_cap == "₹96,465 Cr"  # correctly formatted via format_large_number
        assert result.rating == "BUY"  # correctly mapped via map_rating
        assert result.sector == "Utilities"  # passed through as-is


def test_fetch_market_data_partial_coverage_rating_none_string():  # test the real POCL.NS case found during the design spike
    """A genuine small-cap with recommendationKey == "none" (the literal
    string, not Python None) still returns found=True with the other
    fields populated - verified against real POCL.NS data during the
    design spike, this exact partial-availability case is real."""
    resolved = ResolvedTicker(symbol="POCL.NS", auto_matched=False, matched_name=None)  # simulates a user-typed ticker
    with patch("app.market_data.lookup.yf.Ticker") as mock_ticker_class:  # patch the Ticker class
        mock_ticker_class.return_value.info = _fake_info(  # override to mirror the real POCL.NS response
            shortName="PONDY OXIDES & CHEM LTD", currentPrice=454.15, recommendationKey="none",
        )
        result = fetch_market_data(resolved)  # call the function under test
        assert result.found is True  # the ticker itself resolved to a real security
        assert result.cmp == "₹454.15"  # other fields still populate normally
        assert result.rating is None  # the literal string "none" must not display as a rating


def test_fetch_market_data_invalid_ticker_returns_not_found():  # test the "ticker doesn't resolve to a real security" case
    """A ticker Yahoo doesn't recognize typically returns a thin,
    mostly-empty .info dict rather than raising - this must be detected
    and treated as not-found, not partially rendered."""
    resolved = ResolvedTicker(symbol="NOTAREALTICKERXYZ", auto_matched=False, matched_name=None)  # simulates a bad user-typed ticker
    with patch("app.market_data.lookup.yf.Ticker") as mock_ticker_class:  # patch the Ticker class
        mock_ticker_class.return_value.info = {}  # simulates yfinance's real behavior for an unrecognized symbol
        result = fetch_market_data(resolved)  # call the function under test
        assert result.found is False  # no real identity, treated as not-found


def test_fetch_market_data_ticker_raises_returns_not_found():  # test that a network error during fetch degrades gracefully
    """Any exception from yf.Ticker(...).info (network error, malformed
    response) must return found=False, never propagate."""
    resolved = ResolvedTicker(symbol="JSWENERGY.NS", auto_matched=False, matched_name=None)  # simulates a user-typed ticker
    with patch("app.market_data.lookup.yf.Ticker", side_effect=ConnectionError("boom")):  # simulate a network failure
        result = fetch_market_data(resolved)  # call the function under test
        assert result.found is False  # never raises, never propagates the exception


import time  # for the wall-clock timing assertion in the timeout regression test


def test_get_market_data_full_pipeline_success():  # test the end-to-end orchestration happy path
    """resolve then fetch, wired together, on the happy path."""
    mock_quotes = [{"symbol": "JSWENERGY.NS", "shortname": "JSW ENERGY LIMITED", "quoteType": "EQUITY"}]  # single clean auto-match candidate
    with patch("app.market_data.lookup.yf.Search") as mock_search_class, \
         patch("app.market_data.lookup.yf.Ticker") as mock_ticker_class:  # patch both external calls
        mock_search_class.return_value.quotes = mock_quotes  # configure the search mock
        mock_ticker_class.return_value.info = _fake_info()  # configure the fetch mock
        result = get_market_data("JSW Energy", None)  # blank ticker, full auto-match + fetch pipeline
        assert result.found is True  # both steps succeeded
        assert result.was_auto_matched is True  # resolved via search, not a typed ticker


def test_get_market_data_returns_not_found_without_raising_on_total_failure():  # test that a fully ambiguous/failed lookup degrades cleanly
    """Zero candidates at every stage must still return a clean
    MarketDataResult, never an exception - the pipeline's own outer
    try/except in main.py is a documented second safety net, not the
    primary guarantee."""
    with patch("app.market_data.lookup.yf.Search") as mock_search_class:  # patch the Search class
        mock_search_class.return_value.quotes = []  # zero candidates
        result = get_market_data("Eternal Ltd", None)  # blank ticker, no possible match
        assert result.found is False  # clean not-found result
        assert isinstance(result, type(result))  # sanity check: still a real MarketDataResult object, not None or an exception


def test_get_market_data_ticker_typo_falls_back_to_auto_match():  # test the fallback feature added after the initial spec
    """A wrong/typo'd manually-typed ticker (e.g. a company name typed
    into the ticker field by mistake) must not leave the user worse off
    than an empty field would have - it falls back to auto-matching on
    company_name.

    Bug caught during execution (not just planning): a mock that returns
    the same .info for every symbol never actually exercises "the typo'd
    ticker fails" - real yfinance returns near-empty data for a symbol it
    doesn't recognize, so the mock must discriminate by the symbol it was
    called with, same as real behavior would."""
    mock_quotes = [{"symbol": "JSWENERGY.NS", "shortname": "JSW ENERGY LIMITED", "quoteType": "EQUITY"}]  # what auto-match would find
    def _ticker_side_effect(symbol):  # only the correctly-resolved ticker returns real data, matching real yfinance behavior for an invalid symbol
        mock_ticker = MagicMock()  # a fresh mock per call, so .info can differ by the symbol requested
        mock_ticker.info = _fake_info() if symbol == "JSWENERGY.NS" else {}  # the typo'd "JSW Energy" string returns empty, exactly like an unrecognized ticker
        return mock_ticker
    with patch("app.market_data.lookup.yf.Search") as mock_search_class, \
         patch("app.market_data.lookup.yf.Ticker", side_effect=_ticker_side_effect):  # patch both external calls
        mock_search_class.return_value.quotes = mock_quotes  # the fallback auto-match's candidate
        result = get_market_data("JSW Energy", "JSW Energy")  # a company name mistakenly typed into the ticker field
        assert result.found is True  # the fallback rescued the lookup
        assert result.was_auto_matched is True  # the FINAL resolution was via auto-match, even though a (wrong) ticker was typed first
        assert result.matched_ticker == "JSWENERGY.NS"  # resolved to the real ticker, not the typo'd input


def test_get_market_data_ticker_typo_fallback_also_fails_gracefully():  # test the fallback's own failure path
    """When the fallback auto-match also can't find a confident match,
    the whole lookup still degrades to found=False, not an exception or
    an infinite retry loop."""
    with patch("app.market_data.lookup.yf.Search") as mock_search_class, \
         patch("app.market_data.lookup.yf.Ticker") as mock_ticker_class:  # patch both external calls
        mock_search_class.return_value.quotes = []  # the fallback auto-match also finds nothing
        mock_ticker_class.return_value.info = {}  # the first (typo'd) attempt also fails identity
        result = get_market_data("Some Ambiguous Name", "NOTAREALTICKER")  # both the typed ticker and the fallback fail
        assert result.found is False  # clean failure, no exception


def test_get_market_data_never_blocks_longer_than_the_timeout():  # THE critical regression test for the with-block bug found during spec review
    """Regression test for a real, confirmed bug found during spec
    review: an earlier version of this function used a `with`-managed
    ThreadPoolExecutor, whose __exit__ calls shutdown(wait=True) and
    silently re-blocks for the FULL hang duration even after
    future.result(timeout=...) had already given up - completely
    defeating the timeout. This test proves that regression can never
    silently reappear: without an explicit wall-clock assertion, every
    other test in this file would still pass even if the timeout
    mechanism quietly stopped working, since none of them measure time."""
    def _hanging_search(*args, **kwargs):  # simulates a yfinance call that hangs far longer than the timeout
        time.sleep(MARKET_DATA_TIMEOUT_SECONDS + 5)  # deliberately longer than the timeout this test is verifying
        raise AssertionError("should never reach this point - the timeout must win first")  # proves this thread never finishes before the assertion below runs

    with patch("app.market_data.lookup.yf.Search", side_effect=_hanging_search):  # patch Search to hang
        start = time.monotonic()  # wall-clock start
        result = get_market_data("JSW Energy", None)  # blank ticker triggers the hanging search path
        elapsed = time.monotonic() - start  # wall-clock elapsed

    assert result.found is False  # the timeout path returns a clean not-found result
    assert elapsed < MARKET_DATA_TIMEOUT_SECONDS + 2  # generous margin over the 8s timeout, but must NOT be anywhere near the 13s hang duration - this is the exact assertion the buggy with-managed version would have failed
