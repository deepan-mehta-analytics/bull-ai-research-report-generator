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
