from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from services.analyzer.app.process_reporting import ProcessReporter


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


if __name__ == "__main__":
    unittest.main()
