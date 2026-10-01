"""PlotSettings model and axicli argv builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from plotpilot.models.plot_settings import (
    REORDERING_BASIC,
    REORDERING_STRICT,
    PlotSettings,
    PlotSettingsValidationError,
    build_axicli_plot_argv,
)


def test_default_plot_settings_have_no_overrides() -> None:
    settings = PlotSettings()
    assert not settings.has_overrides
    assert settings.path_reordering == REORDERING_STRICT
    assert not settings.const_speed
    assert not settings.optimize_path_order


def test_default_argv_is_explicit() -> None:
    argv = build_axicli_plot_argv("axicli", Path("layer.svg"))
    assert argv == ["axicli", "layer.svg", "-m", "plot", "-c", "1", "-G", "4", "-N"]
    assert all(flag not in argv for flag in ("-s", "-S", "-a", "-u", "-d", "-L", "-C"))


def test_pen_down_speed_flag() -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("x.svg"),
        PlotSettings(pen_down_speed=40),
    )
    assert "-s" in argv and argv[argv.index("-s") + 1] == "40"


def test_pen_up_speed_flag() -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("x.svg"),
        PlotSettings(pen_up_speed=55),
    )
    assert "-S" in argv and argv[argv.index("-S") + 1] == "55"


def test_acceleration_flag() -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("x.svg"),
        PlotSettings(acceleration=60),
    )
    assert "-a" in argv and argv[argv.index("-a") + 1] == "60"


def test_model_flag() -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("x.svg"),
        PlotSettings(model=2),
    )
    assert "-L" in argv and argv[argv.index("-L") + 1] == "2"


def test_path_reordering_flag_when_enabled() -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("x.svg"),
        PlotSettings(path_reordering=REORDERING_BASIC),
    )
    assert "-G" in argv and argv[argv.index("-G") + 1] == "1"


def test_driver_default_ordering_omits_reordering_flag() -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("x.svg"),
        PlotSettings(path_reordering=None),
    )
    assert "-G" not in argv
    assert "-N" in argv


def test_argv_flag_order_is_deterministic() -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("x.svg"),
        PlotSettings(
            pen_down_speed=10,
            pen_up_speed=90,
            acceleration=50,
            model=3,
            path_reordering=REORDERING_BASIC,
        ),
    )
    assert argv == [
        "axicli",
        "x.svg",
        "-m",
        "plot",
        "-c",
        "1",
        "-s",
        "10",
        "-S",
        "90",
        "-a",
        "50",
        "-L",
        "3",
        "-G",
        "1",
        "-N",
    ]


def test_multiple_overrides_combine() -> None:
    argv = build_axicli_plot_argv(
        "axicli",
        Path("x.svg"),
        PlotSettings(pen_down_speed=10, pen_up_speed=90, acceleration=50, model=3),
    )
    assert argv.count("-s") == 1
    assert "-S" in argv and "-a" in argv and "-L" in argv


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (PlotSettings(pen_down_speed=0), "Pen-down"),
        (PlotSettings(pen_up_speed=101), "Pen-up"),
        (PlotSettings(acceleration=0), "Acceleration"),
        (PlotSettings(model=8), "Model"),
        (PlotSettings(path_reordering=0), "Path ordering"),
        (PlotSettings(path_reordering=3), "Path ordering"),
        (PlotSettings(pen_pos_up=101), "Pen-up position"),
        (PlotSettings(pen_pos_down=-1), "Pen-down position"),
    ],
)
def test_invalid_settings_rejected(settings: PlotSettings, message: str) -> None:
    with pytest.raises(PlotSettingsValidationError, match=message):
        settings.validate()
    with pytest.raises(PlotSettingsValidationError):
        build_axicli_plot_argv("axicli", Path("x.svg"), settings)
