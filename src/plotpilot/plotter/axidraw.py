"""AxiDraw integration via the official axicli executable."""

from __future__ import annotations

import re
import shutil
import signal
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from plotpilot.models.plot_job import PlotResult
from plotpilot.models.plot_settings import PlotSettings, build_axicli_plot_argv
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus

CliRunner = Callable[[list[str], float], subprocess.CompletedProcess[str]]

DEFAULT_CLI = "axicli"
DEFAULT_TIMEOUT = 30.0
PRESENCE_TIMEOUT = 8.0
PLOT_CANCEL_WAIT = 8.0

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


def _combined_output(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        return ""
    parts = [result.stdout.strip(), result.stderr.strip()]
    return "\n".join(part for part in parts if part)


@dataclass
class AxiDrawCliBackend:
    """Invoke axicli manual-mode and plot commands."""

    cli_path: str = DEFAULT_CLI
    timeout_seconds: float = DEFAULT_TIMEOUT
    _runner: CliRunner = field(default=_default_runner, repr=False)
    _plot_process: subprocess.Popen[str] | None = field(default=None, init=False, repr=False)
    _cancel_requested: bool = field(default=False, init=False, repr=False)

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

    def detect_presence(self) -> PlotterStatus:
        """List attached units via passive USB scan (no fw_version / serial open)."""
        cli = self._resolve_cli()
        if cli is None:
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message=f"AxiDraw CLI not found. {_INSTALL_HINT}",
            )

        version_text: str | None = None
        try:
            version_proc = self._runner([cli, "--version"], PRESENCE_TIMEOUT)
            version_text = _combined_output(version_proc).splitlines()[0] if version_proc else None
        except (OSError, subprocess.TimeoutExpired):
            version_text = None

        try:
            names_proc = self._runner(
                [cli, "-m", "manual", "-M", "list_names"],
                PRESENCE_TIMEOUT,
            )
        except FileNotFoundError as exc:
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message=str(exc),
                backend_version=version_text,
            )
        except subprocess.TimeoutExpired:
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message="Timed out while scanning for AxiDraw devices.",
                backend_version=version_text,
            )

        names_blob = _combined_output(names_proc)
        if names_proc.returncode != 0:
            detail = names_blob.splitlines()[0] if names_blob else "Device scan failed"
            return PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message=detail,
                backend_version=version_text,
            )

        if _list_names_indicates_presence(names_blob):
            return PlotterStatus(
                state=PlotterConnectionState.CONNECTED,
                message="Connected",
                backend_version=version_text,
            )
        return PlotterStatus(
            state=PlotterConnectionState.DISCONNECTED,
            message="Not connected",
            backend_version=version_text,
        )

    def pen_up(self) -> PlotterStatus:
        return self._pen_command("raise_pen", "Pen raised")

    def pen_down(self) -> PlotterStatus:
        return self._pen_command("lower_pen", "Pen lowered")

    def walk_home(self) -> PlotterStatus:
        # walk_home returns to enable-origin, not guaranteed machine absolute home — see CLI docs.
        return self._pen_command("walk_home", "Walk home complete")

    def disable_xy(self) -> PlotterStatus:
        return self._pen_command("disable_xy", "Motors disabled")

    def plot_svg(
        self,
        svg_path: Path,
        *,
        settings: PlotSettings | None = None,
    ) -> PlotResult:
        cli = self._resolve_cli()
        if cli is None:
            return PlotResult(
                success=False,
                message=f"AxiDraw CLI not found. {_INSTALL_HINT}",
            )

        self._cancel_requested = False
        try:
            argv = build_axicli_plot_argv(cli, svg_path, settings)
        except ValueError as exc:
            return PlotResult(success=False, message=str(exc))
        try:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            return PlotResult(success=False, message=str(exc))

        self._plot_process = proc
        try:
            stdout, stderr = proc.communicate()
        finally:
            self._plot_process = None

        blob = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
        if self._cancel_requested:
            return PlotResult(
                success=False,
                cancelled=True,
                message="Plot stopped",
                detail=blob,
            )

        if proc.returncode != 0:
            summary = _summarize_plot_output(blob) or f"axicli exited with code {proc.returncode}"
            return PlotResult(success=False, message=summary, detail=blob)

        return PlotResult(success=True, message="Plot complete", detail=blob)

    def cancel_plot(self) -> None:
        proc = self._plot_process
        if proc is None or proc.poll() is not None:
            return
        self._cancel_requested = True
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=PLOT_CANCEL_WAIT)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)

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


def _summarize_plot_output(blob: str) -> str | None:
    if not blob:
        return None
    for line in blob.splitlines():
        cleaned = line.strip()
        if cleaned and "Failed to connect" not in cleaned:
            return cleaned
    return blob.splitlines()[0].strip()


def _parse_list_names(text: str) -> list[str]:
    if not text:
        return []
    lowered = text.lower()
    if "no named" in lowered or "no axidraw" in lowered:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [line for line in lines if not line.lower().startswith("list of attached")]


def _list_names_indicates_presence(text: str) -> bool:
    return len(_parse_list_names(text)) > 0


def _extract_firmware(blob: str) -> str | None:
    for line in blob.splitlines():
        cleaned = line.strip()
        if not cleaned or "Failed to connect" in cleaned:
            continue
        if re.search(r"\d+\.\d+", cleaned):
            return cleaned
    first = next((ln.strip() for ln in blob.splitlines() if ln.strip()), None)
    return first
