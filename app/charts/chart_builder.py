"""Render one bar chart per ChartSeries with matplotlib, returned as
base64 PNG data URIs ready to drop into an <img src="..."> tag. Bar-only
in v1 - the sample's dual-axis growth-percentage line overlay is a
documented trade-off, not an oversight (see ADR-0002)."""
import base64  # encoding library for base64 conversion
import io  # in-memory file buffer for image data
import matplotlib  # matplotlib base module for backend selection

matplotlib.use("Agg")  # set non-interactive backend before pyplot import
import matplotlib.pyplot as plt  # plotting functions for bar charts
from ..extraction.schema import ChartSeries  # import data model for chart series

BAR_COLOR = "#0f7a6c"  # hex color for all bar chart columns


def _render_single_chart(series: ChartSeries) -> str:  # render one series as a bar chart and return base64 data URI
    """Draw one series as a bar chart and return it as a base64 data URI."""
    figure, axis = plt.subplots(figsize=(6, 3.2), dpi=150)  # create figure and axis with specific dimensions
    x_positions = range(len(series.categories))  # create x-axis position indices
    axis.bar(x_positions, series.values, color=BAR_COLOR)  # draw bars with fixed color
    axis.set_xticks(list(x_positions))  # set tick positions on x-axis
    axis.set_xticklabels(series.categories, fontsize=8)  # label x-axis ticks with category names
    axis.set_title(series.label, fontsize=10, fontweight="bold")  # set chart title from series label
    figure.tight_layout()  # auto-adjust subplot layout to prevent label cutoff
    buffer = io.BytesIO()  # create in-memory buffer for image data
    figure.savefig(buffer, format="png")  # render figure to PNG in memory
    plt.close(figure)  # close figure to release memory
    buffer.seek(0)  # reset buffer position to start for reading
    encoded = base64.b64encode(buffer.read()).decode("ascii")  # read buffer and encode as base64 string
    return f"data:image/png;base64,{encoded}"  # return as data URI ready for <img src="...">


def build_charts(chart_series: list[ChartSeries]) -> list[str]:  # produce exactly one image per input series, in order
    """Produce exactly one image per input series, in order."""
    return [_render_single_chart(series) for series in chart_series]  # list comprehension: render each series
