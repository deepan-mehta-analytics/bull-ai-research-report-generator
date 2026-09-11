"""Best-effort live market-data lookup (Yahoo Finance via yfinance) - see
ADR-0005. Every public function in this module is contracted to never
raise: a failure here must never be able to break the underlying
document-based report."""
from dataclasses import dataclass  # lightweight internal-only struct, no validation needed
import yfinance as yf  # the Yahoo Finance client this module wraps


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
