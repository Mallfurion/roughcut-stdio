from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.analyzer.scripts import scan_media_root


class ScanMediaRootTests(unittest.TestCase):
    def test_main_returns_130_on_keyboard_interrupt(self) -> None:
        provider_status = SimpleNamespace(
            configured_provider="deterministic",
            model="",
            revision="",
            cache_dir="",
            device="",
            detail="Deterministic analyzer active.",
            available=True,
            effective_provider="deterministic",
        )
        analysis_config = SimpleNamespace(
            mode="full",
            max_segments_per_asset=99,
            max_keyframes_per_segment=4,
            keyframe_max_width=960,
            concurrency=2,
            cache_enabled=True,
            transcript_provider="auto",
            transcript_model_size="small",
        )

        with TemporaryDirectory() as temp_dir:
            process_output_path = Path(temp_dir) / "process-output.txt"
            args = Namespace(
                project_name="Fixture Run",
                media_root="/tmp/media",
                story_prompt="Build a coherent rough cut.",
                artifacts_root=temp_dir,
                process_output_file=str(process_output_path),
            )

            with (
                patch("services.analyzer.scripts.scan_media_root.parse_args", return_value=args),
                patch(
                    "services.analyzer.scripts.scan_media_root.inspect_ai_provider_status",
                    return_value=provider_status,
                ),
                patch(
                    "services.analyzer.scripts.scan_media_root.load_ai_analysis_config",
                    return_value=analysis_config,
                ),
                patch(
                    "services.analyzer.scripts.scan_media_root.scan_and_analyze_media_root",
                    side_effect=KeyboardInterrupt,
                ),
            ):
                exit_code = scan_media_root.main()
                persisted = process_output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 130)
        self.assertIn("[Process] ERROR: Interrupted from keyboard.", persisted)


if __name__ == "__main__":
    unittest.main()
