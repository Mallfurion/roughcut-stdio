from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.analyzer.scripts import bootstrap_clip


class BootstrapClipTests(unittest.TestCase):
    def test_main_skips_when_clip_is_disabled(self) -> None:
        analysis_config = SimpleNamespace(
            clip_enabled=False,
            clip_model="ViT-B-32",
            clip_model_pretrained="laion2b_s34b_b79k",
        )

        with (
            patch("services.analyzer.scripts.bootstrap_clip.load_ai_analysis_config", return_value=analysis_config),
            patch("services.analyzer.scripts.bootstrap_clip.bootstrap_clip") as bootstrap_mock,
        ):
            exit_code = bootstrap_clip.main()

        self.assertEqual(exit_code, 0)
        bootstrap_mock.assert_not_called()

    def test_main_uses_configured_clip_model_pair(self) -> None:
        analysis_config = SimpleNamespace(
            clip_enabled=True,
            clip_model="ViT-L-14",
            clip_model_pretrained="openai",
        )

        with (
            patch("services.analyzer.scripts.bootstrap_clip.load_ai_analysis_config", return_value=analysis_config),
            patch("services.analyzer.scripts.bootstrap_clip.bootstrap_clip", return_value=True) as bootstrap_mock,
        ):
            exit_code = bootstrap_clip.main()

        self.assertEqual(exit_code, 0)
        bootstrap_mock.assert_called_once_with(
            model_name="ViT-L-14",
            pretrained="openai",
        )


if __name__ == "__main__":
    unittest.main()
