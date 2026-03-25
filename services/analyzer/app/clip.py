from __future__ import annotations

import logging
from typing import Optional
from pathlib import Path
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Check if open-clip-torch is importable and available."""
    try:
        import open_clip
        return True
    except ImportError:
        return False


class CLIPScorer:
    """
    Score images using CLIP semantic similarity against fixed editorial prompts.

    The scorer maintains an embedding cache keyed by image path. Embeddings computed
    during scoring() calls are automatically cached and reused by get_embedding() calls.
    This avoids redundant model inference when the same image is scored multiple times
    or when embeddings are needed separately (e.g., for deduplication).

    Cache lifecycle: Lives for the duration of the scorer instance. Clear with clear_embedding_cache()
    if needed to free memory during long runs.
    """

    # Fixed prompt sets for scoring
    POSITIVE_PROMPTS = [
        "cinematic shot with clear subject",
        "sharp focus and good composition",
        "interesting and visually engaging moment",
        "subject clearly visible and well framed",
    ]

    NEGATIVE_PROMPTS = [
        "blurry or out of focus footage",
        "empty scene with no visible subject",
        "overexposed or underexposed shot",
    ]

    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
    ):
        """
        Initialize CLIP scorer with a specified model.

        Args:
            model_name: open_clip model name (default: ViT-B-32)
            pretrained: pretrained weights identifier (default: laion2b_s34b_b79k)
        """
        self.model_name = model_name
        self.pretrained = pretrained
        self.model = None
        self.transform = None
        self.positive_embeddings = None
        self.negative_embeddings = None
        self._embedding_cache: dict[str, np.ndarray] = {}
        self._load_model()

    def _load_model(self):
        """Load the CLIP model and preprocessing transform."""
        try:
            import open_clip
            import torch

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model, _, self.transform = open_clip.create_model_and_transforms(
                self.model_name,
                pretrained=self.pretrained,
                device=self.device,
            )
            self.model.eval()
            logger.info(f"CLIP model loaded: {self.model_name}/{self.pretrained} on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            self.model = None
            self.transform = None
            raise

    def _get_prompt_embeddings(self) -> tuple[np.ndarray, np.ndarray]:
        """Cache and return embeddings for positive and negative prompts."""
        if self.positive_embeddings is not None and self.negative_embeddings is not None:
            return self.positive_embeddings, self.negative_embeddings

        try:
            import open_clip
            import torch

            tokenizer = open_clip.get_tokenizer(self.model_name)

            # Tokenize and embed positive prompts
            positive_tokens = tokenizer(self.POSITIVE_PROMPTS)
            with torch.no_grad():
                positive_embeddings = self.model.encode_text(positive_tokens.to(self.device))
            self.positive_embeddings = positive_embeddings.cpu().numpy()

            # Tokenize and embed negative prompts
            negative_tokens = tokenizer(self.NEGATIVE_PROMPTS)
            with torch.no_grad():
                negative_embeddings = self.model.encode_text(negative_tokens.to(self.device))
            self.negative_embeddings = negative_embeddings.cpu().numpy()

            logger.debug("Prompt embeddings cached")
            return self.positive_embeddings, self.negative_embeddings
        except Exception as e:
            logger.error(f"Failed to cache prompt embeddings: {e}")
            raise

    def score(self, image_path: str) -> float:
        """
        Score an image using CLIP semantic similarity.

        Args:
            image_path: Path to the image file

        Returns:
            Normalized score in [0, 1]
        """
        # Extract embedding (caches it automatically)
        image_embedding = self.get_embedding(image_path)
        if image_embedding is None:
            return 0.5

        try:
            # Get prompt embeddings
            positive_emb, negative_emb = self._get_prompt_embeddings()

            # Normalize embeddings (already normalized in get_embedding)
            positive_emb = positive_emb / np.linalg.norm(positive_emb, axis=1, keepdims=True)
            negative_emb = negative_emb / np.linalg.norm(negative_emb, axis=1, keepdims=True)

            # Compute cosine similarities
            positive_sims = image_embedding @ positive_emb.T  # [1, num_positive]
            negative_sims = image_embedding @ negative_emb.T  # [1, num_negative]

            # Compute weighted score: mean(pos) - 0.5 * mean(neg)
            pos_mean = float(positive_sims.mean())
            neg_mean = float(negative_sims.mean())
            raw_score = pos_mean - 0.5 * neg_mean

            # Normalize to [0, 1]
            # Map roughly [-0.5, 1.5] to [0, 1] with clamping
            normalized_score = np.clip((raw_score + 0.5) / 2.0, 0.0, 1.0)

            return float(normalized_score)
        except Exception as e:
            logger.error(f"Failed to score image {image_path}: {e}")
            return 0.5

    def get_embedding(self, image_path: str) -> Optional[np.ndarray]:
        """
        Extract raw CLIP embedding for an image (reuses cache if available).

        Args:
            image_path: Path to the image file

        Returns:
            Normalized embedding vector or None if extraction fails
        """
        if not Path(image_path).exists():
            logger.warning(f"Image path does not exist: {image_path}")
            return None

        # Return cached embedding if available
        if image_path in self._embedding_cache:
            return self._embedding_cache[image_path]

        if self.model is None or self.transform is None:
            logger.warning(f"CLIP model not available, cannot extract embedding")
            return None

        try:
            import torch

            # Load and preprocess image
            image = Image.open(image_path).convert("RGB")
            image_tensor = self.transform(image).unsqueeze(0).to(self.device)

            # Get image embedding
            with torch.no_grad():
                image_embedding = self.model.encode_image(image_tensor)
            image_embedding = image_embedding.cpu().numpy()

            # Normalize embedding
            image_embedding = image_embedding / np.linalg.norm(image_embedding, axis=1, keepdims=True)

            # Cache and return
            self._embedding_cache[image_path] = image_embedding
            return image_embedding
        except Exception as e:
            logger.error(f"Failed to extract embedding from {image_path}: {e}")
            return None

    def clear_embedding_cache(self, keep_paths: Optional[list[str]] = None) -> None:
        """
        Clear the embedding cache to free memory.

        Args:
            keep_paths: If provided, only clear embeddings NOT in this list
        """
        if keep_paths is None:
            self._embedding_cache.clear()
            logger.debug(f"Cleared embedding cache (all)")
        else:
            paths_to_remove = [p for p in self._embedding_cache.keys() if p not in keep_paths]
            for path in paths_to_remove:
                del self._embedding_cache[path]
            logger.debug(f"Cleared embedding cache ({len(paths_to_remove)} embeddings removed, {len(keep_paths)} kept)")

    def get_cache_stats(self) -> dict[str, int]:
        """Return cache statistics for monitoring."""
        return {"cached_embeddings": len(self._embedding_cache)}
