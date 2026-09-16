"""In-memory representation of a loaded SVG file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import Element


@dataclass(frozen=True, slots=True)
class SvgDocument:
    """Single loaded SVG document (path, display name, content, parsed root)."""

    path: Path
    name: str
    raw_text: str
    root: Element
