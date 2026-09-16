"""AxiDraw integration via the official axicli executable."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field

from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus

CliRunner = Callable[[list[str], float], subprocess.CompletedProcess[str]]

DEFAULT_CLI = "axicli"
DEFAULT_TIMEOUT = 30.0

_INSTALL_HINT = (
    "Install AxiDraw software so axicli is on your PATH (https://axidraw.com/doc/cli_api/)."
)


def _default_runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    parts = [result.stdout.strip(), result.stderr.strip()]
    return "\n".join(part for part in parts if part)


@dataclass
class AxiDrawCliBackend:
    """Invoke axicli manual-mode commands; no plotting or XY walks."""

    cli_path: str = DEFAULT_CLI
    timeout_seconds: float = DEFAULT_TIMEOUT
    _runner: CliRunner = field(default=_default_runner, repr=False)

    def _resolve_cli(self) -> str | None:
        if "/" in self.cli_path or self.cli_path.startswith("."):
            return self.cli_path
        return shutil.which(self.cli_path)

    def _manual(self, command: str) -> subprocess.CompletedProcess[str]:
        cli = self._resolve_cli()
        if cli is None:
            msg = f"axicli not found. {_INSTALL_HINT}"
            raise FileNotFoundError(msg)
        argv = [cli, "-m", "manual", "-M", command]
        return self._runner(argv, self.timeout_seconds)

    def detect(self) -> PlotterStatus:
        cli = self._resolve_cli()
        if cli is None:
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message=f"AxiDraw CLI not found. {_INSTALL_HINT}",
            )

        version_text: str | None = None
        try:
            version_proc = self._runner([cli, "--version"], self.timeout_seconds)
            version_text = _combined_output(version_proc).splitlines()[0] if version_proc else None
        except (OSError, subprocess.TimeoutExpired):
            version_text = None

        multiple_note = ""
        try:
            names_proc = self._manual("list_names")
            names_blob = _combined_output(names_proc)
            names = _parse_list_names(names_blob)
            if len(names) > 1:
                multiple_note = f" Multiple named units ({len(names)}); using default device."
        except FileNotFoundError as exc:
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message=str(exc),
                backend_version=version_text,
            )
        except subprocess.TimeoutExpired:
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message="Timed out while listing AxiDraw devices.",
                backend_version=version_text,
            )

        try:
            fw_proc = self._manual("fw_version")
        except subprocess.TimeoutExpired:
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message="Timed out while connecting to AxiDraw.",
                backend_version=version_text,
            )

        blob = _combined_output(fw_proc)
        if fw_proc.returncode != 0 or "Failed to connect" in blob:
            message = "Not connected"
            if blob and "Failed to connect" not in blob:
                message = blob.splitlines()[0]
            return PlotterStatus(
                state=PlotterConnectionState.DISCONNECTED,
                message=message + multiple_note,
                backend_version=version_text,
            )

        fw_line = _extract_firmware(blob)
        message = fw_line or "Connected"
        if multiple_note:
            message = f"{message}.{multiple_note.strip()}"
        return PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message=message,
            backend_version=version_text,
        )

    def pen_up(self) -> PlotterStatus:
        return self._pen_command("raise_pen", "Pen raised")

    def pen_down(self) -> PlotterStatus:
        return self._pen_command("lower_pen", "Pen lowered")

    def _pen_command(self, manual_cmd: str, success_message: str) -> PlotterStatus:
        try:
            proc = self._manual(manual_cmd)
        except FileNotFoundError as exc:
            return PlotterStatus(state=PlotterConnectionState.ERROR, message=str(exc))
        except subprocess.TimeoutExpired:
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message=f"Timed out during {manual_cmd}.",
            )

        blob = _combined_output(proc)
        if proc.returncode != 0 or "Failed to connect" in blob:
            detail = blob.splitlines()[0] if blob else "Command failed"
            return PlotterStatus(
                state=PlotterConnectionState.DISCONNECTED,
                message=detail,
            )
        return PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message=success_message,
        )


def _parse_list_names(text: str) -> list[str]:
    if not text:
        return []
    lowered = text.lower()
    if "no named" in lowered:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines


def _extract_firmware(blob: str) -> str | None:
    for line in blob.splitlines():
        cleaned = line.strip()
        if not cleaned or "Failed to connect" in cleaned:
            continue
        if re.search(r"\d+\.\d+", cleaned):
            return cleaned
    first = next((ln.strip() for ln in blob.splitlines() if ln.strip()), None)
    return first
