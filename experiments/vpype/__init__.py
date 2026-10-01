"""Isolated vpype geometry spike for Task #6 evaluation (not wired to production)."""

from experiments.vpype.adapter import (
    ClipBackend,
    VpypePrepareError,
    observe_vpype_golden,
    prepare_vpype_polylines_mm,
)

__all__ = [
    "ClipBackend",
    "VpypePrepareError",
    "observe_vpype_golden",
    "prepare_vpype_polylines_mm",
]
