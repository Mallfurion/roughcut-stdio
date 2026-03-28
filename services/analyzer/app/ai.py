from __future__ import annotations

from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib
import json
import platform
from pathlib import Path
import re
import shutil
import subprocess
import threading
from typing import Any, Protocol
from urllib import error, request

from .ai_runtime.adapters import CachedFallbackAdapter
from .ai_runtime.cache import SCHEMA_VERSION
from .ai_runtime.config import (
    AIAnalysisConfig,
    AIProviderConfig,
    AIProviderStatus,
    AIRuntimeStats,
    bootstrap_mlx_vlm_model,
    load_ai_analysis_config,
    load_ai_provider_config,
    missing_mlx_vlm_dependencies,
    model_cache_environment,
    model_matches,
    resolve_mlx_device,
    resolve_prepared_mlx_vlm_model_path,
)
from .ai_runtime.evidence import (
    batch_image_path_for_evidence,
    build_segment_evidence,
    create_segment_contact_sheet,
    extract_segment_keyframes,
    keyframe_timestamps_for_segment,
    segment_evidence_matches,
)
from .ai_runtime.normalize import (
    boundary_validation_fallback_result,
    close_partial_json,
    extract_generation_text,
    keep_label_or_default,
    list_or_default,
    looks_like_placeholder_text,
    normalize_batch_model_output,
    normalize_boundary_validation_output,
    normalize_model_output,
    number_or_default,
    parse_json_object,
    parse_key_value_object,
    rounded_metric,
    salvage_partial_json_object,
    string_or_default,
)
from .ai_runtime.prompts import (
    boundary_validation_system_prompt,
    boundary_validation_user_prompt,
    local_vlm_boundary_validation_prompt,
    local_vlm_segment_understanding_prompt,
    segment_batch_understanding_system_prompt,
    segment_batch_understanding_user_prompt,
    segment_understanding_system_prompt,
    segment_understanding_user_prompt,
)
from .domain import Asset, BoundaryValidationResult, CandidateSegment, SegmentEvidence, SegmentUnderstanding
from .shared.env import parse_bool_env, parse_float_env, parse_int_env


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


class AIProviderRequestError(RuntimeError):
    pass


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
            detail=(
                "LM Studio was requested but TIMELINE_AI_MODEL is empty. "
                "Falling back to deterministic analysis."
            ),
        )

    models_url = f"{effective_config.base_url.rstrip('/')}/models"
    try:
        req = request.Request(models_url, method="GET")
        with request.urlopen(req, timeout=min(effective_config.timeout_sec, 3.0)) as response:
            raw = response.read().decode("utf-8")
        payload = json.loads(raw)
        advertised = [
            str(item.get("id", "")).strip()
            for item in payload.get("data", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        ]
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
            detail=(
                f"LM Studio is reachable at {effective_config.base_url}; "
                f"model '{effective_config.model}' will be used."
            ),
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
        self._runtime_lock = threading.RLock()

    def ensure_loaded(self) -> None:
        with self._runtime_lock:
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

        with self._runtime_lock:
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


class LMStudioVisionLanguageAnalyzer(CachedFallbackAdapter):
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
        super().__init__(
            model=config.model,
            fallback=fallback or DeterministicVisionLanguageAnalyzer(),
            cache_root=cache_root,
        )

    def analyze(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
    ) -> SegmentUnderstanding:
        cache_key, cached = self._prepare_cached_request(
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=story_prompt,
        )
        if cached is not None:
            return cached

        try:
            self._record_live_request()
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
            return self._record_understanding(
                cache_key=cache_key,
                understanding=understanding,
                live_provider="lmstudio",
            )
        except (AIProviderRequestError, OSError, ValueError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.last_error_detail = str(exc)
            fallback = self._make_fallback_understanding(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
                detail=self.last_error_detail,
                risk_flag="lmstudio_request_failed",
                failure_label="LM Studio request failed, so deterministic fallback was used",
            )
            self._record_fallback_result()
            return fallback

    def analyze_asset_segments(
        self,
        *,
        asset: Asset,
        tasks: list[tuple[CandidateSegment, SegmentEvidence, str]],
    ) -> dict[str, SegmentUnderstanding]:
        if not tasks:
            return {}

        results, pending = self._collect_pending_tasks(asset=asset, tasks=tasks)

        if not pending:
            return results

        image_paths = [
            batch_image_path_for_evidence(evidence)
            for _segment, evidence, _story_prompt, _cache_key in pending
        ]

        try:
            self._record_live_request()
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
                results[segment.id] = self._record_understanding(
                    cache_key=cache_key,
                    understanding=understanding,
                    live_provider="lmstudio",
                )
        except (AIProviderRequestError, OSError, ValueError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.last_error_detail = str(exc)
            for segment, evidence, story_prompt, _cache_key in pending:
                fallback = self._make_fallback_understanding(
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    story_prompt=story_prompt,
                    detail=self.last_error_detail,
                    risk_flag="lmstudio_request_failed",
                    failure_label="LM Studio batch request failed, so deterministic fallback was used",
                )
                self._record_fallback_result()
                results[segment.id] = fallback

        return results


class MLXVLMVisionLanguageAnalyzer(CachedFallbackAdapter):
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
        self.debug_log_path = Path(debug_log_path) if debug_log_path is not None else None
        super().__init__(
            model=config.model,
            fallback=fallback or DeterministicVisionLanguageAnalyzer(),
            cache_root=cache_root,
        )

    def analyze(
        self,
        *,
        asset: Asset,
        segment: CandidateSegment,
        evidence: SegmentEvidence,
        story_prompt: str,
    ) -> SegmentUnderstanding:
        cache_key, cached = self._prepare_cached_request(
            asset=asset,
            segment=segment,
            evidence=evidence,
            story_prompt=story_prompt,
        )
        if cached is not None:
            return cached

        image_path = batch_image_path_for_evidence(evidence)
        if not image_path:
            understanding = self._make_fallback_understanding(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
                detail="No image evidence was available for mlx-vlm-local.",
                risk_flag="mlx_vlm_no_image_evidence",
                failure_label="MLX-VLM local analysis failed, so deterministic fallback was used",
            )
            self._record_fallback_result()
            return understanding

        try:
            self._record_live_request()
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
            return self._record_understanding(
                cache_key=cache_key,
                understanding=understanding,
                live_provider="mlx-vlm-local",
            )
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
            understanding = self._make_fallback_understanding(
                asset=asset,
                segment=segment,
                evidence=evidence,
                story_prompt=story_prompt,
                detail=self.last_error_detail,
                risk_flag="mlx_vlm_local_failed",
                failure_label="MLX-VLM local analysis failed, so deterministic fallback was used",
            )
            self._record_fallback_result()
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
                asset=asset,
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
            analyzer._write_debug_entry(
                event="boundary_raw_response",
                asset=asset,
                segment=segment,
                evidence=evidence,
                payload={
                    "provider": "mlx-vlm-local",
                    "model": analyzer.config.model,
                    "image_path": image_path,
                    "raw_response": raw,
                },
            )
            payload = parse_json_object(raw)
            if payload is None:
                payload = parse_key_value_object(
                    raw,
                    allowed_keys={"decision", "reason", "confidence"},
                )
            if payload is None:
                analyzer._write_debug_entry(
                    event="boundary_parse_failed",
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    payload={
                        "provider": "mlx-vlm-local",
                        "model": analyzer.config.model,
                        "image_path": image_path,
                        "raw_response": raw,
                        "error": "MLX-VLM local response did not contain valid JSON.",
                    },
                )
                raise AIProviderRequestError("MLX-VLM local response did not contain valid JSON.")
            result = normalize_boundary_validation_output(
                payload,
                provider="mlx-vlm-local",
                model=analyzer.config.model,
                segment=segment,
                asset=asset,
            )
            analyzer._write_debug_entry(
                event="boundary_parsed_response",
                asset=asset,
                segment=segment,
                evidence=evidence,
                payload={
                    "provider": "mlx-vlm-local",
                    "model": analyzer.config.model,
                    "image_path": image_path,
                    "parsed_payload": payload,
                    "normalized_result": {
                        "decision": result.decision,
                        "confidence": result.confidence,
                        "suggested_range_sec": result.suggested_range_sec,
                        "split_ranges_sec": result.split_ranges_sec,
                    },
                },
            )
            return result
        except (AIProviderRequestError, OSError, ValueError, RuntimeError, TimeoutError, json.JSONDecodeError, ImportError) as exc:
            analyzer.last_error_detail = str(exc)
            analyzer._write_debug_entry(
                event="boundary_validate_failed",
                asset=asset,
                segment=segment,
                evidence=evidence,
                payload={
                    "provider": "mlx-vlm-local",
                    "model": analyzer.config.model,
                    "image_path": image_path,
                    "error": analyzer.last_error_detail,
                },
            )
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
