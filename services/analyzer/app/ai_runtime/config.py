from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
from typing import Any
from urllib import error, request

from ..shared.env import parse_bool_env, parse_float_env, parse_int_env

MLX_MODEL_MANIFEST = "mlx-vlm-manifest.json"


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
    transcript_provider: str = "auto"
    transcript_model_size: str = "small"
    clip_enabled: bool = True
    clip_min_score: float = 0.1
    vlm_budget_pct: int = 100
    clip_model: str = "ViT-B-32"
    clip_model_pretrained: str = "laion2b_s34b_b79k"
    boundary_refinement_enabled: bool = True
    boundary_refinement_legacy_fallback: bool = True
    semantic_boundary_validation_enabled: bool = True
    semantic_boundary_ambiguity_threshold: float = 0.6
    semantic_boundary_floor_threshold: float = 0.45
    semantic_boundary_min_targets: int = 1
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


def load_ai_provider_config() -> AIProviderConfig:
    timeout_raw = os.environ.get("TIMELINE_AI_TIMEOUT_SEC", "30")
    try:
        timeout_sec = max(5.0, float(timeout_raw))
    except ValueError:
        timeout_sec = 30.0

    provider = os.environ.get("TIMELINE_AI_PROVIDER", "mlx-vlm-local").strip().lower()
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
    mode = os.environ.get("TIMELINE_AI_MODE", "full").strip().lower() or "full"
    if mode not in {"fast", "full"}:
        mode = "full"
    transcript_provider = os.environ.get("TIMELINE_TRANSCRIPT_PROVIDER", "auto").strip().lower() or "auto"
    if transcript_provider not in {"auto", "disabled", "faster-whisper"}:
        transcript_provider = "auto"
    transcript_model_size = os.environ.get("TIMELINE_TRANSCRIPT_MODEL_SIZE", "small").strip().lower() or "small"

    max_segments_default = 1 if mode == "fast" else 99
    max_keyframes_default = 1 if mode == "fast" else 4
    max_width_default = 448 if mode == "fast" else 960
    boundary_refinement_enabled = parse_bool_env("TIMELINE_SEGMENT_BOUNDARY_REFINEMENT", True)
    boundary_refinement_legacy_fallback = parse_bool_env("TIMELINE_SEGMENT_LEGACY_FALLBACK", True)
    semantic_boundary_validation_enabled = parse_bool_env("TIMELINE_SEGMENT_SEMANTIC_VALIDATION", True)
    semantic_boundary_ambiguity_threshold = max(
        0.0,
        min(1.0, parse_float_env("TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD", 0.6)),
    )
    semantic_boundary_floor_threshold = max(
        0.0,
        min(1.0, parse_float_env("TIMELINE_SEGMENT_SEMANTIC_FLOOR_THRESHOLD", 0.45)),
    )
    if semantic_boundary_floor_threshold > semantic_boundary_ambiguity_threshold:
        semantic_boundary_floor_threshold = semantic_boundary_ambiguity_threshold
    semantic_boundary_min_targets = max(0, parse_int_env("TIMELINE_SEGMENT_SEMANTIC_MIN_TARGETS", 1))
    semantic_boundary_validation_budget_pct = max(
        0,
        min(100, parse_int_env("TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT", 100)),
    )
    semantic_boundary_validation_max_segments = max(
        0,
        parse_int_env("TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS", 2),
    )
    semantic_boundary_max_adjustment_sec = max(
        0.25,
        parse_float_env("TIMELINE_SEGMENT_SEMANTIC_MAX_ADJUSTMENT_SEC", 1.5),
    )

    clip_min_score_raw = os.environ.get("TIMELINE_AI_CLIP_MIN_SCORE", "0.1").strip()
    try:
        clip_min_score = max(0.0, min(1.0, float(clip_min_score_raw)))
    except ValueError:
        clip_min_score = 0.1

    vlm_budget_pct = max(0, min(100, parse_int_env("TIMELINE_AI_VLM_BUDGET_PCT", 100)))

    return AIAnalysisConfig(
        mode=mode,
        max_segments_per_asset=max(1, parse_int_env("TIMELINE_AI_MAX_SEGMENTS_PER_ASSET", max_segments_default)),
        max_keyframes_per_segment=max(1, parse_int_env("TIMELINE_AI_MAX_KEYFRAMES", max_keyframes_default)),
        keyframe_max_width=max(160, parse_int_env("TIMELINE_AI_KEYFRAME_MAX_WIDTH", max_width_default)),
        concurrency=max(1, parse_int_env("TIMELINE_AI_CONCURRENCY", 2)),
        cache_enabled=parse_bool_env("TIMELINE_AI_CACHE", True),
        transcript_provider=transcript_provider,
        transcript_model_size=transcript_model_size,
        clip_enabled=parse_bool_env("TIMELINE_AI_CLIP_ENABLED", True),
        clip_min_score=clip_min_score,
        vlm_budget_pct=vlm_budget_pct,
        clip_model=os.environ.get("TIMELINE_AI_CLIP_MODEL", "ViT-B-32").strip() or "ViT-B-32",
        clip_model_pretrained=os.environ.get("TIMELINE_AI_CLIP_MODEL_PRETRAINED", "laion2b_s34b_b79k").strip() or "laion2b_s34b_b79k",
        boundary_refinement_enabled=boundary_refinement_enabled,
        boundary_refinement_legacy_fallback=boundary_refinement_legacy_fallback,
        semantic_boundary_validation_enabled=semantic_boundary_validation_enabled,
        semantic_boundary_ambiguity_threshold=semantic_boundary_ambiguity_threshold,
        semantic_boundary_floor_threshold=semantic_boundary_floor_threshold,
        semantic_boundary_min_targets=semantic_boundary_min_targets,
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
            from ..ai import MLXVLMRuntime

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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def store_mlx_vlm_manifest_entry(
    *,
    cache_dir: str,
    model_id: str,
    revision: str,
    local_path: str,
) -> None:
    if not cache_dir:
        return
    path = mlx_vlm_manifest_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_mlx_vlm_manifest(cache_dir)
    manifest[manifest_model_key(model_id=model_id, revision=revision)] = {
        "model_id": model_id,
        "revision": revision,
        "local_path": local_path,
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def manifest_model_key(*, model_id: str, revision: str) -> str:
    return f"{slugify_model_id(model_id)}@{revision or 'default'}"


def slugify_model_id(model_id: str) -> str:
    return model_id.strip().replace("/", "--").replace(":", "-")


def derived_mlx_vlm_local_path(*, model_id: str, revision: str, cache_dir: str) -> Path:
    suffix = f"-{revision}" if revision else ""
    return Path(cache_dir).expanduser() / f"{slugify_model_id(model_id)}{suffix}"


def resolve_prepared_mlx_vlm_model_path(
    *,
    model_id: str,
    revision: str,
    cache_dir: str,
) -> str | None:
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


def missing_mlx_vlm_dependencies() -> list[str]:
    required = {
        "mlx": "mlx",
        "mlx_vlm": "mlx-vlm",
        "torch": "torch",
        "torchvision": "torchvision",
        "PIL": "pillow",
    }
    return [
        label
        for module_name, label in required.items()
        if importlib.util.find_spec(module_name) is None
    ]


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

    if missing_mlx_vlm_dependencies():
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


def model_matches(requested_model: str, advertised_model: str) -> bool:
    requested = requested_model.strip().lower()
    advertised = advertised_model.strip().lower()
    return requested == advertised or requested in advertised or advertised in requested
