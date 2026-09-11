"""Best-effort live market-data lookup (Yahoo Finance via yfinance) - see
ADR-0005. Every public function in this module is contracted to never
raise: a failure here must never be able to break the underlying
document-based report."""
import concurrent.futures  # thread-based hard timeout wrapper, transport-agnostic
from dataclasses import dataclass  # lightweight internal-only struct, no validation needed
from datetime import datetime, timezone  # for the stored fetched_at_utc timestamp
import yfinance as yf  # the Yahoo Finance client this module wraps

from .schema import MarketDataResult  # the result model this module produces
from .formatting import format_price, format_large_number, map_rating  # formatting helpers

MARKET_DATA_TIMEOUT_SECONDS = 8  # hard wall-clock cap on the whole lookup+fetch operation

# Module-level, created once at import time - shared across every request. Deliberately NOT a
# `with`-managed executor: exiting a `with` block calls shutdown(wait=True), which blocks until
# the submitted task actually finishes - defeating the timeout below the moment any call hangs.
# CONFIRMED BUG, fixed here: a with-managed pool re-blocked for the FULL hang duration on exit
# even though future.result(timeout=...) had already given up. See
# test_get_market_data_never_blocks_longer_than_the_timeout above - that test exists specifically
# because this bug was real, not hypothetical.
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)  # bounded worker count, module-level singleton


@dataclass
class ResolvedTicker:  # internal handoff between resolve_ticker and fetch_market_data (added Task 3)
    symbol: str  # the resolved ticker, e.g. "JSWENERGY.NS"
    auto_matched: bool  # True if found via search, False if the user typed it directly
    matched_name: str | None  # Yahoo's own name for the match, for the caption; None when user-typed


def resolve_ticker(company_name: str, ticker_input: str | None) -> ResolvedTicker | None:  # decide which ticker to query, or None if nothing confident
    if ticker_input and ticker_input.strip():  # explicit user input always wins, trusted as-is
        return ResolvedTicker(symbol=ticker_input.strip(), auto_matched=False, matched_name=None)  # no search performed

    try:  # auto-match path: search by company name
        results = yf.Search(company_name, max_results=8, timeout=8).quotes  # 8s cap, native param on Search
    except Exception:  # network error, malformed response, anything - never propagate
        return None  # caller treats this the same as "no match"

    equities = [r for r in results if r.get("quoteType") == "EQUITY"]  # drop mutual funds, etc.
    if not equities:  # zero results - never guess
        return None

    ns_matches = [r for r in equities if r.get("symbol", "").endswith(".NS")]  # prefer NSE
    bo_matches = [r for r in equities if r.get("symbol", "").endswith(".BO")]  # then BSE
    preferred_pool = ns_matches or bo_matches or equities  # fall back to whatever exists

    def name_matches(candidate: dict) -> bool:  # require real word overlap, not a substring guess
        cand_name = (candidate.get("shortname") or candidate.get("longname") or "").lower()  # candidate's own display name
        query_words = {w for w in company_name.lower().split() if len(w) > 2}  # skip short/noise words
        cand_words = {w for w in cand_name.split() if len(w) > 2}  # same filter on the candidate's name
        return bool(query_words & cand_words)  # any shared significant word counts as a match

    name_filtered = [r for r in preferred_pool if name_matches(r)]  # apply the name-overlap gate

    if len(name_filtered) != 1:  # zero or still-ambiguous - never guess among candidates
        return None

    match = name_filtered[0]  # the single unambiguous candidate
    return ResolvedTicker(
        symbol=match["symbol"],  # the matched ticker
        auto_matched=True,  # this came from search, not a typed ticker
        matched_name=match.get("shortname") or match.get("longname"),  # for the caption
    )


def fetch_market_data(resolved: ResolvedTicker) -> MarketDataResult:  # never raises - caller also wraps this, but this function contracts to the same guarantee
    try:  # the actual network call - anything here can fail (bad ticker, network, Yahoo schema change)
        info = yf.Ticker(resolved.symbol).info  # single call; .info is a plain dict, not a further-nested call chain
    except Exception:  # invalid ticker, network error, whatever - treat uniformly as "not found"
        return MarketDataResult(found=False)

    # a ticker is "valid" only if Yahoo actually recognizes it - an invalid symbol's .info
    # typically comes back near-empty rather than raising, so check for real identity, not just
    # "the dict has some key or other"
    has_identity = bool(info.get("shortName")) and (
        info.get("currentPrice") is not None or info.get("regularMarketPrice") is not None
    )
    if not has_identity:  # ticker didn't resolve to a real, quoted security
        return MarketDataResult(found=False)

    currency = info.get("currency", "")  # e.g. "INR" - drives symbol lookup and Cr/B/M formatting
    return MarketDataResult(
        found=True,  # a real security was found, even if individual fields below are None
        matched_ticker=resolved.symbol,  # echo back what was actually queried
        matched_company_name=resolved.matched_name or info.get("shortName"),  # prefer the search-time name, fall back to .info's
        was_auto_matched=resolved.auto_matched,  # carried through for the caption wording
        cmp=format_price(info.get("currentPrice") or info.get("regularMarketPrice"), currency),  # formatted current price
        market_cap=format_large_number(info.get("marketCap"), currency),  # formatted market cap
        target_price=format_price(info.get("targetMeanPrice"), currency),  # formatted analyst target price
        rating=map_rating(info.get("recommendationKey")),  # mapped rating, "none"/missing -> None
        sector=info.get("sector") or None,  # empty string treated as missing, not a valid sector name
        fetched_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),  # UTC, not server-local, to stay portable across deploy targets
    )


def get_market_data(company_name: str, ticker_input: str | None) -> MarketDataResult:  # never raises
    """Best-effort live market-data lookup. Always returns a result
    object, never an exception - this step must never be able to break
    the underlying document-based report."""
    def _do_lookup() -> MarketDataResult:  # runs on the shared executor, bounded by the timeout below
        resolved = resolve_ticker(company_name, ticker_input)  # first attempt: typed ticker, or auto-match if blank
        if resolved is None:  # nothing confident to query
            return MarketDataResult(found=False)
        result = fetch_market_data(resolved)  # try the resolved ticker
        if not result.found and not resolved.auto_matched and ticker_input:  # a user-typed ticker didn't resolve
            # A typo'd/wrong ticker shouldn't leave the user worse off than if they'd left the
            # field blank - give auto-match a second chance on company_name before giving up.
            # Bounded by the SAME outer timeout below - this whole function runs inside one
            # get_market_data() call, so the worst case is roughly double the network
            # round-trips within the existing 8s ceiling, not a new/separate timeout budget.
            fallback_resolved = resolve_ticker(company_name, ticker_input=None)  # force the auto-match path
            if fallback_resolved is not None:
                return fetch_market_data(fallback_resolved)
        return result

    future = _EXECUTOR.submit(_do_lookup)  # non-blocking; queues on the shared pool if all 4 workers are busy
    try:
        return future.result(timeout=MARKET_DATA_TIMEOUT_SECONDS)  # bounds THIS call regardless of queue/running state
    except Exception:  # timeout, or anything _do_lookup's own internal catches missed
        return MarketDataResult(found=False)  # the abandoned future is left to finish (or hang) in the background - a bounded, accepted trade-off (see ADR-0005 / spec §9)
