from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from services.analyzer.app.process_reporting import ProcessConsoleProxy, ProcessReporter


class DummyConsole:
    def __init__(self, *, is_tty: bool) -> None:
        self._is_tty = is_tty
        self.buffer = ""

    def write(self, text: str) -> int:
        self.buffer += text
        return len(text)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return self._is_tty


class ProcessReporterTests(unittest.TestCase):
    def test_interactive_console_uses_color_and_non_persistent_progress(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            console = DummyConsole(is_tty=True)
            with TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "process-output.txt"
                reporter = ProcessReporter(artifact_path=output_path, console_stream=console)
                start_time = time.monotonic() - 5.0

                reporter.header("Process Preflight")
                reporter.warn("AI Runtime", "Missing local model files.")
                reporter.progress(
                    processed=1,
                    total=4,
                    asset_name="Clip A001",
                    start_time=start_time,
                    activity="Analyzing",
                )
                reporter.finish()

                persisted = output_path.read_text(encoding="utf-8")
                self.assertIn("=== Process Preflight ===", persisted)
                self.assertIn("[AI Runtime] WARN: Missing local model files.", persisted)
                self.assertNotIn("1/4 assets", persisted)
                self.assertIn("\033[33m", console.buffer)
                self.assertIn("\r[", console.buffer)

    def test_noninteractive_console_keeps_progress_lines_plain(self) -> None:
        console = DummyConsole(is_tty=False)
        reporter = ProcessReporter(console_stream=console)
        start_time = time.monotonic() - 3.0

        reporter.progress(
            processed=2,
            total=5,
            asset_name="Clip B002",
            start_time=start_time,
            activity="Analyzing",
        )

        self.assertIn("[", console.buffer)
        self.assertIn("2/5 assets", console.buffer)
        self.assertNotIn("\033", console.buffer)

    def test_prefill_updates_are_folded_into_live_progress_line(self) -> None:
        console = DummyConsole(is_tty=True)
        with patch.dict("os.environ", {}, clear=True):
            reporter = ProcessReporter(console_stream=console)
            proxy = ProcessConsoleProxy(stream=console, reporter=reporter)
            start_time = time.monotonic() - 2.0

            reporter.progress(
                processed=3,
                total=5,
                asset_name="Clip C003",
                start_time=start_time,
                activity="Analyzing",
            )
            proxy.write("Prefill: 100%|██████████| 2336/2337 [00:00<00:00, 2564.73tok/s]\r")
            proxy.write("Warning: example external warning\n")

        self.assertIn("3/5 assets", console.buffer)
        self.assertIn("prefilling 2336/2337", console.buffer)
        self.assertNotIn("Prefill: 100%", console.buffer)
        self.assertIn("Warning: example external warning\n", console.buffer)
        self.assertTrue(console.buffer.rstrip().endswith("prefilling 2336/2337"))

    def test_known_external_hf_and_use_fast_warnings_are_suppressed(self) -> None:
        console = DummyConsole(is_tty=True)
        with patch.dict("os.environ", {}, clear=True):
            reporter = ProcessReporter(console_stream=console)
            proxy = ProcessConsoleProxy(stream=console, reporter=reporter)
            start_time = time.monotonic() - 2.0

            reporter.progress(
                processed=4,
                total=5,
                asset_name="Clip D004",
                start_time=start_time,
                activity="Analyzing",
            )
            proxy.write(
                "The `use_fast` parameter is deprecated and will be removed in a future version.\n"
            )
            proxy.write(
                "Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.\n"
            )
            proxy.write(
                "WARNING:huggingface_hub.utils._http:Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.\n"
            )

        self.assertIn("4/5 assets", console.buffer)
        self.assertNotIn("use_fast", console.buffer)
        self.assertNotIn("HF Hub", console.buffer)


if __name__ == "__main__":
    unittest.main()
