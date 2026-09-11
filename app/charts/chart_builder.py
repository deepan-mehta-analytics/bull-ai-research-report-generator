"""Render one bar chart per ChartSeries with matplotlib, returned as
base64 PNG data URIs ready to drop into an <img src="..."> tag. Dual-axis
bar+growth-line overlay, matching the reference sample's own chart style
- a deliberate exception to general dataviz best practice, made because
this project's ADR-0004 already commits to sample fidelity over generic
convention, and dual-axis bar+line value/growth charts are standard
practice in the equity-research domain this project and its reference
sample both belong to (see ADR-0006). Growth is computed arithmetically
from already-extracted ChartSeries.values, gated by a whole-series
period-format guard - never requested from Claude (see ADR-0006 and the
design spec for the full reasoning).

Uses the object-oriented Figure/FigureCanvasAgg API rather than the
global pyplot state machine: the FastAPI route is a plain `def` handler,
so it runs in a threadpool where concurrent requests would otherwise
share (and corrupt) pyplot's process-wide figure registry."""
import re  # standard library, for the period-format classification below
import base64  # encoding library for base64 conversion
import io  # in-memory file buffer for image data
from matplotlib.figure import Figure  # object-oriented figure class, no global pyplot state
from matplotlib.backends.backend_agg import FigureCanvasAgg  # Agg renderer attached explicitly to each figure
from ..extraction.schema import ChartSeries  # import data model for chart series

MAX_CHART_SERIES = 4  # upper bound on charts per report; extraction has returned 17 series for one document, which overflows the layout by pages

SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]  # validated 3-hue categorical set (dataviz skill, all-pairs PASS); a 4th chart reuses index 0, see ADR-0006
GROWTH_LINE_COLOR = "#0b0b0b"  # text-primary token, not a competing categorical hue - see ADR-0006 for the rationale

_QUARTER_RE = re.compile(r"\bQ\d", re.IGNORECASE)  # matches "Q1", "Q2-2025", "Q2 FY26", "Q2FY26" - no trailing \b, since "1" and "F" share no word boundary
_HALF_RE = re.compile(r"\bH\d", re.IGNORECASE)  # matches "H1", "H1 FY25", "H1FY26" - same trailing-boundary fix as _QUARTER_RE
_YEAR_RE = re.compile(r"\bFY\d{2,4}\b", re.IGNORECASE)  # matches "FY2025", "FY25" (checked only if Q/H didn't already match)


def _period_format(label: str) -> str | None:  # classify one category label's period type, or None if unrecognized
    """Classify a category label's period granularity. Order matters: a
    label like "Q2 FY26" must classify as "quarter", not "year", so the
    quarter/half checks run before the bare-year check."""
    if _QUARTER_RE.search(label):  # check quarter pattern first - it can co-occur with an FY token
        return "quarter"  # e.g. "Q2-2025", "Q2 FY26"
    if _HALF_RE.search(label):  # then half-year pattern, same reasoning
        return "half"  # e.g. "H1 FY25"
    if _YEAR_RE.search(label):  # only a bare "FY####" with no Q/H prefix
        return "year"  # e.g. "FY2025"
    return None  # unrecognized format - never guess, this excludes the whole series from growth (see _all_same_format)


def _all_same_format(categories: list[str]) -> bool:  # whole-series guard: every label must share one period type
    """True only if every category in the series classifies to the SAME
    non-None period format. A mixed series (e.g. JSW Energy's real
    Q2 FY25/Q2 FY26/H1 FY25/H1 FY26) or any unrecognized label returns
    False, which skips the growth line for the whole series - safer than
    guessing at partial/per-pair validity."""
    formats = {_period_format(label) for label in categories}  # set of distinct classifications across the series
    return len(formats) == 1 and None not in formats  # exactly one format, and it's a recognized one


def _compute_growth(values: list[float]) -> list[float | None]:  # index-adjacent % growth, aligned to `values`
    """Period-over-period growth as a percentage, aligned 1:1 with `values`.
    growth[0] is always None (no prior point). growth[i] is None when the
    prior value is zero (undefined growth) rather than raising or
    returning inf/nan - consistent with this module's "skip rather than
    raise" pattern. Caller is responsible for calling this ONLY when
    `_all_same_format` is True; this function does not re-check format, it
    only guards against division by zero."""
    growth: list[float | None] = [None]  # first point has no prior point to compare against
    for previous, current in zip(values, values[1:]):  # pair each value with its immediate predecessor
        growth.append(None if previous == 0 else (current - previous) / previous * 100)  # None on div-by-zero, else % change
    return growth


def _render_single_chart(series: ChartSeries, color: str) -> str | None:  # render one series as a dual-axis chart, or None if it isn't plottable
    """Draw one series as a bar chart, with an optional growth-% line
    overlay, and return it as a base64 data URI, or None when the series
    has no usable data. Categories and values are truncated to their
    common length so a ragged extraction result can never raise a raw
    matplotlib exception through the caller."""
    usable_length = min(len(series.categories), len(series.values))  # longest prefix where both lists have a paired entry
    if usable_length == 0:  # nothing to plot if either list is empty (or they share no common prefix)
        return None  # signal "skip this series" to build_charts
    categories = series.categories[:usable_length]  # truncate labels to the common length
    values = series.values[:usable_length]  # truncate values to the same common length

    growth = _compute_growth(values) if _all_same_format(categories) else [None] * usable_length  # whole-series guard before computing anything
    valid_growth_points = [(i, g) for i, g in enumerate(growth) if g is not None]  # indices/values where a real growth number exists

    figure = Figure(figsize=(6, 3.2), dpi=150)  # construct a standalone figure with no pyplot involvement
    FigureCanvasAgg(figure)  # attach an Agg canvas so the figure can render itself to PNG
    axis = figure.subplots()  # create the primary (value/bar) axes this chart draws on
    x_positions = range(usable_length)  # create x-axis position indices
    axis.bar(x_positions, values, color=color, label=series.label)  # draw bars with this series' assigned color; label feeds the legend below
    axis.set_xticks(list(x_positions))  # set tick positions on x-axis
    axis.set_xticklabels(categories, fontsize=8)  # label x-axis ticks with category names
    axis.set_title(series.label, fontsize=10, fontweight="bold")  # set chart title from series label - the real identity channel across charts

    last_index = usable_length - 1  # position of the most recent period's bar
    axis.annotate(  # selective value label - last bar only, never on every point (dataviz skill mark-spec)
        f"{values[last_index]:,.1f}",  # the most recent period's value, formatted with thousands separators
        xy=(last_index, values[last_index]),  # anchor point: the top of the last bar
        xytext=(0, 4), textcoords="offset points",  # small upward offset so the label sits above the bar, not overlapping it
        ha="center", fontsize=7,  # centered, small font to stay unobtrusive
    )

    if valid_growth_points:  # only build the second axis/line when at least one real growth number exists
        growth_axis = axis.twinx()  # second y-axis, scaled independently for the % values
        gx = [i for i, _ in valid_growth_points]  # x-positions with a valid growth number (skips index 0 and any div-by-zero gap)
        gy = [g for _, g in valid_growth_points]  # the growth % values themselves
        growth_axis.plot(gx, gy, color=GROWTH_LINE_COLOR, marker="o", linewidth=2, label="Growth %")  # dual-axis line overlay
        growth_axis.set_ylabel("Growth %", fontsize=8)  # names the second axis explicitly, not left ambiguous
        growth_axis.annotate(  # selective label - endpoint only, matches the bar's own last-point-only labeling
            f"{gy[-1]:+.1f}%",  # the final growth point's value, with an explicit +/- sign
            xy=(gx[-1], gy[-1]),  # anchor point: the last plotted growth marker
            xytext=(4, 4), textcoords="offset points",  # small offset so the label doesn't sit directly on the marker
            ha="left", fontsize=7, color=GROWTH_LINE_COLOR,  # matches the line's own color for a clear visual pairing
        )
        bar_handles, bar_labels = axis.get_legend_handles_labels()  # dataviz skill: >=2 encoded series always gets a legend
        line_handles, line_labels = growth_axis.get_legend_handles_labels()  # the growth line's own legend entry
        axis.legend(bar_handles + line_handles, bar_labels + line_labels, fontsize=7, loc="upper left")  # combined legend covering both axes

    figure.tight_layout()  # auto-adjust subplot layout to prevent label cutoff
    buffer = io.BytesIO()  # create in-memory buffer for image data
    figure.savefig(buffer, format="png")  # render figure to PNG in memory
    buffer.seek(0)  # reset buffer position to start for reading
    encoded = base64.b64encode(buffer.read()).decode("ascii")  # read buffer and encode as base64 string
    return f"data:image/png;base64,{encoded}"  # return as data URI ready for <img src="...">


def build_charts(chart_series: list[ChartSeries]) -> list[str]:  # produce one image per plottable input series, in order
    """Produce one image per plottable input series, in order; series with
    no usable category/value pairs are skipped rather than raising. Each
    series gets its color assigned by position - external signature and
    caller contract are unchanged from v1."""
    rendered = [  # assign each series its color by position, matching MAX_CHART_SERIES's own ordering
        _render_single_chart(series, SERIES_COLORS[index % len(SERIES_COLORS)])  # index % 3: a 4th series reuses slot 1, see ADR-0006
        for index, series in enumerate(chart_series)  # enumerate to get each series' position for color assignment
    ]
    return [image for image in rendered if image is not None]  # drop the skipped series from the returned list
