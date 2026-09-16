"""SVG text parsing (stdlib XML only, no Qt)."""

from __future__ import annotations

from enum import StrEnum
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element


class SvgParseKind(StrEnum):
    XML = "xml"
    NOT_SVG = "not_svg"


class SvgParseError(Exception):
    """Failed to parse SVG text."""

    def __init__(self, kind: SvgParseKind, user_message: str) -> None:
        self.kind = kind
        self.user_message = user_message
        super().__init__(user_message)


def _local_tag(tag: str) -> str:
    if tag.startswith("{"):
        _, _, local = tag.partition("}")
        return local
    return tag


def is_svg_root(element: Element) -> bool:
    return _local_tag(element.tag) == "svg"


def parse_svg_text(text: str) -> Element:
    """Parse *text* as XML and return the root if it is an SVG element."""
    stripped = text.strip()
    if not stripped:
        raise SvgParseError(
            SvgParseKind.XML,
            "The file is empty or contains no XML.",
        )

    try:
        root = ET.fromstring(stripped)
    except ET.ParseError as exc:
        raise SvgParseError(
            SvgParseKind.XML,
            f"The file is not valid XML.\n\n{exc}",
        ) from exc

    if not is_svg_root(root):
        raise SvgParseError(
            SvgParseKind.NOT_SVG,
            "The file is XML but the root element is not <svg>.",
        )

    return root
