from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from base64 import b64encode
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha1
import importlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Protocol
from urllib import error, request

from .domain import Asset, BoundaryValidationResult, CandidateSegment, SegmentEvidence, SegmentUnderstanding


SCHEMA_VERSION = "segment-understanding-v1"
MLX_MODEL_MANIFEST = "mlx-vlm-manifest.json"
PLACEHOLDER_TEXT_VALUES = {
    "short label",
    "short sentence",
    "item1",
    "item2",
    "item 1",
    "item 2",
    "label",
    "sentence",
    "n/a",
    "none",
    "null",
    "placeholder",
}


class ProviderClient(Protocol):
    def create_json_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str],
        timeout_sec: float,
    ) -> dict[str, object]:
        ...


class VisionLanguageAnalyzer(Protocol):
    requires_keyframes: bool

    def analyze(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
    ) -> SegmentUnderstanding:
        ...

    def analyze_asset_segments(
        self,
        *,
        asset: Asset,
        tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
    ) -> dict[str, SegmentUnderstanding]:
        ...


class LocalVisionRuntime(Protocol):
    model_id: str
    revision: str
    device: str
    cache_dir: str

    def query_image(
        self,
        *,
        image_path: str,
        prompt: str,
    ) -> str:
        ...


class RankingPlanner(Protocol):
    def plan(self, payload: dict[str, object]) -> dict[str, object]:
        ...


@dataclass(slots=True)
class AIProviderConfig:
    provider: str
    model: str
    base_url: str
    timeout_sec: float
    revision: str = ""
    cache_dir: str = ""
    device: str = "auto"


@dataclass(slots=True)
class AIAnalysisConfig:
    mode: str
    max_segments_per_asset: int
    max_keyframes_per_segment: int
    keyframe_max_width: int
    concurrency: int
    cache_enabled: bool
    clip_enabled: bool = True
    clip_min_score: float = 0.35
    vlm_budget_pct: int = 100
    clip_model: str = "ViT-B-32"
    clip_model_pretrained: str = "laion2b_s34b_b79k"
    boundary_refinement_enabled: bool = True
    boundary_refinement_legacy_fallback: bool = True
    semantic_boundary_validation_enabled: bool = True
    semantic_boundary_ambiguity_threshold: float = 0.7
    semantic_boundary_validation_budget_pct: int = 100
    semantic_boundary_validation_max_segments: int = 2
    semantic_boundary_max_adjustment_sec: float = 1.5


@dataclass(slots=True)
class AIProviderStatus:
    configured_provider: str
    effective_provider: str
    model: str
    base_url: str
    revision: str
    cache_dir: str
    device: str
    available: bool
    detail: str


@dataclass(slots=True)
class AIRuntimeStats:
    live_segment_count: int = 0
    cached_segment_count: int = 0
    fallback_segment_count: int = 0
    live_request_count: int = 0


class AIProviderRequestError(RuntimeError):
    pass


class OpenAICompatibleProviderClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def create_json_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str],
        timeout_sec: float,
    ) -> dict[str, object]:
        content: list[dict[str, object]] = [{"type": "text", "text": user_prompt}]
        for image_path in image_paths:
            data_url = encode_image_as_data_url(image_path)
            if data_url is None:
                continue
            content.append({"type": "image_url", "image_url": {"url": data_url}})

        base_payload = {
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
        }

        completion: dict[str, object] | None = None
        last_error: str | None = None
        payload_variants = [
            {**base_payload, "response_format": {"type": "json_object"}},
            base_payload,
        ]
        for payload in payload_variants:
            try:
                raw = self._post_chat_completion(payload=payload, timeout_sec=timeout_sec)
                completion = json.loads(raw)
                break
            except AIProviderRequestError as exc:
                last_error = str(exc)
                continue

        if completion is None:
            raise AIProviderRequestError(last_error or "Chat completion request failed.")

        choices = completion.get("choices", [])
        if not choices:
            raise AIProviderRequestError("Provider returned no completion choices.")

        message = choices[0].get("message", {})
        content_value = message.get("content", "")
        if isinstance(content_value, list):
            text_parts = [part.get("text", "") for part in content_value if isinstance(part, dict)]
            content_text = "\n".join(part for part in text_parts if part)
        else:
            content_text = str(content_value)

        parsed = parse_json_object(content_text)
        if parsed is None:
            raise AIProviderRequestError("Provider response did not contain valid JSON.")
        return parsed

    def _post_chat_completion(self, *, payload: dict[str, object], timeout_sec: float) -> str:
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_sec) as response:
                return response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AIProviderRequestError(
                f"HTTP {exc.code} from provider: {body or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise AIProviderRequestError(f"Provider request failed: {exc}") from exc


class MLXVLMRuntime:
    def __init__(
        self,
        *,
        model_id: str,
        revision: str,
        cache_dir: str,
        device: str,
        local_files_only: bool = False,
    ) -> None:
        self.model_id = model_id
        self.revision = revision
        self.cache_dir = cache_dir
        self.device = device
        self.local_files_only = local_files_only
        self._model: Any | None = None
        self._processor: Any | None = None
        self._config: Any | None = None

    def ensure_loaded(self) -> None:
        if self._model is not None:
            return

        load = importlib.import_module("mlx_vlm").load
        load_config = importlib.import_module("mlx_vlm.utils").load_config

        self.device = resolve_mlx_device(requested=self.device)
        model_reference = resolve_prepared_mlx_vlm_model_path(
            model_id=self.model_id,
            revision=self.revision,
            cache_dir=self.cache_dir,
        )
        if model_reference is None:
            raise AIProviderRequestError(
                "Prepared MLX-VLM model files were not found in the local cache. "
                "Run `npm run setup` to download the configured model before processing."
            )
        with model_cache_environment(self.cache_dir):
            model, processor = load(model_reference)
            try:
                config = load_config(model_reference)
            except Exception:
                config = getattr(model, "config", None)

        self._model = model
        self._processor = processor
        self._config = config

    def _model_type(self) -> str:
        config = self._config
        if isinstance(config, dict):
            return str(config.get("model_type", "")).strip().lower()
        return str(getattr(config, "model_type", "")).strip().lower()

    def _to_mx_array(self, value: Any) -> Any:
        mx = importlib.import_module("mlx.core")
        if value is None:
            return None
        if isinstance(value, mx.array):
            return value
        if hasattr(value, "detach") and hasattr(value, "cpu"):
            value = value.detach().cpu().numpy()
        return mx.array(value)

    def _query_qwen_with_prepared_inputs(
        self,
        *,
        image_path: str,
        prompt: str,
    ) -> str:
        generate = importlib.import_module("mlx_vlm").generate
        model = self._model
        processor = self._processor
        if model is None:
            raise AIProviderRequestError("MLX-VLM model did not initialize.")
        if processor is None:
            raise AIProviderRequestError("MLX-VLM processor did not initialize.")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )

        kwargs: dict[str, Any] = {
            "input_ids": self._to_mx_array(inputs["input_ids"]),
            "mask": self._to_mx_array(inputs.get("attention_mask")),
            "max_tokens": 120,
            "temperature": 0.0,
            "verbose": False,
        }

        pixel_values = inputs.get("pixel_values_videos", inputs.get("pixel_values"))
        if pixel_values is None:
            raise AIProviderRequestError("MLX-VLM processor did not return pixel values for the image input.")
        kwargs["pixel_values"] = self._to_mx_array(pixel_values)

        for key in (
            "image_grid_thw",
            "video_grid_thw",
            "pixel_attention_mask",
            "aspect_ratio_ids",
            "aspect_ratio_mask",
            "cross_attention_mask",
        ):
            if key in inputs and inputs[key] is not None:
                kwargs[key] = self._to_mx_array(inputs[key])

        result = generate(
            model,
            processor,
            "",
            **kwargs,
        )
        return extract_generation_text(result)

    def query_image(
        self,
        *,
        image_path: str,
        prompt: str,
    ) -> str:
        if not image_path:
            raise AIProviderRequestError("MLX-VLM local backend received no image path.")
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            raise AIProviderRequestError(f"MLX-VLM local backend image path is invalid: {image_path}")

        self.ensure_loaded()
        model_type = self._model_type()
        if model_type.startswith("qwen3"):
            return self._query_qwen_with_prepared_inputs(
                image_path=image_path,
                prompt=prompt,
            )

        pil_image = importlib.import_module("PIL.Image")
        image = pil_image.open(path).convert("RGB")
        apply_chat_template = importlib.import_module("mlx_vlm.prompt_utils").apply_chat_template
        generate = importlib.import_module("mlx_vlm").generate
        model = self._model
        processor = self._processor
        config = self._config
        if model is None:
            raise AIProviderRequestError("MLX-VLM model did not initialize.")
        if processor is None:
            raise AIProviderRequestError("MLX-VLM processor did not initialize.")

        formatted_prompt = apply_chat_template(
            processor,
            config,
            prompt,
            num_images=1,
        )

        result = generate(
            model,
            processor,
            formatted_prompt,
            [image],
            verbose=False,
            max_tokens=120,
            temperature=0.0,
        )
        return extract_generation_text(result)


class DeterministicVisionLanguageAnalyzer:
    requires_keyframes = False

    def analyze(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
    ) -> SegmentUnderstanding:
        metrics = evidence.metrics_snapshot
        distinctiveness = rounded_metric(metrics.get("visual_novelty", 0.0))
        clarity = rounded_metric(metrics.get("subject_clarity", 0.0))
        story_relevance = rounded_metric(metrics.get("story_alignment", 0.0))
        confidence = rounded_metric((distinctiveness + clarity + story_relevance) / 3)

        if confidence >= 0.75:
            keep_label = "keep"
        elif confidence >= 0.58:
            keep_label = "maybe"
        else:
            keep_label = "reject"

        return SegmentUnderstanding(
            provider="deterministic",
            provider_model="fallback-v1",
            schema_version=SCHEMA_VERSION,
            summary=segment.description,
            subjects=subject_tokens(asset),
            actions=action_tokens(segment, metrics),
            shot_type=infer_shot_type(metrics),
            camera_motion=infer_camera_motion(metrics),
            mood=infer_mood(metrics, segment.analysis_mode),
            story_roles=infer_story_roles(segment, metrics),
            quality_findings=infer_quality_findings(metrics),
            keep_label=keep_label,
            confidence=confidence,
            rationale=(
                f"Fallback analysis favors {segment.analysis_mode} coverage with clarity {clarity:.2f}, "
                f"distinctiveness {distinctiveness:.2f}, and story relevance {story_relevance:.2f}."
            ),
            risk_flags=infer_risk_flags(metrics),
            visual_distinctiveness=distinctiveness,
            clarity=clarity,
            story_relevance=story_relevance,
        )

    def analyze_asset_segments(
        self,
        *,
        asset: Asset,
        tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
    ) -> dict[str, SegmentUnderstanding]:
        return {
            segment.id: self.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            for segment, evidence, story_prompt in tasks
        }

    def runtime_stats(self) -> AIRuntimeStats:
        return AIRuntimeStats()


class LMStudioVisionLanguageAnalyzer:
    requires_keyframes = True

    def __init__(
        self,
        *,
        config: AIProviderConfig,
        client: ProviderClient,
        fallback: VisionLanguageAnalyzer | None = None,
        cache_root: str | Path | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.fallback = fallback or DeterministicVisionLanguageAnalyzer()
        self.last_error_detail = ""
        self.cache_root = Path(cache_root) if cache_root is not None else None
        self._runtime_stats = AIRuntimeStats()

    def analyze(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
    ) -> SegmentUnderstanding:
        cache_key = build_segment_cache_key(
            model=self.config.model,
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=story_prompt,
        )
        cached = load_cached_understanding(self.cache_root, cache_key)
        if cached is not None:
            self._runtime_stats.cached_segment_count += 1
            return cached

        try:
            self._runtime_stats.live_request_count += 1
            payload = self.client.create_json_completion(
                model=self.config.model,
                system_prompt=segment_understanding_system_prompt(),
                user_prompt=segment_understanding_user_prompt(
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    story_prompt=story_prompt,
                ),
                image_paths=evidence.keyframe_paths,
                timeout_sec=self.config.timeout_sec,
            )
            understanding = normalize_model_output(
                payload,
                provider="lmstudio",
                model=self.config.model,
                fallback=self.fallback,
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            if understanding.provider == "lmstudio":
                self._runtime_stats.live_segment_count += 1
            else:
                self._runtime_stats.fallback_segment_count += 1
            store_cached_understanding(self.cache_root, cache_key, understanding)
            return understanding
        except (AIProviderRequestError, OSError, ValueError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.last_error_detail = str(exc)
            fallback = self.fallback.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            fallback.provider = "deterministic"
            fallback.provider_model = "fallback-v1"
            fallback.risk_flags = sorted(set([*fallback.risk_flags, "lmstudio_request_failed"]))
            fallback.rationale = (
                f"{fallback.rationale} LM Studio request failed, so deterministic fallback was used: {self.last_error_detail}"
            )
            self._runtime_stats.fallback_segment_count += 1
            return fallback

    def analyze_asset_segments(
        self,
        *,
        asset: Asset,
        tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
    ) -> dict[str, SegmentUnderstanding]:
        if not tasks:
            return {}

        results: dict[str, SegmentUnderstanding] = {}
        pending: list[tuple[CandidateSegment, SegmentEvidence, str, str]] = []

        for segment, evidence, story_prompt in tasks:
            cache_key = build_segment_cache_key(
                model=self.config.model,
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            cached = load_cached_understanding(self.cache_root, cache_key)
            if cached is not None:
                self._runtime_stats.cached_segment_count += 1
                results[segment.id] = cached
            else:
                pending.append((segment, evidence, story_prompt, cache_key))

        if not pending:
            return results

        image_paths = [
            batch_image_path_for_evidence(evidence)
            for _segment, evidence, _story_prompt, _cache_key in pending
        ]

        try:
            self._runtime_stats.live_request_count += 1
            payload = self.client.create_json_completion(
                model=self.config.model,
                system_prompt=segment_batch_understanding_system_prompt(),
                user_prompt=segment_batch_understanding_user_prompt(
                    asset=asset,
                    tasks=[(segment, evidence, story_prompt) for segment, evidence, story_prompt, _cache_key in pending],
                ),
                image_paths=image_paths,
                timeout_sec=self.config.timeout_sec,
            )
            normalized = normalize_batch_model_output(
                payload=payload,
                provider="lmstudio",
                model=self.config.model,
                fallback=self.fallback,
                asset=asset,
                tasks=[(segment, evidence, story_prompt) for segment, evidence, story_prompt, _cache_key in pending],
            )
            for segment, _evidence, _story_prompt, cache_key in pending:
                understanding = normalized.get(segment.id)
                if understanding is None:
                    continue
                if understanding.provider == "lmstudio":
                    self._runtime_stats.live_segment_count += 1
                else:
                    self._runtime_stats.fallback_segment_count += 1
                store_cached_understanding(self.cache_root, cache_key, understanding)
                results[segment.id] = understanding
        except (AIProviderRequestError, OSError, ValueError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.last_error_detail = str(exc)
            for segment, evidence, story_prompt, _cache_key in pending:
                fallback = self.fallback.analyze(
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    story_prompt=story_prompt,
                )
                fallback.provider = "deterministic"
                fallback.provider_model = "fallback-v1"
                fallback.risk_flags = sorted(set([*fallback.risk_flags, "lmstudio_request_failed"]))
                fallback.rationale = (
                    f"{fallback.rationale} LM Studio batch request failed, so deterministic fallback was used: "
                    f"{self.last_error_detail}"
                )
                self._runtime_stats.fallback_segment_count += 1
                results[segment.id] = fallback

        return results

    def runtime_stats(self) -> AIRuntimeStats:
        return AIRuntimeStats(
            live_segment_count=self._runtime_stats.live_segment_count,
            cached_segment_count=self._runtime_stats.cached_segment_count,
            fallback_segment_count=self._runtime_stats.fallback_segment_count,
            live_request_count=self._runtime_stats.live_request_count,
        )


class MLXVLMVisionLanguageAnalyzer:
    requires_keyframes = True

    def __init__(
        self,
        *,
        config: AIProviderConfig,
        runtime: LocalVisionRuntime,
        fallback: VisionLanguageAnalyzer | None = None,
        cache_root: str | Path | None = None,
        debug_log_path: str | Path | None = None,
    ) -> None:
        self.config = config
        self.runtime = runtime
        self.fallback = fallback or DeterministicVisionLanguageAnalyzer()
        self.last_error_detail = ""
        self.cache_root = Path(cache_root) if cache_root is not None else None
        self.debug_log_path = Path(debug_log_path) if debug_log_path is not None else None
        self._runtime_stats = AIRuntimeStats()

    def analyze(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
    ) -> SegmentUnderstanding:
        cache_key = build_segment_cache_key(
            model=self.config.model,
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=story_prompt,
        )
        cached = load_cached_understanding(self.cache_root, cache_key)
        if cached is not None:
            self._runtime_stats.cached_segment_count += 1
            return cached

        image_path = batch_image_path_for_evidence(evidence)
        if not image_path:
            understanding = self._fallback_understanding(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
                detail="No image evidence was available for mlx-vlm-local.",
                risk_flag="mlx_vlm_no_image_evidence",
            )
            self._runtime_stats.fallback_segment_count += 1
            return understanding

        try:
            self._runtime_stats.live_request_count += 1
            raw = self.runtime.query_image(
                image_path=image_path,
                prompt=local_vlm_segment_understanding_prompt(
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    story_prompt=story_prompt,
                ),
            )
            self._write_debug_entry(
                event="raw_response",
                asset=asset,
                segment=segment,
                evidence=evidence,
                payload={
                    "provider": "mlx-vlm-local",
                    "model": self.config.model,
                    "image_path": image_path,
                    "raw_response": raw,
                },
            )
            payload = parse_json_object(raw)
            if payload is None:
                self._write_debug_entry(
                    event="parse_failed",
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    payload={
                        "provider": "mlx-vlm-local",
                        "model": self.config.model,
                        "image_path": image_path,
                        "raw_response": raw,
                        "error": "MLX-VLM local response did not contain valid JSON.",
                    },
                )
                raise AIProviderRequestError("MLX-VLM local response did not contain valid JSON.")
            understanding = normalize_model_output(
                payload,
                provider="mlx-vlm-local",
                model=self.config.model,
                fallback=self.fallback,
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            self._write_debug_entry(
                event="parsed_response",
                asset=asset,
                segment=segment,
                evidence=evidence,
                payload={
                    "provider": "mlx-vlm-local",
                    "model": self.config.model,
                    "image_path": image_path,
                    "parsed_payload": payload,
                },
            )
            if understanding.provider == "mlx-vlm-local":
                self._runtime_stats.live_segment_count += 1
            else:
                self._runtime_stats.fallback_segment_count += 1
            store_cached_understanding(self.cache_root, cache_key, understanding)
            return understanding
        except (AIProviderRequestError, OSError, ValueError, RuntimeError, TimeoutError, json.JSONDecodeError, ImportError) as exc:
            self.last_error_detail = str(exc)
            self._write_debug_entry(
                event="analyze_failed",
                asset=asset,
                segment=segment,
                evidence=evidence,
                payload={
                    "provider": "mlx-vlm-local",
                    "model": self.config.model,
                    "image_path": image_path,
                    "error": self.last_error_detail,
                },
            )
            understanding = self._fallback_understanding(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
                detail=self.last_error_detail,
                risk_flag="mlx_vlm_local_failed",
            )
            self._runtime_stats.fallback_segment_count += 1
            return understanding

    def analyze_asset_segments(
        self,
        *,
        asset: Asset,
        tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
    ) -> dict[str, SegmentUnderstanding]:
        return {
            segment.id: self.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            for segment, evidence, story_prompt in tasks
        }

    def runtime_stats(self) -> AIRuntimeStats:
        return AIRuntimeStats(
            live_segment_count=self._runtime_stats.live_segment_count,
            cached_segment_count=self._runtime_stats.cached_segment_count,
            fallback_segment_count=self._runtime_stats.fallback_segment_count,
            live_request_count=self._runtime_stats.live_request_count,
        )

    def _write_debug_entry(
        self,
        *,
        event: str,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        payload: dict[str, Any],
    ) -> None:
        if self.debug_log_path is None:
            return
        self.debug_log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "event": event,
            "asset_id": asset.id,
            "asset_name": asset.name,
            "segment_id": segment.id,
            "segment_range": [round(segment.start_sec, 3), round(segment.end_sec, 3)],
            "analysis_mode": segment.analysis_mode,
            "contact_sheet_path": evidence.contact_sheet_path,
            "keyframe_paths": evidence.keyframe_paths,
            **payload,
        }
        with self.debug_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def _fallback_understanding(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
        detail: str,
        risk_flag: str,
    ) -> SegmentUnderstanding:
        fallback = self.fallback.analyze(
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=story_prompt,
        )
        fallback.provider = "deterministic"
        fallback.provider_model = "fallback-v1"
        fallback.risk_flags = sorted(set([*fallback.risk_flags, risk_flag]))
        fallback.rationale = (
            f"{fallback.rationale} MLX-VLM local analysis failed, so deterministic fallback was used: {detail}"
        )
        return fallback


def default_vision_language_analyzer(
    *,
    artifacts_root: str | Path | None = None,
    analysis_config: AIAnalysisConfig | None = None,
) -> VisionLanguageAnalyzer:
    config = load_ai_provider_config()
    status = inspect_ai_provider_status(config=config)
    runtime_config = analysis_config or load_ai_analysis_config()
    if status.effective_provider == "lmstudio" and config.model:
        return LMStudioVisionLanguageAnalyzer(
            config=config,
            client=OpenAICompatibleProviderClient(config.base_url),
            cache_root=(Path(artifacts_root) / "ai-cache") if artifacts_root is not None and runtime_config.cache_enabled else None,
        )
    if status.effective_provider == "mlx-vlm-local" and config.model:
        return MLXVLMVisionLanguageAnalyzer(
            config=config,
            runtime=MLXVLMRuntime(
                model_id=config.model,
                revision=config.revision,
                cache_dir=config.cache_dir,
                device=config.device,
            ),
            cache_root=(Path(artifacts_root) / "ai-cache") if artifacts_root is not None and runtime_config.cache_enabled else None,
            debug_log_path=(Path(artifacts_root) / "vlm-debug.jsonl") if artifacts_root is not None else None,
        )
    return DeterministicVisionLanguageAnalyzer()


def load_ai_provider_config() -> AIProviderConfig:
    timeout_raw = os.environ.get("TIMELINE_AI_TIMEOUT_SEC", "30")
    try:
        timeout_sec = max(5.0, float(timeout_raw))
    except ValueError:
        timeout_sec = 30.0

    provider = os.environ.get("TIMELINE_AI_PROVIDER", "deterministic").strip().lower()
    requested_model = os.environ.get("TIMELINE_AI_MODEL", "").strip()
    model_id = os.environ.get("TIMELINE_AI_MODEL_ID", "").strip()
    revision = os.environ.get("TIMELINE_AI_MODEL_REVISION", "").strip()
    cache_dir = os.environ.get("TIMELINE_AI_MODEL_CACHE_DIR", "").strip()
    device = os.environ.get("TIMELINE_AI_DEVICE", "auto").strip() or "auto"

    if provider == "mlx-vlm-local":
        model_id, revision = resolve_mlx_vlm_model(model=requested_model, model_id=model_id, revision=revision)
        requested_model = model_id
        if not cache_dir:
            cache_dir = str((Path.cwd() / "models" / "mlx-vlm").resolve())

    return AIProviderConfig(
        provider=provider,
        model=requested_model,
        base_url=os.environ.get("TIMELINE_AI_BASE_URL", "http://127.0.0.1:1234/v1").strip(),
        timeout_sec=timeout_sec,
        revision=revision,
        cache_dir=cache_dir,
        device=device,
    )


def load_ai_analysis_config() -> AIAnalysisConfig:
    mode = os.environ.get("TIMELINE_AI_MODE", "fast").strip().lower() or "fast"
    if mode not in {"fast", "full"}:
        mode = "fast"

    max_segments_default = 1 if mode == "fast" else 99
    max_keyframes_default = 1 if mode == "fast" else 4
    max_width_default = 448 if mode == "fast" else 960
    boundary_refinement_enabled = parse_bool_env("TIMELINE_SEGMENT_BOUNDARY_REFINEMENT", True)
    boundary_refinement_legacy_fallback = parse_bool_env("TIMELINE_SEGMENT_LEGACY_FALLBACK", True)
    semantic_boundary_validation_enabled = parse_bool_env("TIMELINE_SEGMENT_SEMANTIC_VALIDATION", True)
    semantic_boundary_ambiguity_threshold = parse_float_env("TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD", 0.7)
    semantic_boundary_ambiguity_threshold = max(0.0, min(1.0, semantic_boundary_ambiguity_threshold))
    semantic_boundary_validation_budget_pct = parse_int_env("TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT", 100)
    semantic_boundary_validation_budget_pct = max(0, min(100, semantic_boundary_validation_budget_pct))
    semantic_boundary_validation_max_segments = max(
        0,
        parse_int_env("TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS", 2),
    )
    semantic_boundary_max_adjustment_sec = max(
        0.25,
        parse_float_env("TIMELINE_SEGMENT_SEMANTIC_MAX_ADJUSTMENT_SEC", 1.5),
    )

    # CLIP configuration
    clip_min_score_raw = os.environ.get("TIMELINE_AI_CLIP_MIN_SCORE", "0.35").strip()
    try:
        clip_min_score = float(clip_min_score_raw)
        clip_min_score = max(0.0, min(1.0, clip_min_score))  # Clamp to [0, 1]
    except ValueError:
        clip_min_score = 0.35

    vlm_budget_pct = parse_int_env("TIMELINE_AI_VLM_BUDGET_PCT", 100)
    vlm_budget_pct = max(0, min(100, vlm_budget_pct))  # Clamp to [0, 100]

    return AIAnalysisConfig(
        mode=mode,
        max_segments_per_asset=max(1, parse_int_env("TIMELINE_AI_MAX_SEGMENTS_PER_ASSET", max_segments_default)),
        max_keyframes_per_segment=max(1, parse_int_env("TIMELINE_AI_MAX_KEYFRAMES", max_keyframes_default)),
        keyframe_max_width=max(160, parse_int_env("TIMELINE_AI_KEYFRAME_MAX_WIDTH", max_width_default)),
        concurrency=max(1, parse_int_env("TIMELINE_AI_CONCURRENCY", 2)),
        cache_enabled=parse_bool_env("TIMELINE_AI_CACHE", True),
        clip_enabled=parse_bool_env("TIMELINE_AI_CLIP_ENABLED", True),
        clip_min_score=clip_min_score,
        vlm_budget_pct=vlm_budget_pct,
        clip_model=os.environ.get("TIMELINE_AI_CLIP_MODEL", "ViT-B-32").strip() or "ViT-B-32",
        clip_model_pretrained=os.environ.get("TIMELINE_AI_CLIP_MODEL_PRETRAINED", "laion2b_s34b_b79k").strip() or "laion2b_s34b_b79k",
        boundary_refinement_enabled=boundary_refinement_enabled,
        boundary_refinement_legacy_fallback=boundary_refinement_legacy_fallback,
        semantic_boundary_validation_enabled=semantic_boundary_validation_enabled,
        semantic_boundary_ambiguity_threshold=semantic_boundary_ambiguity_threshold,
        semantic_boundary_validation_budget_pct=semantic_boundary_validation_budget_pct,
        semantic_boundary_validation_max_segments=semantic_boundary_validation_max_segments,
        semantic_boundary_max_adjustment_sec=semantic_boundary_max_adjustment_sec,
    )


def inspect_ai_provider_status(
    config: AIProviderConfig | None = None,
    *,
    runtime_probe: bool = False,
) -> AIProviderStatus:
    effective_config = config or load_ai_provider_config()

    if effective_config.provider == "mlx-vlm-local":
        return inspect_mlx_vlm_provider_status(effective_config, runtime_probe=runtime_probe)

    if effective_config.provider != "lmstudio":
        return AIProviderStatus(
            configured_provider=effective_config.provider,
            effective_provider="deterministic",
            model=effective_config.model,
            base_url=effective_config.base_url,
            revision=effective_config.revision,
            cache_dir=effective_config.cache_dir,
            device=effective_config.device,
            available=True,
            detail="Deterministic structured analysis is active.",
        )

    if not effective_config.model:
        return AIProviderStatus(
            configured_provider="lmstudio",
            effective_provider="deterministic",
            model="",
            base_url=effective_config.base_url,
            revision=effective_config.revision,
            cache_dir=effective_config.cache_dir,
            device=effective_config.device,
            available=False,
            detail="LM Studio was requested but TIMELINE_AI_MODEL is empty. Falling back to deterministic analysis.",
        )

    models_url = f"{effective_config.base_url.rstrip('/')}/models"
    try:
        req = request.Request(models_url, method="GET")
        with request.urlopen(req, timeout=min(effective_config.timeout_sec, 3.0)) as response:
            raw = response.read().decode("utf-8")
        payload = json.loads(raw)
        advertised = []
        for item in payload.get("data", []):
            if isinstance(item, dict):
                identifier = str(item.get("id", "")).strip()
                if identifier:
                    advertised.append(identifier)

        if advertised and not any(model_matches(effective_config.model, identifier) for identifier in advertised):
            return AIProviderStatus(
                configured_provider="lmstudio",
                effective_provider="deterministic",
                model=effective_config.model,
                base_url=effective_config.base_url,
                revision=effective_config.revision,
                cache_dir=effective_config.cache_dir,
                device=effective_config.device,
                available=False,
                detail=(
                    f"LM Studio is reachable at {effective_config.base_url}, but model "
                    f"'{effective_config.model}' was not listed. Falling back to deterministic analysis."
                ),
            )

        return AIProviderStatus(
            configured_provider="lmstudio",
            effective_provider="lmstudio",
            model=effective_config.model,
            base_url=effective_config.base_url,
            revision=effective_config.revision,
            cache_dir=effective_config.cache_dir,
            device=effective_config.device,
            available=True,
            detail=f"LM Studio is reachable at {effective_config.base_url}; model '{effective_config.model}' will be used.",
        )
    except (OSError, error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return AIProviderStatus(
            configured_provider="lmstudio",
            effective_provider="deterministic",
            model=effective_config.model,
            base_url=effective_config.base_url,
            revision=effective_config.revision,
            cache_dir=effective_config.cache_dir,
            device=effective_config.device,
            available=False,
            detail=(
                f"LM Studio is not reachable at {effective_config.base_url}. "
                "Falling back to deterministic analysis."
            ),
        )


def inspect_mlx_vlm_provider_status(
    config: AIProviderConfig,
    *,
    runtime_probe: bool = False,
) -> AIProviderStatus:
    missing = missing_mlx_vlm_dependencies()
    ffmpeg_available = shutil.which("ffmpeg") is not None
    cache_path = Path(config.cache_dir).expanduser() if config.cache_dir else None
    cache_exists = bool(cache_path and cache_path.exists())
    prepared_model_path = resolve_prepared_mlx_vlm_model_path(
        model_id=config.model,
        revision=config.revision,
        cache_dir=config.cache_dir,
    )
    apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"

    if missing:
        return AIProviderStatus(
            configured_provider="mlx-vlm-local",
            effective_provider="deterministic",
            model=config.model,
            base_url=config.base_url,
            revision=config.revision,
            cache_dir=config.cache_dir,
            device=config.device,
            available=False,
            detail=(
                "MLX-VLM local backend is not ready because required Python modules are missing: "
                + ", ".join(missing)
                + ". Falling back to deterministic analysis."
            ),
        )

    if not apple_silicon:
        return AIProviderStatus(
            configured_provider="mlx-vlm-local",
            effective_provider="deterministic",
            model=config.model,
            base_url=config.base_url,
            revision=config.revision,
            cache_dir=config.cache_dir,
            device=config.device,
            available=False,
            detail=(
                "MLX-VLM local backend requires Apple Silicon on macOS. "
                "Falling back to deterministic analysis."
            ),
        )

    if not ffmpeg_available:
        return AIProviderStatus(
            configured_provider="mlx-vlm-local",
            effective_provider="deterministic",
            model=config.model,
            base_url=config.base_url,
            revision=config.revision,
            cache_dir=config.cache_dir,
            device=config.device,
            available=False,
            detail=(
                "MLX-VLM local backend requires ffmpeg to extract keyframes and build contact sheets, "
                "but ffmpeg is not installed or not on PATH. Falling back to deterministic analysis."
            ),
        )

    if prepared_model_path is None:
        return AIProviderStatus(
            configured_provider="mlx-vlm-local",
            effective_provider="deterministic",
            model=config.model,
            base_url=config.base_url,
            revision=config.revision,
            cache_dir=config.cache_dir,
            device=config.device,
            available=False,
            detail=(
                "MLX-VLM local backend has no prepared local model files yet. "
                "Run `npm run setup` to download the configured model before processing."
            ),
        )

    if runtime_probe:
        try:
            runtime = MLXVLMRuntime(
                model_id=config.model,
                revision=config.revision,
                cache_dir=config.cache_dir,
                device=config.device,
            )
            runtime.ensure_loaded()
            return AIProviderStatus(
                configured_provider="mlx-vlm-local",
                effective_provider="mlx-vlm-local",
                model=config.model,
                base_url=config.base_url,
                revision=config.revision,
                cache_dir=config.cache_dir,
                device=runtime.device,
                available=True,
                detail=(
                    f"MLX-VLM local backend is ready; model '{config.model}'"
                    + (f" revision '{config.revision}'" if config.revision else "")
                    + f" loaded on device '{runtime.device}'."
                ),
            )
        except Exception as exc:
            return AIProviderStatus(
                configured_provider="mlx-vlm-local",
                effective_provider="deterministic",
                model=config.model,
                base_url=config.base_url,
                revision=config.revision,
                cache_dir=config.cache_dir,
                device=config.device,
                available=False,
                detail=(
                    "MLX-VLM local backend could not load the configured model. "
                    f"Falling back to deterministic analysis. Error: {exc}"
                ),
            )

    detail = (
        f"MLX-VLM local backend is configured for model '{config.model}'"
        + (f" revision '{config.revision}'" if config.revision else "")
        + (f"; cache {'found' if cache_exists else 'not found yet'} at {config.cache_dir}" if config.cache_dir else "")
        + (f"; prepared model path {prepared_model_path}" if prepared_model_path else "")
        + f"; requested runtime '{resolve_mlx_device(requested=config.device)}'."
    )
    return AIProviderStatus(
        configured_provider="mlx-vlm-local",
        effective_provider="mlx-vlm-local",
        model=config.model,
        base_url=config.base_url,
        revision=config.revision,
        cache_dir=config.cache_dir,
        device=resolve_mlx_device(requested=config.device),
        available=True,
        detail=detail,
    )


def build_segment_evidence(
    *,
    asset: Asset,
    segment: CandidateSegment,
    asset_segments: list[CandidateSegment],
    segment_index: int,
    story_prompt: str,
    artifacts_root: str | Path | None,
    extract_keyframes: bool,
    max_keyframes_per_segment: int = 3,
    keyframe_max_width: int = 640,
) -> SegmentEvidence:
    keyframe_timestamps = keyframe_timestamps_for_segment(
        segment.start_sec,
        segment.end_sec,
        target_count=max_keyframes_per_segment,
    )
    keyframe_paths: list[str] = []
    contact_sheet_path = ""

    if extract_keyframes and artifacts_root is not None:
        keyframe_paths = extract_segment_keyframes(
            asset=asset,
            segment=segment,
            timestamps=keyframe_timestamps,
            artifacts_root=artifacts_root,
            max_width=keyframe_max_width,
        )
        contact_sheet_path = create_segment_contact_sheet(
            asset=asset,
            segment=segment,
            keyframe_paths=keyframe_paths,
            artifacts_root=artifacts_root,
        )

    context_window_start_sec = segment.start_sec
    context_window_end_sec = segment.end_sec
    if segment_index > 0:
        context_window_start_sec = asset_segments[segment_index - 1].start_sec
    if segment_index < len(asset_segments) - 1:
        context_window_end_sec = asset_segments[segment_index + 1].end_sec

    return SegmentEvidence(
        media_path=asset.proxy_path,
        transcript_excerpt=segment.transcript_excerpt,
        story_prompt=story_prompt,
        analysis_mode=segment.analysis_mode,
        keyframe_timestamps_sec=[round(timestamp, 3) for timestamp in keyframe_timestamps],
        keyframe_paths=keyframe_paths,
        contact_sheet_path=contact_sheet_path,
        context_window_start_sec=round(context_window_start_sec, 3),
        context_window_end_sec=round(context_window_end_sec, 3),
        metrics_snapshot=dict(segment.quality_metrics),
    )


def keyframe_timestamps_for_segment(
    start_sec: float,
    end_sec: float,
    target_count: int | None = None,
) -> list[float]:
    duration = max(0.01, end_sec - start_sec)
    count = target_count or (3 if duration <= 8.0 else 4)
    count = max(1, count)
    step = duration / (count + 1)
    return [start_sec + (step * index) for index in range(1, count + 1)]


def extract_segment_keyframes(
    *,
    asset: Asset,
    segment: CandidateSegment,
    timestamps: list[float],
    artifacts_root: str | Path,
    max_width: int,
) -> list[str]:
    if shutil.which("ffmpeg") is None:
        return []

    segment_dir = Path(artifacts_root) / "keyframes" / asset.id
    segment_dir.mkdir(parents=True, exist_ok=True)

    extracted: list[str] = []
    for index, timestamp in enumerate(timestamps, start=1):
        target = segment_dir / f"{segment.id}-k{index:02d}.jpg"
        process = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                asset.proxy_path,
                "-vf",
                f"scale=min({max_width}\\,iw):-2",
                "-frames:v",
                "1",
                "-q:v",
                "4",
                str(target),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if process.returncode == 0 and target.exists():
            extracted.append(str(target))

    return extracted


def create_segment_contact_sheet(
    *,
    asset: Asset,
    segment: CandidateSegment,
    keyframe_paths: list[str],
    artifacts_root: str | Path,
) -> str:
    if not keyframe_paths:
        return ""
    if len(keyframe_paths) == 1:
        return keyframe_paths[0]
    if shutil.which("ffmpeg") is None:
        return keyframe_paths[0]

    contact_dir = Path(artifacts_root) / "contact-sheets" / asset.id
    contact_dir.mkdir(parents=True, exist_ok=True)
    target = contact_dir / f"{segment.id}.jpg"
    command = ["ffmpeg", "-y", "-v", "error"]
    for path in keyframe_paths:
        command.extend(["-i", path])
    command.extend(
        [
            "-filter_complex",
            f"hstack=inputs={len(keyframe_paths)}",
            "-q:v",
            "4",
            str(target),
        ]
    )
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode == 0 and target.exists():
        return str(target)
    return keyframe_paths[0]


def segment_understanding_system_prompt() -> str:
    return (
        "You analyze short video segments for an editor. "
        "Return exactly one JSON object only. Do not add markdown fences or commentary. "
        "Use concise editorial language and keep the response short. "
        "subjects, actions, story_roles, quality_findings, and risk_flags must each contain at most 3 short items. "
        "keep_label must be one of: keep, maybe, reject. "
        "confidence, visual_distinctiveness, clarity, and story_relevance must be numbers from 0 to 1. "
        "Keys required: summary, subjects, actions, shot_type, camera_motion, mood, "
        "story_roles, quality_findings, keep_label, confidence, rationale, risk_flags, "
        "visual_distinctiveness, clarity, story_relevance."
    )


def segment_batch_understanding_system_prompt() -> str:
    return (
        "You analyze shortlisted video segments from the same source clip for an editor. "
        "Return exactly one JSON object only. Do not add markdown fences or commentary. "
        "Keep each segment result short. subjects, actions, story_roles, quality_findings, and risk_flags "
        "must each contain at most 3 short items. "
        "keep_label must be one of: keep, maybe, reject. "
        "confidence, visual_distinctiveness, clarity, and story_relevance must be numbers from 0 to 1. "
        "Respond with an object containing a `segments` array. "
        "Each array item must include: segment_id, summary, subjects, actions, shot_type, camera_motion, "
        "mood, story_roles, quality_findings, keep_label, confidence, rationale, risk_flags, "
        "visual_distinctiveness, clarity, story_relevance."
    )


def segment_understanding_user_prompt(
    *,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    metrics = ", ".join(
        f"{key}={value:.2f}" for key, value in sorted(evidence.metrics_snapshot.items())
    )
    transcript = evidence.transcript_excerpt or "No transcript excerpt available."
    keyframes = ", ".join(f"{timestamp:.2f}s" for timestamp in evidence.keyframe_timestamps_sec)

    return (
        "Project story prompt:\n"
        f"{story_prompt}\n\n"
        "Segment metadata:\n"
        f"- Asset: {asset.name}\n"
        f"- Reel: {asset.interchange_reel_name}\n"
        f"- Analysis mode: {segment.analysis_mode}\n"
        f"- Segment: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s\n"
        f"- Context window: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s\n"
        f"- Keyframe timestamps: {keyframes}\n"
        f"- Metrics: {metrics}\n"
        f"- Transcript: {transcript}\n\n"
        "Decide what is happening in the segment, whether it is editorially useful, "
        "what role it could play in a rough cut, and whether it should be kept."
    )


def segment_batch_understanding_user_prompt(
    *,
    asset: Asset,
    tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
) -> str:
    story_prompt = tasks[0][2] if tasks else ""
    lines = [
        "Project story prompt:",
        story_prompt,
        "",
        "Asset metadata:",
        f"- Asset: {asset.name}",
        f"- Reel: {asset.interchange_reel_name}",
        "",
        "Images are provided in the same order as the segments below. Each image is a stitched contact sheet for one segment.",
        "Evaluate each segment independently and return output for every listed segment.",
        "",
        "Segments:",
    ]
    for index, (segment, evidence, _story_prompt) in enumerate(tasks, start=1):
        metrics = ", ".join(
            f"{key}={value:.2f}" for key, value in sorted(evidence.metrics_snapshot.items())
        )
        transcript = evidence.transcript_excerpt or "No transcript excerpt available."
        lines.extend(
            [
                f"{index}. segment_id={segment.id}",
                f"   - analysis_mode: {segment.analysis_mode}",
                f"   - range: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s",
                f"   - context: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s",
                f"   - keyframes: {', '.join(f'{timestamp:.2f}s' for timestamp in evidence.keyframe_timestamps_sec)}",
                f"   - transcript: {transcript}",
                f"   - metrics: {metrics}",
            ]
        )
    return "\n".join(lines)


def local_vlm_segment_understanding_prompt(
    *,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    metrics = ", ".join(
        f"{key}={value:.2f}" for key, value in sorted(evidence.metrics_snapshot.items())
    )
    transcript = evidence.transcript_excerpt or "No transcript excerpt available."
    return (
        "Analyze this stitched contact sheet from a shortlisted video segment and respond with exactly one compact JSON object. "
        "No markdown fences. No commentary outside JSON. No duplicated list items. "
        "Return JSON with these keys only: "
        "summary, subjects, actions, shot_type, camera_motion, mood, keep_label, confidence, rationale.\n"
        "Rules: summary and rationale must each be one short sentence with real content. "
        "subjects and actions may contain 0 to 2 short items only. "
        "shot_type must be a real label like wide, medium, close, detail, overhead, or low angle. "
        "camera_motion must be a real label like static, handheld, pan, tilt, tracking, or walking. "
        "mood must be a real label like calm, active, tense, work, or casual. "
        "keep_label must be exactly one of keep, maybe, reject. "
        "confidence must be a number between 0 and 1. "
        "If unsure, use fewer items, not more. Do not use placeholder words like short label, short sentence, item1, or item2.\n\n"
        f"Project story prompt: {story_prompt}\n"
        f"Asset: {asset.name}\n"
        f"Reel: {asset.interchange_reel_name}\n"
        f"Analysis mode: {segment.analysis_mode}\n"
        f"Segment range: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s\n"
        f"Context window: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s\n"
        f"Transcript: {transcript}\n"
        f"Metrics: {metrics}\n"
        "Focus on whether the segment has a clear subject, usable motion, readable composition, and editorial usefulness."
    )


def boundary_validation_system_prompt() -> str:
    return (
        "You validate whether a short video segment starts and ends at a complete editorial beat. "
        "Return exactly one JSON object only. Do not add markdown fences or commentary. "
        "Keys required: decision, reason, confidence, suggested_start_sec, suggested_end_sec, split_point_sec. "
        "decision must be one of: keep, extend, trim, split. "
        "reason must be one short sentence. confidence must be a number from 0 to 1. "
        "Use null for split_point_sec unless decision is split. "
        "When decision is keep, suggested_start_sec and suggested_end_sec should match the current segment bounds."
    )


def boundary_validation_user_prompt(
    *,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    metrics = ", ".join(
        f"{key}={value:.2f}" for key, value in sorted(evidence.metrics_snapshot.items())
    )
    transcript = evidence.transcript_excerpt or "No transcript excerpt available."
    boundary_strategy = segment.prefilter.boundary_strategy if segment.prefilter is not None else "unknown"
    assembly = (
        f"{segment.prefilter.assembly_operation}:{segment.prefilter.assembly_rule_family}"
        if segment.prefilter is not None and segment.prefilter.assembly_operation != "none"
        else "none"
    )
    return (
        "Project story prompt:\n"
        f"{story_prompt}\n\n"
        "Segment metadata:\n"
        f"- Asset: {asset.name}\n"
        f"- Reel: {asset.interchange_reel_name}\n"
        f"- Analysis mode: {segment.analysis_mode}\n"
        f"- Segment: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s\n"
        f"- Context window: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s\n"
        f"- Boundary strategy: {boundary_strategy}\n"
        f"- Assembly lineage: {assembly}\n"
        f"- Transcript: {transcript}\n"
        f"- Metrics: {metrics}\n\n"
        "Decide whether the current segment is complete as-is, needs a small extend or trim, "
        "or contains two ideas that should be split once. Keep adjustments local to the current bounds."
    )


def local_vlm_boundary_validation_prompt(
    *,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    return (
        "Analyze this stitched contact sheet and decide whether the segment boundaries feel complete. "
        "Return exactly one compact JSON object only with keys: "
        "decision, reason, confidence, suggested_start_sec, suggested_end_sec, split_point_sec. "
        "decision must be keep, extend, trim, or split. "
        "confidence must be a number between 0 and 1. reason must be one short sentence. "
        "If the segment is already complete, use decision keep and repeat the current start and end. "
        "Only suggest nearby changes.\n\n"
        f"Project story prompt: {story_prompt}\n"
        f"Asset: {asset.name}\n"
        f"Reel: {asset.interchange_reel_name}\n"
        f"Analysis mode: {segment.analysis_mode}\n"
        f"Segment range: {segment.start_sec:.2f}s to {segment.end_sec:.2f}s\n"
        f"Context window: {evidence.context_window_start_sec:.2f}s to {evidence.context_window_end_sec:.2f}s\n"
        f"Transcript: {evidence.transcript_excerpt or 'No transcript excerpt available.'}\n"
        "Focus on whether the moment starts too late, ends too early, or bundles two separate beats."
    )


def normalize_boundary_validation_output(
    payload: dict[str, object],
    *,
    provider: str,
    model: str,
    segment: CandidateSegment,
) -> BoundaryValidationResult:
    decision_raw = str(payload.get("decision", "keep")).strip().lower()
    decision = decision_raw if decision_raw in {"keep", "extend", "trim", "split"} else "keep"
    reason = string_or_default(payload.get("reason"), "Semantic validation kept the deterministic boundary.")
    confidence = rounded_metric(number_or_default(payload.get("confidence"), 0.0))
    suggested_start_sec = round(float(number_or_default(payload.get("suggested_start_sec"), segment.start_sec)), 3)
    suggested_end_sec = round(float(number_or_default(payload.get("suggested_end_sec"), segment.end_sec)), 3)
    split_point_sec = payload.get("split_point_sec")
    split_ranges_sec: list[list[float]] = []
    if decision == "split":
        split_point = number_or_default(split_point_sec, (segment.start_sec + segment.end_sec) / 2.0)
        split_ranges_sec = [
            [round(segment.start_sec, 3), round(split_point, 3)],
            [round(split_point, 3), round(segment.end_sec, 3)],
        ]

    return BoundaryValidationResult(
        status="validated",
        decision=decision,
        reason=reason,
        confidence=confidence,
        provider=provider,
        provider_model=model,
        original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        suggested_range_sec=[round(suggested_start_sec, 3), round(suggested_end_sec, 3)],
        split_ranges_sec=split_ranges_sec,
    )


def boundary_validation_fallback_result(
    *,
    segment: CandidateSegment,
    detail: str,
    provider: str = "deterministic",
    model: str = "fallback-v1",
    skip_reason: str = "request_failed",
) -> BoundaryValidationResult:
    return BoundaryValidationResult(
        status="fallback",
        decision="keep",
        reason=f"Semantic boundary validation fell back to deterministic output: {detail}",
        confidence=0.0,
        provider=provider,
        provider_model=model,
        skip_reason=skip_reason,
        applied=False,
        original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        suggested_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
    )


def extract_generation_text(result: Any) -> str:
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text.strip()
    return str(result).strip()


def normalize_model_output(
    payload: dict[str, object],
    *,
    provider: str,
    model: str,
    fallback: VisionLanguageAnalyzer,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> SegmentUnderstanding:
    fallback_understanding = fallback.analyze(
        asset=asset,
        segment=segment,
        evidence=evidence,
        story_prompt=story_prompt,
    )

    return SegmentUnderstanding(
        provider=provider,
        provider_model=model,
        schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
        summary=string_or_default(payload.get("summary"), fallback_understanding.summary),
        subjects=list_or_default(payload.get("subjects"), fallback_understanding.subjects),
        actions=list_or_default(payload.get("actions"), fallback_understanding.actions),
        shot_type=string_or_default(payload.get("shot_type"), fallback_understanding.shot_type),
        camera_motion=string_or_default(payload.get("camera_motion"), fallback_understanding.camera_motion),
        mood=string_or_default(payload.get("mood"), fallback_understanding.mood),
        story_roles=list_or_default(payload.get("story_roles"), fallback_understanding.story_roles),
        quality_findings=list_or_default(
            payload.get("quality_findings"),
            fallback_understanding.quality_findings,
        ),
        keep_label=keep_label_or_default(payload.get("keep_label"), fallback_understanding.keep_label),
        confidence=rounded_metric(number_or_default(payload.get("confidence"), fallback_understanding.confidence)),
        rationale=string_or_default(payload.get("rationale"), fallback_understanding.rationale),
        risk_flags=list_or_default(payload.get("risk_flags"), fallback_understanding.risk_flags),
        visual_distinctiveness=rounded_metric(
            number_or_default(payload.get("visual_distinctiveness"), fallback_understanding.visual_distinctiveness)
        ),
        clarity=rounded_metric(number_or_default(payload.get("clarity"), fallback_understanding.clarity)),
        story_relevance=rounded_metric(
            number_or_default(payload.get("story_relevance"), fallback_understanding.story_relevance)
        ),
    )


def normalize_batch_model_output(
    *,
    payload: dict[str, object],
    provider: str,
    model: str,
    fallback: VisionLanguageAnalyzer,
    asset: Asset,
    tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
) -> dict[str, SegmentUnderstanding]:
    items = payload.get("segments", [])
    by_segment_id = {
        str(item.get("segment_id", "")).strip(): item
        for item in items
        if isinstance(item, dict)
    } if isinstance(items, list) else {}

    normalized: dict[str, SegmentUnderstanding] = {}
    for segment, evidence, story_prompt in tasks:
        item = by_segment_id.get(segment.id)
        if item is None:
            understanding = fallback.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            understanding.risk_flags = sorted(set([*understanding.risk_flags, "lmstudio_incomplete_batch_result"]))
            understanding.rationale = (
                f"{understanding.rationale} LM Studio batch response did not include this segment, "
                "so deterministic fallback was used."
            )
        else:
            understanding = normalize_model_output(
                item,
                provider=provider,
                model=model,
                fallback=fallback,
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
        normalized[segment.id] = understanding
    return normalized


def batch_image_path_for_evidence(evidence: SegmentEvidence) -> str:
    if evidence.contact_sheet_path:
        return evidence.contact_sheet_path
    if evidence.keyframe_paths:
        return evidence.keyframe_paths[0]
    return ""


def infer_story_roles(segment: CandidateSegment, metrics: dict[str, float]) -> list[str]:
    roles: list[str] = []
    if segment.start_sec <= 0.5:
        roles.append("opener")
    if metrics.get("story_alignment", 0.0) >= 0.72:
        roles.append("bridge")
    if metrics.get("visual_novelty", 0.0) >= 0.78:
        roles.append("payoff")
    if not roles:
        roles.append("detail" if metrics.get("subject_clarity", 0.0) >= 0.78 else "bridge")
    return roles


def infer_quality_findings(metrics: dict[str, float]) -> list[str]:
    findings: list[str] = []
    if metrics.get("subject_clarity", 0.0) >= 0.8:
        findings.append("clear framing")
    if metrics.get("motion_energy", 0.0) >= 0.72:
        findings.append("usable motion")
    if metrics.get("duration_fit", 0.0) >= 0.75:
        findings.append("rough-cut friendly duration")
    if not findings:
        findings.append("usable coverage")
    return findings


def infer_risk_flags(metrics: dict[str, float]) -> list[str]:
    risks: list[str] = []
    if metrics.get("motion_energy", 0.0) < 0.38:
        risks.append("low_motion")
    if metrics.get("subject_clarity", 0.0) < 0.6:
        risks.append("low_clarity")
    if metrics.get("story_alignment", 0.0) < 0.58:
        risks.append("weak_story_fit")
    return risks


def infer_shot_type(metrics: dict[str, float]) -> str:
    if metrics.get("visual_novelty", 0.0) >= 0.8 and metrics.get("motion_energy", 0.0) >= 0.7:
        return "wide"
    if metrics.get("subject_clarity", 0.0) >= 0.8:
        return "detail"
    if metrics.get("motion_energy", 0.0) < 0.45:
        return "static"
    return "medium"


def infer_camera_motion(metrics: dict[str, float]) -> str:
    motion_energy = metrics.get("motion_energy", 0.0)
    if motion_energy < 0.35:
        return "static"
    if motion_energy < 0.65:
        return "gentle movement"
    return "active movement"


def infer_mood(metrics: dict[str, float], analysis_mode: str) -> str:
    if analysis_mode == "speech":
        return "informative" if metrics.get("story_alignment", 0.0) >= 0.7 else "conversational"
    if metrics.get("motion_energy", 0.0) >= 0.72:
        return "energetic"
    if metrics.get("visual_novelty", 0.0) >= 0.76:
        return "cinematic"
    return "steady"


def subject_tokens(asset: Asset) -> list[str]:
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", asset.name.lower()) if token]
    if not tokens:
        return [asset.interchange_reel_name.lower()]
    return tokens[:3]


def action_tokens(segment: CandidateSegment, metrics: dict[str, float]) -> list[str]:
    if segment.analysis_mode == "speech":
        return ["speaking", "delivering a line"]
    if metrics.get("motion_energy", 0.0) >= 0.7:
        return ["camera move", "visual transition"]
    return ["holding frame", "ambient coverage"]


def encode_image_as_data_url(image_path: str) -> str | None:
    if not image_path:
        return None
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        return None

    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    payload = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


@contextmanager
def model_cache_environment(cache_dir: str):
    if not cache_dir:
        yield
        return

    cache_path = str(Path(cache_dir).expanduser())
    Path(cache_path).mkdir(parents=True, exist_ok=True)
    previous_hf_home = os.environ.get("HF_HOME")
    previous_hf_hub = os.environ.get("HF_HUB_CACHE")
    os.environ["HF_HOME"] = cache_path
    os.environ["HF_HUB_CACHE"] = str(Path(cache_path) / "hub")
    try:
        yield
    finally:
        if previous_hf_home is None:
            os.environ.pop("HF_HOME", None)
        else:
            os.environ["HF_HOME"] = previous_hf_home
        if previous_hf_hub is None:
            os.environ.pop("HF_HUB_CACHE", None)
        else:
            os.environ["HF_HUB_CACHE"] = previous_hf_hub


def mlx_vlm_manifest_path(cache_dir: str) -> Path:
    return Path(cache_dir).expanduser() / MLX_MODEL_MANIFEST


def load_mlx_vlm_manifest(cache_dir: str) -> dict[str, dict[str, str]]:
    if not cache_dir:
        return {}
    path = mlx_vlm_manifest_path(cache_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    manifest: dict[str, dict[str, str]] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, dict):
            manifest[key] = {str(sub_key): str(sub_value) for sub_key, sub_value in value.items()}
    return manifest


def store_mlx_vlm_manifest_entry(
    *,
    cache_dir: str,
    model_id: str,
    revision: str,
    local_path: str,
) -> None:
    if not cache_dir:
        return
    manifest = load_mlx_vlm_manifest(cache_dir)
    manifest[manifest_model_key(model_id=model_id, revision=revision)] = {
        "model_id": model_id,
        "revision": revision,
        "local_path": local_path,
    }
    path = mlx_vlm_manifest_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def manifest_model_key(*, model_id: str, revision: str) -> str:
    return f"{model_id}@{revision or 'latest'}"


def slugify_model_id(model_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", model_id).strip("-") or "model"


def derived_mlx_vlm_local_path(*, model_id: str, revision: str, cache_dir: str) -> Path:
    return Path(cache_dir).expanduser() / f"{slugify_model_id(model_id)}-{revision or 'latest'}"


def resolve_prepared_mlx_vlm_model_path(
    *,
    model_id: str,
    revision: str,
    cache_dir: str,
) -> str | None:
    if not model_id:
        return None
    direct_path = Path(model_id).expanduser()
    if direct_path.exists():
        return str(direct_path)
    if not cache_dir:
        return None
    manifest = load_mlx_vlm_manifest(cache_dir)
    entry = manifest.get(manifest_model_key(model_id=model_id, revision=revision), {})
    local_path = str(entry.get("local_path", "")).strip()
    if local_path and Path(local_path).exists():
        return local_path
    derived = derived_mlx_vlm_local_path(model_id=model_id, revision=revision, cache_dir=cache_dir)
    if derived.exists():
        return str(derived)
    return None


def parse_json_object(raw: str) -> dict[str, object] | None:
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return salvage_partial_json_object(raw)
        try:
            loaded = json.loads(match.group(0))
            return loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            return salvage_partial_json_object(match.group(0))


def salvage_partial_json_object(raw: str) -> dict[str, object] | None:
    start = raw.find("{")
    if start < 0:
        return None

    candidate = raw[start:].rstrip()
    while candidate:
        try:
            loaded = json.loads(candidate)
            return loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            last_comma = candidate.rfind(",")
            if last_comma < 0:
                break
            candidate = close_partial_json(candidate[:last_comma].rstrip())

    return None


def close_partial_json(raw: str) -> str:
    output: list[str] = []
    closers: list[str] = []
    in_string = False
    escaped = False

    for char in raw:
        output.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            closers.append("}")
        elif char == "[":
            closers.append("]")
        elif char in {"]", "}"} and closers and closers[-1] == char:
            closers.pop()

    if in_string:
        output.append('"')

    while closers:
        output.append(closers.pop())

    return "".join(output)


def missing_mlx_vlm_dependencies() -> list[str]:
    required = {
        "mlx": "mlx",
        "mlx_vlm": "mlx-vlm",
        "torch": "torch",
        "torchvision": "torchvision",
        "PIL": "pillow",
    }
    missing: list[str] = []
    for module_name, label in required.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(label)
    return missing


def resolve_mlx_vlm_model(
    *,
    model: str,
    model_id: str,
    revision: str,
) -> tuple[str, str]:
    requested = (model_id or model).strip()
    if requested and "/" in requested:
        return requested, revision.strip()
    return "mlx-community/Qwen3.5-0.8B-4bit", revision.strip()


def resolve_mlx_device(*, requested: str) -> str:
    requested_value = (requested or "auto").strip().lower()
    if requested_value in {"auto", "", "mps", "metal", "gpu"}:
        return "metal"
    if requested_value == "cpu":
        return "cpu"
    return "metal"


def prepare_mlx_vlm_model(config: AIProviderConfig) -> AIProviderStatus:
    if config.provider != "mlx-vlm-local":
        return inspect_ai_provider_status(config, runtime_probe=False)

    missing = missing_mlx_vlm_dependencies()
    if missing:
        return inspect_ai_provider_status(config, runtime_probe=False)

    local_target = derived_mlx_vlm_local_path(
        model_id=config.model,
        revision=config.revision,
        cache_dir=config.cache_dir,
    )
    local_target.mkdir(parents=True, exist_ok=True)

    huggingface_hub = importlib.import_module("huggingface_hub")
    snapshot_download = getattr(huggingface_hub, "snapshot_download")

    download_kwargs: dict[str, Any] = {
        "repo_id": config.model,
        "local_dir": str(local_target),
        "local_dir_use_symlinks": False,
    }
    if config.revision:
        download_kwargs["revision"] = config.revision

    with model_cache_environment(config.cache_dir):
        downloaded_path = snapshot_download(**download_kwargs)

    store_mlx_vlm_manifest_entry(
        cache_dir=config.cache_dir,
        model_id=config.model,
        revision=config.revision,
        local_path=str(Path(downloaded_path).resolve()),
    )
    return inspect_ai_provider_status(config, runtime_probe=True)


def bootstrap_mlx_vlm_model(config: AIProviderConfig | None = None) -> AIProviderStatus:
    effective_config = config or load_ai_provider_config()
    if effective_config.provider != "mlx-vlm-local":
        return inspect_ai_provider_status(effective_config, runtime_probe=False)
    return prepare_mlx_vlm_model(effective_config)


def string_or_default(value: object, default: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned and not looks_like_placeholder_text(cleaned):
            return cleaned
    return default


def list_or_default(value: object, default: list[str]) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        seen: set[str] = set()
        for item in value:
            cleaned = str(item).strip()
            if not cleaned or looks_like_placeholder_text(cleaned):
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(cleaned)
        if items:
            return items
    return default


def keep_label_or_default(value: object, default: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"keep", "maybe", "reject"}:
            return cleaned
    return default


def looks_like_placeholder_text(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    if not normalized:
        return True
    if normalized in PLACEHOLDER_TEXT_VALUES:
        return True
    if normalized.startswith("short "):
        return True
    return bool(re.fullmatch(r"item\s*\d+", normalized))


def number_or_default(value: object, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def rounded_metric(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def model_matches(requested_model: str, advertised_model: str) -> bool:
    requested = requested_model.strip().lower()
    advertised = advertised_model.strip().lower()
    return requested == advertised or requested in advertised or advertised in requested


def analyze_segments_bounded(
    *,
    analyzer: VisionLanguageAnalyzer,
    tasks: list[tuple[Asset, CandidateSegment, SegmentEvidence, str]],
    concurrency: int,
) -> dict[str, SegmentUnderstanding]:
    if not tasks:
        return {}
    if concurrency <= 1 or len(tasks) == 1:
        return {
            segment.id: analyzer.analyze(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            for asset, segment, evidence, story_prompt in tasks
        }

    results: dict[str, SegmentUnderstanding] = {}
    with ThreadPoolExecutor(max_workers=min(concurrency, len(tasks))) as executor:
        future_map = {
            executor.submit(
                analyzer.analyze,
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            ): segment.id
            for asset, segment, evidence, story_prompt in tasks
        }
        for future in as_completed(future_map):
            segment_id = future_map[future]
            results[segment_id] = future.result()
    return results


def analyze_asset_segments(
    *,
    analyzer: VisionLanguageAnalyzer,
    asset: Asset,
    tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
    concurrency: int,
) -> dict[str, SegmentUnderstanding]:
    if not tasks:
        return {}
    batch_method = getattr(analyzer, "analyze_asset_segments", None)
    if callable(batch_method):
        return batch_method(asset=asset, tasks=tasks)
    expanded = [(asset, segment, evidence, story_prompt) for segment, evidence, story_prompt in tasks]
    return analyze_segments_bounded(
        analyzer=analyzer,
        tasks=expanded,
        concurrency=concurrency,
    )


def validate_segment_boundaries(
    *,
    analyzer: VisionLanguageAnalyzer,
    asset: Asset,
    tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
    concurrency: int,
) -> dict[str, BoundaryValidationResult]:
    if not tasks:
        return {}
    expanded = [(asset, segment, evidence, story_prompt) for segment, evidence, story_prompt in tasks]
    if concurrency <= 1 or len(expanded) == 1:
        return {
            segment.id: validate_single_segment_boundary(
                analyzer=analyzer,
                asset=asset_item,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            )
            for asset_item, segment, evidence, story_prompt in expanded
        }

    results: dict[str, BoundaryValidationResult] = {}
    with ThreadPoolExecutor(max_workers=min(concurrency, len(expanded))) as executor:
        future_map = {
            executor.submit(
                validate_single_segment_boundary,
                analyzer=analyzer,
                asset=asset_item,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
            ): segment.id
            for asset_item, segment, evidence, story_prompt in expanded
        }
        for future in as_completed(future_map):
            results[future_map[future]] = future.result()
    return results


def validate_single_segment_boundary(
    *,
    analyzer: VisionLanguageAnalyzer,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> BoundaryValidationResult:
    if isinstance(analyzer, LMStudioVisionLanguageAnalyzer):
        try:
            image_path = batch_image_path_for_evidence(evidence)
            payload = analyzer.client.create_json_completion(
                model=analyzer.config.model,
                system_prompt=boundary_validation_system_prompt(),
                user_prompt=boundary_validation_user_prompt(
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    story_prompt=story_prompt,
                ),
                image_paths=[image_path] if image_path else evidence.keyframe_paths,
                timeout_sec=analyzer.config.timeout_sec,
            )
            return normalize_boundary_validation_output(
                payload,
                provider="lmstudio",
                model=analyzer.config.model,
                segment=segment,
            )
        except (AIProviderRequestError, OSError, ValueError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            analyzer.last_error_detail = str(exc)
            return boundary_validation_fallback_result(segment=segment, detail=str(exc), skip_reason="request_failed")

    if isinstance(analyzer, MLXVLMVisionLanguageAnalyzer):
        image_path = batch_image_path_for_evidence(evidence)
        if not image_path:
            return boundary_validation_fallback_result(
                segment=segment,
                detail="No image evidence was available for semantic boundary validation.",
                skip_reason="no_evidence",
            )
        try:
            raw = analyzer.runtime.query_image(
                image_path=image_path,
                prompt=local_vlm_boundary_validation_prompt(
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    story_prompt=story_prompt,
                ),
            )
            payload = parse_json_object(raw)
            if payload is None:
                raise AIProviderRequestError("MLX-VLM local response did not contain valid JSON.")
            return normalize_boundary_validation_output(
                payload,
                provider="mlx-vlm-local",
                model=analyzer.config.model,
                segment=segment,
            )
        except (AIProviderRequestError, OSError, ValueError, RuntimeError, TimeoutError, json.JSONDecodeError, ImportError) as exc:
            analyzer.last_error_detail = str(exc)
            return boundary_validation_fallback_result(segment=segment, detail=str(exc), skip_reason="request_failed")

    return BoundaryValidationResult(
        status="skipped",
        decision="keep",
        reason="Semantic boundary validation is unavailable for the active analyzer.",
        confidence=0.0,
        provider="deterministic",
        provider_model="fallback-v1",
        skip_reason="ai_unavailable",
        applied=False,
        original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        suggested_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
    )


def get_ai_runtime_stats(analyzer: VisionLanguageAnalyzer) -> AIRuntimeStats:
    runtime_method = getattr(analyzer, "runtime_stats", None)
    if callable(runtime_method):
        stats = runtime_method()
        if isinstance(stats, AIRuntimeStats):
            return stats
    return AIRuntimeStats()


def load_cached_understanding(cache_root: Path | None, cache_key: str) -> SegmentUnderstanding | None:
    if cache_root is None:
        return None
    target = cache_root / f"{cache_key}.json"
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return SegmentUnderstanding(**payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def store_cached_understanding(cache_root: Path | None, cache_key: str, understanding: SegmentUnderstanding) -> None:
    if cache_root is None:
        return
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / f"{cache_key}.json"
    try:
        payload = asdict(understanding) if hasattr(understanding, "__dataclass_fields__") else dict(understanding)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def build_segment_cache_key(
    *,
    model: str,
    asset: Asset,
    segment: CandidateSegment,
    evidence: SegmentEvidence,
    story_prompt: str,
) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "model": model,
        "asset_id": asset.id,
        "asset_path": asset.proxy_path,
        "segment_id": segment.id,
        "segment_range": [segment.start_sec, segment.end_sec],
        "analysis_mode": segment.analysis_mode,
        "transcript_excerpt": evidence.transcript_excerpt,
        "story_prompt": story_prompt,
        "keyframe_timestamps_sec": evidence.keyframe_timestamps_sec,
    }
    return sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def parse_bool_env(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def parse_int_env(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def parse_float_env(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
