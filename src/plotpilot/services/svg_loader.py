"""Load SVG files from disk into application models."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from plotpilot.models.svg_document import SvgDocument
from plotpilot.svg.parse import SvgParseError, SvgParseKind, parse_svg_text


class SvgLoadKind(StrEnum):
    MISSING = "missing"
    UNREADABLE = "unreadable"
    ENCODING = "encoding"
    XML = "xml"
    NOT_SVG = "not_svg"


class SvgLoadError(Exception):
    """Could not load an SVG from the given path."""

    def __init__(self, kind: SvgLoadKind, user_message: str) -> None:
        self.kind = kind
        self.user_message = user_message
        super().__init__(user_message)


def load_svg_from_path(path: Path) -> SvgDocument:
    """Read *path*, validate SVG structure, and return an ``SvgDocument``."""
    resolved = path.expanduser()
    if not resolved.is_file():
        raise SvgLoadError(
            SvgLoadKind.MISSING,
            f"The file could not be found:\n{resolved}",
        )

    try:
        raw_bytes = resolved.read_bytes()
    except OSError as exc:
        raise SvgLoadError(
            SvgLoadKind.UNREADABLE,
            f"Could not read the file:\n{resolved}\n\n{exc}",
        ) from exc

    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SvgLoadError(
            SvgLoadKind.ENCODING,
            "The file is not valid UTF-8 text. Save the SVG as UTF-8 and try again.",
        ) from exc

    try:
        root = parse_svg_text(raw_text)
    except SvgParseError as exc:
        kind = SvgLoadKind.NOT_SVG if exc.kind is SvgParseKind.NOT_SVG else SvgLoadKind.XML
        raise SvgLoadError(kind, exc.user_message) from exc

    absolute = resolved.resolve()
    return SvgDocument(
        path=absolute,
        name=absolute.name,
        raw_text=raw_text,
        root=root,
    )
