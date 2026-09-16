"""Unit tests for SVG text parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from plotpilot.svg.parse import SvgParseError, SvgParseKind, parse_svg_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_parse_valid_basic_svg() -> None:
    text = (FIXTURES / "valid_basic.svg").read_text(encoding="utf-8")
    root = parse_svg_text(text)
    assert root.tag.endswith("svg")


def test_parse_malformed_xml_raises() -> None:
    text = (FIXTURES / "malformed.xml").read_text(encoding="utf-8")
    with pytest.raises(SvgParseError) as exc_info:
        parse_svg_text(text)
    assert exc_info.value.kind is SvgParseKind.XML


def test_parse_non_svg_root_raises() -> None:
    text = (FIXTURES / "not_svg.xml").read_text(encoding="utf-8")
    with pytest.raises(SvgParseError) as exc_info:
        parse_svg_text(text)
    assert exc_info.value.kind is SvgParseKind.NOT_SVG


def test_parse_empty_text_raises() -> None:
    with pytest.raises(SvgParseError) as exc_info:
        parse_svg_text("   \n")
    assert exc_info.value.kind is SvgParseKind.XML
