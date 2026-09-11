"""Render one bar chart per ChartSeries with matplotlib, returned as
base64 PNG data URIs ready to drop into an <img src="..."> tag. Bar-only
in v1 - the sample's dual-axis growth-percentage line overlay is a
documented trade-off, not an oversight (see ADR-0002).

Uses the object-oriented Figure/FigureCanvasAgg API rather than the
global pyplot state machine: the FastAPI route is a plain `def` handler,
so it runs in a threadpool where concurrent requests would otherwise
share (and corrupt) pyplot's process-wide figure registry."""
import base64  # encoding library for base64 conversion
import io  # in-memory file buffer for image data
from matplotlib.figure import Figure  # object-oriented figure class, no global pyplot state
from matplotlib.backends.backend_agg import FigureCanvasAgg  # Agg renderer attached explicitly to each figure
from ..extraction.schema import ChartSeries  # import data model for chart series

BAR_COLOR = "#0f7a6c"  # hex color for all bar chart columns

MAX_CHART_SERIES = 4  # upper bound on charts per report; extraction has returned 17 series for one document, which overflows the layout by pages

import re  # standard library, for the period-format classification below

_QUARTER_RE = re.compile(r"\bQ\d", re.IGNORECASE)  # matches "Q1", "Q2-2025", "Q2 FY26", "Q2FY26" - no trailing \b since "1" and "F" in "Q2FY26" share no word boundary
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


def _render_single_chart(series: ChartSeries) -> str | None:  # render one series as a bar chart, or None if it isn't plottable
    """Draw one series as a bar chart and return it as a base64 data URI,
    or None when the series has no usable data. Categories and values are
    truncated to their common length so a ragged extraction result can
    never raise a raw matplotlib exception through the caller."""
    usable_length = min(len(series.categories), len(series.values))  # longest prefix where both lists have a paired entry
    if usable_length == 0:  # nothing to plot if either list is empty (or they share no common prefix)
        return None  # signal "skip this series" to build_charts
    categories = series.categories[:usable_length]  # truncate labels to the common length
    values = series.values[:usable_length]  # truncate values to the same common length
    figure = Figure(figsize=(6, 3.2), dpi=150)  # construct a standalone figure with no pyplot involvement
    FigureCanvasAgg(figure)  # attach an Agg canvas so the figure can render itself to PNG
    axis = figure.subplots()  # create the single axes this chart draws on
    x_positions = range(usable_length)  # create x-axis position indices
    axis.bar(x_positions, values, color=BAR_COLOR)  # draw bars with fixed color
    axis.set_xticks(list(x_positions))  # set tick positions on x-axis
    axis.set_xticklabels(categories, fontsize=8)  # label x-axis ticks with category names
    axis.set_title(series.label, fontsize=10, fontweight="bold")  # set chart title from series label
    figure.tight_layout()  # auto-adjust subplot layout to prevent label cutoff
    buffer = io.BytesIO()  # create in-memory buffer for image data
    figure.savefig(buffer, format="png")  # render figure to PNG in memory
    buffer.seek(0)  # reset buffer position to start for reading
    encoded = base64.b64encode(buffer.read()).decode("ascii")  # read buffer and encode as base64 string
    return f"data:image/png;base64,{encoded}"  # return as data URI ready for <img src="...">


def build_charts(chart_series: list[ChartSeries]) -> list[str]:  # produce one image per plottable input series, in order
    """Produce one image per plottable input series, in order; series with
    no usable category/value pairs are skipped rather than raising."""
    rendered = [_render_single_chart(series) for series in chart_series]  # render each series, possibly yielding None for unplottable ones
    return [image for image in rendered if image is not None]  # drop the skipped series from the returned list
