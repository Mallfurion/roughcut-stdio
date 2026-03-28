#!/usr/bin/env python3
from __future__ import annotations

import logging
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.ai_runtime.config import load_ai_analysis_config  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def bootstrap_clip(*, model_name: str, pretrained: str) -> bool:
    """Download and cache the configured CLIP model."""
    try:
        import open_clip
    except ImportError:
        logger.error("open-clip-torch is not installed. Skipping CLIP bootstrap.")
        return False

    try:
        logger.info("Downloading CLIP model: %s / %s", model_name, pretrained)
        logger.info("This may take a minute on first run...")

        # This will download and cache the model
        open_clip.create_model_and_transforms(
            model_name,
            pretrained=pretrained,
        )

        logger.info("✓ CLIP model downloaded and cached successfully")
        logger.info("  Model is ready for semantic scoring during analysis")
        return True
    except Exception as exc:
        logger.error("Failed to bootstrap CLIP model: %s", exc)
        logger.error("CLIP will attempt to download on first run, or you can retry setup")
        return False


def main() -> int:
    analysis_config = load_ai_analysis_config()
    if not analysis_config.clip_enabled:
        logger.info("CLIP bootstrap skipped because TIMELINE_AI_CLIP_ENABLED is disabled.")
        return 0

    success = bootstrap_clip(
        model_name=analysis_config.clip_model,
        pretrained=analysis_config.clip_model_pretrained,
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
