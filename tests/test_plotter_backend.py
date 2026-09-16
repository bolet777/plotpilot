"""AxiDraw CLI backend (mocked subprocess)."""

from __future__ import annotations

import subprocess

from plotpilot.models.plotter_status import PlotterConnectionState
from plotpilot.plotter.axidraw import AxiDrawCliBackend


def _completed(
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["axicli"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_detect_disconnected_when_fw_fails() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], _timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[-1] == "--version":
            return _completed(0, stdout="AxiDraw CLI 3.9.6\n")
        if argv[-1] == "list_names":
            return _completed(0, stdout="No named AxiDraw units located.\n")
        if argv[-1] == "fw_version":
            return _completed(1, stderr="Failed to connect to AxiDraw.\n")
        raise AssertionError(argv)

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    status = backend.detect()
    assert status.state is PlotterConnectionState.DISCONNECTED
    assert "Not connected" in status.message


def test_detect_connected_reads_firmware() -> None:
    def runner(argv: list[str], _timeout: float) -> subprocess.CompletedProcess[str]:
        if argv[-1] == "--version":
            return _completed(0, stdout="AxiDraw CLI 3.9.6\n")
        if argv[-1] == "list_names":
            return _completed(0, stdout="No named AxiDraw units located.\n")
        if argv[-1] == "fw_version":
            return _completed(0, stdout="Firmware 2.7.0\n")
        if argv[-1] == "raise_pen":
            return _completed(0, stdout="OK\n")
        raise AssertionError(argv)

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    status = backend.detect()
    assert status.state is PlotterConnectionState.CONNECTED
    assert backend.pen_up().state is PlotterConnectionState.CONNECTED


def test_missing_cli_is_error() -> None:
    backend = AxiDrawCliBackend(cli_path="/nonexistent/axicli")
    status = backend.detect()
    assert status.state is PlotterConnectionState.ERROR


def test_pen_down_failure_does_not_raise() -> None:
    def runner(argv: list[str], _timeout: float) -> subprocess.CompletedProcess[str]:
        if "list_names" in argv or "fw_version" in argv or "--version" in argv:
            return _completed(0, stdout="ok\n")
        return _completed(1, stderr="Failed to connect to AxiDraw.\n")

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    status = backend.pen_down()
    assert status.state is PlotterConnectionState.DISCONNECTED
