#!/usr/bin/env python3
"""
Bootstrap CLIP model by downloading and caching it locally.

This script is run during setup to ensure the CLIP model is available
before the first process run. It downloads the default model and caches it
so that process runs don't have to wait for model download.
"""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def bootstrap_clip():
    """Download and cache the CLIP model."""
    try:
        import open_clip
    except ImportError:
        logger.error("open-clip-torch is not installed. Skipping CLIP bootstrap.")
        return False

    try:
        logger.info("Downloading CLIP model: ViT-B-32 / laion2b_s34b_b79k")
        logger.info("This may take a minute on first run...")

        # This will download and cache the model
        model, _, transform = open_clip.create_model_and_transforms(
            "ViT-B-32",
            pretrained="laion2b_s34b_b79k",
        )

        logger.info("✓ CLIP model downloaded and cached successfully")
        logger.info("  Model is ready for semantic scoring during analysis")
        return True
    except Exception as e:
        logger.error(f"Failed to bootstrap CLIP model: {e}")
        logger.error("CLIP will attempt to download on first run, or you can retry setup")
        return False


if __name__ == "__main__":
    success = bootstrap_clip()
    sys.exit(0 if success else 1)
