"""Test suite for chart builder module - validates matplotlib rendering to base64 data URIs."""
from app.extraction.schema import ChartSeries  # import ChartSeries model for test data
from app.charts.chart_builder import build_charts  # import the chart builder function under test


def test_build_charts_returns_one_image_per_series():  # test that one image is produced per input series
    """Verify that build_charts returns exactly one base64 PNG data URI per input ChartSeries."""
    series = [  # create test data with two chart series
        ChartSeries(label="Revenue", categories=["Q1", "Q2"], values=[100.0, 120.0]),  # first series with 2 data points
        ChartSeries(label="EBITDA", categories=["Q1", "Q2"], values=[10.0, 15.0]),  # second series with 2 data points
    ]
    images = build_charts(series)  # call build_charts with test data
    assert len(images) == 2  # verify exactly 2 images returned
    for image in images:  # iterate through each returned image
        assert image.startswith("data:image/png;base64,")  # verify each image is a valid PNG data URI


def test_build_charts_empty_input_returns_empty_list():  # test that empty input produces empty output
    """Verify that build_charts returns an empty list when given empty input."""
    assert build_charts([]) == []  # call with empty list and verify empty list returned


def test_build_charts_truncates_ragged_series_instead_of_raising():  # test the length-mismatch guard
    """A series with more categories than values must render against the
    common prefix rather than raising a raw matplotlib exception."""
    series = [ChartSeries(label="Revenue", categories=["Q1", "Q2", "Q3"], values=[100.0, 120.0])]  # 3 labels but only 2 values
    images = build_charts(series)  # call build_charts with the ragged series
    assert len(images) == 1  # the series still renders, truncated to the common length
    assert images[0].startswith("data:image/png;base64,")  # and is a valid PNG data URI


def test_build_charts_skips_series_with_no_usable_data():  # test the empty-series guard
    """A series with an empty categories or values list is skipped entirely."""
    series = [  # two unplottable series plus one good one
        ChartSeries(label="No values", categories=["Q1", "Q2"], values=[]),  # labels but no numbers
        ChartSeries(label="No categories", categories=[], values=[1.0, 2.0]),  # numbers but no labels
        ChartSeries(label="Revenue", categories=["Q1"], values=[100.0]),  # a plottable series
    ]
    images = build_charts(series)  # call build_charts with the mixed list
    assert len(images) == 1  # only the plottable series produces an image
