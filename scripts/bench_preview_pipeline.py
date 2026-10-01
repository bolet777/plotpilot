"""Time cold layer preparation against cached transform/clip.

    uv run python scripts/bench_preview_pipeline.py

Before/after figures are recorded in specs/025-preview-performance/benchmarks.md.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.svg_document import SvgDocument
from plotpilot.services.layer_geometry import (
    position_and_clip_geometry,
    prepare_layer_geometry,
)
from plotpilot.services.layer_service import layers_for_document
from plotpilot.svg.parse import parse_svg_text

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _cubic_svg(path_count: int) -> str:
    cols = max(1, int(math.sqrt(path_count)))
    rows = math.ceil(path_count / cols)
    cell_w = 200.0 / cols
    cell_h = 280.0 / rows
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" '
        'viewBox="0 0 210 297">',
    ]
    for index in range(path_count):
        col = index % cols
        row = index // cols
        x = 5.0 + col * cell_w
        y = 5.0 + row * cell_h
        parts.append(
            f'<path d="M {x:.3f} {y:.3f} '
            f"C {x + cell_w * 0.15:.3f} {y + cell_h * 0.8:.3f} "
            f"{x + cell_w * 0.7:.3f} {y + cell_h * 0.1:.3f} "
            f'{x + cell_w * 0.85:.3f} {y + cell_h * 0.7:.3f}" '
            'fill="none" stroke="#000"/>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def _document(name: str, text: str) -> SvgDocument:
    return SvgDocument(path=Path(name), name=name, raw_text=text, root=parse_svg_text(text))


def _ms(seconds: float) -> str:
    return f"{seconds * 1000.0:8.1f} ms"


def _measure(label: str, text: str) -> None:
    document = _document(f"{label}.svg", text)
    layer = layers_for_document(document)[0]
    started = time.perf_counter()
    geometry = prepare_layer_geometry(document, layer)
    cold_s = time.perf_counter() - started

    def clip(transform: ArtworkTransform, width: float, height: float) -> float:
        started_clip = time.perf_counter()
        position_and_clip_geometry(
            geometry,
            transform,
            viewport_width_mm=width,
            viewport_height_mm=height,
        )
        return time.perf_counter() - started_clip

    x_s = clip(ArtworkTransform(x_mm=12.0, y_mm=0.0, scale=1.0), 210.0, 297.0)
    y_s = clip(ArtworkTransform(x_mm=12.0, y_mm=-4.0, scale=1.0), 210.0, 297.0)
    scale_s = clip(ArtworkTransform(x_mm=12.0, y_mm=-4.0, scale=1.15), 210.0, 297.0)
    orientation_s = clip(ArtworkTransform(x_mm=12.0, y_mm=-4.0, scale=1.15), 297.0, 210.0)
    points = sum(len(subpath) for subpath in geometry.polylines)
    print(f"\n== {label} ==")
    print(f"  subpaths: {len(geometry.polylines)}  points: {points}")
    print(f"  cold prepare (flatten) {_ms(cold_s)}")
    print(f"  cached X               {_ms(x_s)}")
    print(f"  cached Y               {_ms(y_s)}")
    print(f"  cached scale           {_ms(scale_s)}")
    print(f"  cached orientation     {_ms(orientation_s)}")


def main() -> None:
    app = QApplication.instance() or QApplication([])
    _ = app
    simple = (FIXTURES / "simple.svg").read_text(encoding="utf-8")
    print("preview pipeline benchmark (cached transform/clip)")
    for label, text in (
        ("simple", simple),
        ("normal-80-cubics", _cubic_svg(80)),
        ("paths-1k", _cubic_svg(1000)),
        ("paths-10k", _cubic_svg(10_000)),
    ):
        _measure(label, text)


if __name__ == "__main__":
    main()
