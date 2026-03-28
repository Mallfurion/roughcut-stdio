from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
import time
from typing import TextIO


RESET = "\033[0m"
STYLES = {
    "header": "\033[1;36m",
    "info": "",
    "success": "\033[32m",
    "warn": "\033[33m",
    "error": "\033[31m",
}
SPINNER_FRAMES = ("|", "/", "-", "\\")
PREFILL_RE = re.compile(r"^Prefill:\s+\d+%\|.*?\|\s*(?P<current>\d+)(?:/(?P<total>\d+))?")
SUPPRESSED_EXTERNAL_LINE_PATTERNS = (
    "The `use_fast` parameter is deprecated",
    "You are sending unauthenticated requests to the HF Hub",
    "huggingface_hub.utils._http:Warning:",
)


@dataclass(slots=True)
class ProcessReportEvent:
    kind: str
    section: str
    message: str
    severity: str = "info"
    persist: bool = True


class ProcessReporter:
    def __init__(
        self,
        *,
        artifact_path: str | Path | None = None,
        console_stream: TextIO | None = None,
        interactive: bool | None = None,
    ) -> None:
        self.console_stream = console_stream or sys.stderr
        self.artifact_path = Path(artifact_path) if artifact_path else None
        stream_is_tty = bool(getattr(self.console_stream, "isatty", lambda: False)())
        self.interactive = stream_is_tty if interactive is None else interactive
        self.color_enabled = self.interactive and os.environ.get("NO_COLOR", "").strip() == ""
        self.progress_active = False
        self.last_progress_message = ""
        self.last_progress_state: dict[str, object] = {}
        self.progress_status = ""
        self._spinner_index = 0

    def header(self, title: str, *, persist: bool = True) -> None:
        self.emit(ProcessReportEvent(kind="header", section="", message=title, severity="header", persist=persist))

    def info(self, section: str, message: str, *, persist: bool = True) -> None:
        self.emit(ProcessReportEvent(kind="message", section=section, message=message, severity="info", persist=persist))

    def success(self, section: str, message: str, *, persist: bool = True) -> None:
        self.emit(ProcessReportEvent(kind="message", section=section, message=message, severity="success", persist=persist))

    def warn(self, section: str, message: str, *, persist: bool = True) -> None:
        self.emit(ProcessReportEvent(kind="message", section=section, message=message, severity="warn", persist=persist))

    def error(self, section: str, message: str, *, persist: bool = True) -> None:
        self.emit(ProcessReportEvent(kind="message", section=section, message=message, severity="error", persist=persist))

    def emit(self, event: ProcessReportEvent) -> None:
        self._finish_progress_line()
        console_line = self._format_console_event(event)
        if console_line:
            self.console_stream.write(console_line + "\n")
            self.console_stream.flush()
        if event.persist and self.artifact_path is not None:
            self._append_file_line(self._format_file_event(event))

    def progress(
        self,
        *,
        processed: int,
        total: int,
        asset_name: str,
        start_time: float,
        activity: str = "Analyzing",
        persist: bool = False,
    ) -> None:
        message = self._format_progress_message(
            processed=processed,
            total=total,
            asset_name=asset_name,
            start_time=start_time,
            activity=activity,
        )
        self.last_progress_state = {
            "processed": processed,
            "total": total,
            "asset_name": asset_name,
            "start_time": start_time,
            "activity": activity,
        }
        if self.interactive:
            self._render_progress_line(message)
        else:
            self._finish_progress_line()
            self.console_stream.write(message + "\n")
            self.console_stream.flush()
        if persist and self.artifact_path is not None:
            self._append_file_line(message)

    def finish(self) -> None:
        self._finish_progress_line()

    def break_progress_line(self) -> None:
        if not self.progress_active:
            return
        self.console_stream.write("\n")
        self.console_stream.flush()

    def set_progress_status(self, status: str | None) -> None:
        self.progress_status = (status or "").strip()
        self.refresh_progress()

    def clear_progress_status(self) -> None:
        self.set_progress_status("")

    def advance_spinner(self) -> str:
        frame = SPINNER_FRAMES[self._spinner_index % len(SPINNER_FRAMES)]
        self._spinner_index += 1
        return frame

    def refresh_progress(self) -> None:
        if self.interactive and self.progress_active and self.last_progress_state:
            self._render_progress_line(
                self._format_progress_message(
                    processed=int(self.last_progress_state["processed"]),
                    total=int(self.last_progress_state["total"]),
                    asset_name=str(self.last_progress_state["asset_name"]),
                    start_time=float(self.last_progress_state["start_time"]),
                    activity=str(self.last_progress_state["activity"]),
                )
            )

    def _format_progress_message(
        self,
        *,
        processed: int,
        total: int,
        asset_name: str,
        start_time: float,
        activity: str,
    ) -> str:
        total = max(total, 1)
        ratio = min(1.0, max(0.0, processed / total))
        width = 28
        filled = int(round(width * ratio))
        bar = "=" * filled + "." * (width - filled)
        elapsed = max(0.0, time.monotonic() - start_time)
        eta = (elapsed / processed) * (total - processed) if processed > 0 else 0.0
        label = f"{activity.lower()} {asset_name}".strip()
        label = label[:44]
        message = (
            f"[{bar}] {processed}/{total} assets"
            f" | elapsed {format_clock(elapsed)}"
            f" | eta {format_clock(eta)}"
            f" | {label}"
        )
        if self.progress_status:
            message += f" | {self.progress_status}"
        return message

    def _format_console_event(self, event: ProcessReportEvent) -> str:
        if event.kind == "header":
            text = f"=== {event.message} ==="
        else:
            prefix = f"[{event.section}] " if event.section else ""
            if event.severity == "warn":
                prefix += "WARN: "
            elif event.severity == "error":
                prefix += "ERROR: "
            elif event.severity == "success":
                prefix += "OK: "
            text = prefix + event.message
        if not self.color_enabled:
            return text
        style = STYLES.get(event.severity, "")
        if not style:
            return text
        return f"{style}{text}{RESET}"

    def _format_file_event(self, event: ProcessReportEvent) -> str:
        if event.kind == "header":
            return f"=== {event.message} ==="
        prefix = f"[{event.section}] " if event.section else ""
        if event.severity == "warn":
            prefix += "WARN: "
        elif event.severity == "error":
            prefix += "ERROR: "
        elif event.severity == "success":
            prefix += "OK: "
        return prefix + event.message

    def _append_file_line(self, line: str) -> None:
        if self.artifact_path is None:
            return
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        with self.artifact_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _render_progress_line(self, message: str) -> None:
        self.progress_active = True
        self.last_progress_message = message
        self.console_stream.write("\r" + message.ljust(160))
        self.console_stream.flush()

    def _finish_progress_line(self) -> None:
        if not self.progress_active:
            return
        self.console_stream.write("\n")
        self.console_stream.flush()
        self.progress_active = False
        self.last_progress_message = ""
        self.last_progress_state = {}
        self.progress_status = ""


class ProcessConsoleProxy:
    def __init__(self, *, stream: TextIO, reporter: ProcessReporter) -> None:
        self.stream = stream
        self.reporter = reporter
        self._buffer = ""

    def write(self, text: str) -> int:
        for char in text:
            if char in "\r\n":
                self._flush_buffer()
            else:
                self._buffer += char
        return len(text)

    def flush(self) -> None:
        self.stream.flush()

    def isatty(self) -> bool:
        return bool(getattr(self.stream, "isatty", lambda: False)())

    def _flush_buffer(self) -> None:
        line = self._buffer.strip()
        self._buffer = ""
        if not line:
            return

        match = PREFILL_RE.match(line)
        if match:
            current = match.group("current")
            total = match.group("total")
            spinner = self.reporter.advance_spinner()
            detail = f"{spinner} prefilling {current}/{total}" if total else f"{spinner} prefilling"
            self.reporter.set_progress_status(detail)
            return

        if any(pattern in line for pattern in SUPPRESSED_EXTERNAL_LINE_PATTERNS):
            self.reporter.refresh_progress()
            return

        self.reporter.break_progress_line()
        self.stream.write(line + "\n")
        self.stream.flush()
        self.reporter.refresh_progress()


def format_clock(value: float) -> str:
    total_seconds = int(round(max(0.0, value)))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
