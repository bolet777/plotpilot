# Implementation Plan: AxiDraw Connection and Pen Controls

**Branch**: `004-axidraw-connect` | **Spec**: [spec.md](./spec.md)

## Summary

`PlotterBackend` protocol with `AxiDrawCliBackend` (subprocess `axicli` manual commands) and
`FakePlotterBackend` for tests. `PlotterService` (QObject) runs detect/pen on `QThreadPool`, emits
`status_changed`. Main window gains a bottom **Plotter** strip wired to the service.

## Technical Context

- **Hardware**: external `axicli` on PATH only
- **Async**: `QRunnable` + signals (no asyncio)
- **Tests**: fake backend + optional mock runner for CLI backend unit tests

## Constitution Check

UI → `PlotterService` → `PlotterBackend`; no subprocess in UI. SVG paths unchanged.
