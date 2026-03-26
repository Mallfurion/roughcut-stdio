use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, State};

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RuntimeConfig {
    provider: String,
    #[serde(rename = "aiModel")]
    ai_model: String,
    #[serde(rename = "aiBaseUrl")]
    ai_base_url: String,
    #[serde(rename = "aiModelId")]
    ai_model_id: String,
    #[serde(rename = "aiModelRevision")]
    ai_model_revision: String,
    #[serde(rename = "aiModelCacheDir")]
    ai_model_cache_dir: String,
    #[serde(rename = "aiDevice")]
    ai_device: String,
    #[serde(rename = "projectName")]
    project_name: String,
    #[serde(rename = "storyPrompt")]
    story_prompt: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct RuntimeCheckResult {
    configured_provider: String,
    effective_provider: String,
    model: String,
    revision: String,
    cache_dir: String,
    device: String,
    base_url: String,
    available: bool,
    detail: String,
    output: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AppSettings {
    #[serde(rename = "aiProvider")]
    ai_provider: String,
    #[serde(rename = "projectName")]
    project_name: String,
    #[serde(rename = "storyPrompt")]
    story_prompt: String,
    #[serde(rename = "aiMode")]
    ai_mode: String,
    #[serde(rename = "aiTimeoutSec")]
    ai_timeout_sec: String,
    #[serde(rename = "aiModel")]
    ai_model: String,
    #[serde(rename = "aiBaseUrl")]
    ai_base_url: String,
    #[serde(rename = "aiModelId")]
    ai_model_id: String,
    #[serde(rename = "aiDevice")]
    ai_device: String,
    #[serde(rename = "aiMaxSegmentsPerAsset")]
    ai_max_segments_per_asset: String,
    #[serde(rename = "aiMaxKeyframes")]
    ai_max_keyframes: String,
    #[serde(rename = "aiKeyframeMaxWidth")]
    ai_keyframe_max_width: String,
    #[serde(rename = "aiConcurrency")]
    ai_concurrency: String,
    #[serde(rename = "aiCacheEnabled")]
    ai_cache_enabled: bool,
    #[serde(rename = "transcriptProvider")]
    transcript_provider: String,
    #[serde(rename = "transcriptModelSize")]
    transcript_model_size: String,
    #[serde(rename = "audioEnabled")]
    audio_enabled: bool,
    #[serde(rename = "deduplicationEnabled")]
    deduplication_enabled: bool,
    #[serde(rename = "dedupThreshold")]
    dedup_threshold: String,
    #[serde(rename = "clipEnabled")]
    clip_enabled: bool,
    #[serde(rename = "clipMinScore")]
    clip_min_score: String,
    #[serde(rename = "vlmBudgetPct")]
    vlm_budget_pct: String,
    #[serde(rename = "segmentBoundaryRefinementEnabled")]
    segment_boundary_refinement_enabled: bool,
    #[serde(rename = "segmentLegacyFallbackEnabled")]
    segment_legacy_fallback_enabled: bool,
    #[serde(rename = "segmentSemanticValidationEnabled")]
    segment_semantic_validation_enabled: bool,
    #[serde(rename = "segmentSemanticAmbiguityThreshold")]
    segment_semantic_ambiguity_threshold: String,
    #[serde(rename = "segmentSemanticValidationBudgetPct")]
    segment_semantic_validation_budget_pct: String,
    #[serde(rename = "segmentSemanticValidationMaxSegments")]
    segment_semantic_validation_max_segments: String,
    #[serde(rename = "segmentSemanticMaxAdjustmentSec")]
    segment_semantic_max_adjustment_sec: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ProcessRequest {
    #[serde(rename = "mediaDir")]
    media_dir: String,
    #[serde(rename = "aiMode")]
    ai_mode: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct MediaFolderSummary {
    path: String,
    video_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct LoadedProjectPayload {
    project: serde_json::Value,
    source: String,
    file_path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ProcessRunState {
    running: bool,
    status: String,
    processed: usize,
    total: usize,
    current_asset: String,
    elapsed: String,
    eta: String,
    logs: Vec<String>,
    output_path: Option<String>,
    error: Option<String>,
}

impl Default for ProcessRunState {
    fn default() -> Self {
        Self {
            running: false,
            status: "idle".into(),
            processed: 0,
            total: 0,
            current_asset: String::new(),
            elapsed: "00:00".into(),
            eta: "00:00".into(),
            logs: Vec::new(),
            output_path: None,
            error: None,
        }
    }
}

#[derive(Default)]
struct ProcessController {
    state: Arc<Mutex<ProcessRunState>>,
}

#[tauri::command]
fn load_app_settings() -> Result<AppSettings, String> {
    let root = workspace_root()?;
    read_app_settings(&root)
}

#[tauri::command]
fn save_app_settings(settings: AppSettings) -> Result<AppSettings, String> {
    let root = workspace_root()?;
    write_app_settings(&root, &settings)?;
    read_app_settings(&root)
}

#[tauri::command]
fn get_process_state(state: State<ProcessController>) -> Result<ProcessRunState, String> {
    Ok(state
        .state
        .lock()
        .map_err(|_| "Process state lock poisoned".to_string())?
        .clone())
}

#[tauri::command]
fn check_runtime_ready(config: RuntimeConfig) -> Result<RuntimeCheckResult, String> {
    let root = workspace_root()?;
    let output = run_script_capture(&root, "scripts/check_ai.sh", &build_env(&config, None))?;
    Ok(parse_runtime_check_output(&output.stdout, output.status.success()))
}

#[tauri::command]
fn run_setup(config: RuntimeConfig) -> Result<RuntimeCheckResult, String> {
    let root = workspace_root()?;
    let setup_output = run_script_capture(&root, "scripts/setup.sh", &build_env(&config, None))?;
    let check_output = run_script_capture(&root, "scripts/check_ai.sh", &build_env(&config, None))?;
    let mut result = parse_runtime_check_output(&check_output.stdout, check_output.status.success());
    let mut combined = String::new();
    if !setup_output.stdout.trim().is_empty() {
      combined.push_str(&setup_output.stdout);
    }
    if !setup_output.stderr.trim().is_empty() {
      if !combined.is_empty() {
        combined.push_str("\n---\n");
      }
      combined.push_str(&setup_output.stderr);
    }
    if !check_output.stdout.trim().is_empty() {
      if !combined.is_empty() {
        combined.push_str("\n---\n");
      }
      combined.push_str(&check_output.stdout);
    }
    result.output = combined;
    Ok(result)
}

#[tauri::command]
fn inspect_media_folder(path: String) -> Result<MediaFolderSummary, String> {
    let folder = PathBuf::from(path.trim());
    if !folder.exists() {
        return Err(format!("Media folder does not exist: {}", folder.display()));
    }
    if !folder.is_dir() {
        return Err(format!("Media path is not a folder: {}", folder.display()));
    }

    Ok(MediaFolderSummary {
        path: folder.to_string_lossy().into_owned(),
        video_count: count_video_files(&folder)?,
    })
}

#[tauri::command]
fn start_process(
    app: AppHandle,
    state: State<ProcessController>,
    request: ProcessRequest,
) -> Result<(), String> {
    {
        let current = state
            .state
            .lock()
            .map_err(|_| "Process state lock poisoned".to_string())?;
        if current.running {
            return Err("A process run is already active.".into());
        }
    }

    let root = workspace_root()?;
    let mut envs = Vec::new();
    if !request.media_dir.trim().is_empty() {
        envs.push(("TIMELINE_MEDIA_DIR".into(), request.media_dir.clone()));
    }
    if !request.ai_mode.trim().is_empty() {
        envs.push(("TIMELINE_AI_MODE".into(), request.ai_mode.clone()));
    }
    let process_state = state.state.clone();
    let app_handle = app.clone();

    {
        let mut current = process_state
            .lock()
            .map_err(|_| "Process state lock poisoned".to_string())?;
        *current = ProcessRunState {
            running: true,
            status: "running".into(),
            processed: 0,
            total: 0,
            current_asset: String::new(),
            elapsed: "00:00".into(),
            eta: "00:00".into(),
            logs: vec!["Starting process run...".into()],
            output_path: None,
            error: None,
        };
    }
    emit_process_state(&app_handle, &process_state);

    thread::spawn(move || {
        let result = spawn_process_run(&root, &envs, &process_state, &app_handle);
        if let Err(error) = result {
            if let Ok(mut current) = process_state.lock() {
                current.running = false;
                current.status = "failed".into();
                current.error = Some(error.clone());
                current.logs.push(format!("Process failed: {error}"));
            }
            emit_process_state(&app_handle, &process_state);
        }
    });

    Ok(())
}

#[tauri::command]
fn load_active_project() -> Result<LoadedProjectPayload, String> {
    let root = workspace_root()?;
    let generated_path = root.join("generated/project.json");
    let sample_path = root.join("fixtures/sample-project.json");
    let (path, source) = if generated_path.exists() {
        (generated_path, "generated")
    } else {
        (sample_path, "sample")
    };
    let text = fs::read_to_string(&path).map_err(|error| format!("Failed to read project JSON: {error}"))?;
    let value: serde_json::Value =
        serde_json::from_str(&text).map_err(|error| format!("Failed to parse project JSON: {error}"))?;
    Ok(LoadedProjectPayload {
        project: value,
        source: source.into(),
        file_path: path.to_string_lossy().into_owned(),
    })
}

#[tauri::command]
fn export_timeline(target_path: String) -> Result<String, String> {
    let root = workspace_root()?;
    let output = run_script_capture(&root, "scripts/export.sh", &[])?;
    if !output.status.success() {
        return Err(format!(
            "Export script failed:\n{}\n{}",
            output.stdout, output.stderr
        ));
    }
    let source_path = root.join("generated/timeline.fcpxml");
    if !source_path.exists() {
        return Err("Export did not produce generated/timeline.fcpxml".into());
    }
    let target = PathBuf::from(target_path);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|error| format!("Failed to create export directory: {error}"))?;
    }
    fs::copy(&source_path, &target).map_err(|error| format!("Failed to write export target: {error}"))?;
    Ok(target.to_string_lossy().into_owned())
}

#[tauri::command]
fn clean_generated() -> Result<(), String> {
    let root = workspace_root()?;
    let generated_dir = root.join("generated");
    
    if generated_dir.exists() {
        fs::remove_dir_all(&generated_dir)
            .map_err(|error| format!("Failed to remove generated folder: {error}"))?;
    }
    
    Ok(())
}

fn workspace_root() -> Result<PathBuf, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .join("../../..")
        .canonicalize()
        .map_err(|error| format!("Failed to resolve workspace root: {error}"))
}

fn count_video_files(root: &Path) -> Result<usize, String> {
    let mut stack = vec![root.to_path_buf()];
    let mut count = 0usize;

    while let Some(current) = stack.pop() {
        let entries = fs::read_dir(&current)
            .map_err(|error| format!("Failed to read folder {}: {error}", current.display()))?;

        for entry in entries {
            let entry = entry.map_err(|error| format!("Failed to read folder entry: {error}"))?;
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            if !path.is_file() {
                continue;
            }

            let Some(extension) = path.extension().and_then(|value| value.to_str()) else {
                continue;
            };
            match extension.to_ascii_lowercase().as_str() {
                "mp4" | "mov" | "mxf" | "m4v" | "avi" | "mkv" | "webm" => count += 1,
                _ => {}
            }
        }
    }

    Ok(count)
}

fn default_app_settings() -> AppSettings {
    AppSettings {
        ai_provider: "deterministic".into(),
        project_name: "Roughcut Stdio Project".into(),
        story_prompt: "Build a coherent rough cut from the strongest visual and spoken beats.".into(),
        ai_mode: "fast".into(),
        ai_timeout_sec: "45".into(),
        ai_model: "qwen3.5-9b".into(),
        ai_base_url: "http://127.0.0.1:1234/v1".into(),
        ai_model_id: "mlx-community/Qwen3.5-0.8B-4bit".into(),
        ai_device: "auto".into(),
        ai_max_segments_per_asset: "1".into(),
        ai_max_keyframes: "1".into(),
        ai_keyframe_max_width: "448".into(),
        ai_concurrency: "2".into(),
        ai_cache_enabled: true,
        transcript_provider: "auto".into(),
        transcript_model_size: "small".into(),
        audio_enabled: true,
        deduplication_enabled: true,
        dedup_threshold: "0.85".into(),
        clip_enabled: true,
        clip_min_score: "0.35".into(),
        vlm_budget_pct: "100".into(),
        segment_boundary_refinement_enabled: true,
        segment_legacy_fallback_enabled: true,
        segment_semantic_validation_enabled: true,
        segment_semantic_ambiguity_threshold: "0.6".into(),
        segment_semantic_validation_budget_pct: "100".into(),
        segment_semantic_validation_max_segments: "2".into(),
        segment_semantic_max_adjustment_sec: "1.5".into(),
    }
}

fn read_app_settings(root: &Path) -> Result<AppSettings, String> {
    let env_path = root.join(".env");
    let env_map = read_env_map(&env_path)?;
    let mut settings = default_app_settings();

    if let Some(value) = env_map.get("TIMELINE_AI_PROVIDER") {
        settings.ai_provider = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_PROJECT_NAME") {
        settings.project_name = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_STORY_PROMPT") {
        settings.story_prompt = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_MODE") {
        settings.ai_mode = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_TIMEOUT_SEC") {
        settings.ai_timeout_sec = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_MODEL") {
        settings.ai_model = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_BASE_URL") {
        settings.ai_base_url = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_MODEL_ID") {
        settings.ai_model_id = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_DEVICE") {
        settings.ai_device = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_MAX_SEGMENTS_PER_ASSET") {
        settings.ai_max_segments_per_asset = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_MAX_KEYFRAMES") {
        settings.ai_max_keyframes = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_KEYFRAME_MAX_WIDTH") {
        settings.ai_keyframe_max_width = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_CONCURRENCY") {
        settings.ai_concurrency = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_CACHE") {
        settings.ai_cache_enabled = parse_bool(value, true);
    }
    if let Some(value) = env_map.get("TIMELINE_TRANSCRIPT_PROVIDER") {
        settings.transcript_provider = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_TRANSCRIPT_MODEL_SIZE") {
        settings.transcript_model_size = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_AUDIO_ENABLED") {
        settings.audio_enabled = parse_bool(value, true);
    }
    if let Some(value) = env_map.get("TIMELINE_DEDUPLICATION_ENABLED") {
        settings.deduplication_enabled = parse_bool(value, true);
    }
    if let Some(value) = env_map.get("TIMELINE_DEDUP_THRESHOLD") {
        settings.dedup_threshold = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_CLIP_ENABLED") {
        settings.clip_enabled = parse_bool(value, true);
    }
    if let Some(value) = env_map.get("TIMELINE_AI_CLIP_MIN_SCORE") {
        settings.clip_min_score = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_AI_VLM_BUDGET_PCT") {
        settings.vlm_budget_pct = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_BOUNDARY_REFINEMENT") {
        settings.segment_boundary_refinement_enabled = parse_bool(value, true);
    }
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_LEGACY_FALLBACK") {
        settings.segment_legacy_fallback_enabled = parse_bool(value, true);
    }
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_SEMANTIC_VALIDATION") {
        settings.segment_semantic_validation_enabled = parse_bool(value, true);
    }
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD") {
        settings.segment_semantic_ambiguity_threshold = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT") {
        settings.segment_semantic_validation_budget_pct = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS") {
        settings.segment_semantic_validation_max_segments = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_SEMANTIC_MAX_ADJUSTMENT_SEC") {
        settings.segment_semantic_max_adjustment_sec = value.clone();
    }

    Ok(settings)
}

fn write_app_settings(root: &Path, settings: &AppSettings) -> Result<(), String> {
    let env_path = root.join(".env");
    let mut lines = if env_path.exists() {
        fs::read_to_string(&env_path)
            .map_err(|error| format!("Failed to read {}: {error}", env_path.display()))?
            .lines()
            .map(ToOwned::to_owned)
            .collect::<Vec<_>>()
    } else {
        Vec::new()
    };

    let entries = managed_app_settings_entries(settings);
    let mut seen = HashSet::new();
    let mut rewritten = Vec::new();

    for line in lines.drain(..) {
        let Some((key, _value)) = parse_env_assignment(&line) else {
            rewritten.push(line);
            continue;
        };

        if let Some((_, value)) = entries.iter().find(|(entry_key, _)| entry_key == &key) {
            if seen.insert(key.clone()) {
                rewritten.push(format!("{key}={value}"));
            }
            continue;
        }

        rewritten.push(line);
    }

    if !rewritten.is_empty() && rewritten.last().is_some_and(|line| !line.is_empty()) {
        rewritten.push(String::new());
    }

    for (key, value) in entries {
        if seen.insert(key.clone()) {
            rewritten.push(format!("{key}={value}"));
        }
    }

    let content = format!("{}\n", rewritten.join("\n"));
    fs::write(&env_path, content)
        .map_err(|error| format!("Failed to write {}: {error}", env_path.display()))
}

fn managed_app_settings_entries(settings: &AppSettings) -> Vec<(String, String)> {
    vec![
        ("TIMELINE_AI_PROVIDER".into(), sanitize_single_line(&settings.ai_provider)),
        ("TIMELINE_PROJECT_NAME".into(), sanitize_single_line(&settings.project_name)),
        ("TIMELINE_STORY_PROMPT".into(), sanitize_single_line(&settings.story_prompt)),
        ("TIMELINE_AI_MODE".into(), sanitize_single_line(&settings.ai_mode)),
        ("TIMELINE_AI_TIMEOUT_SEC".into(), sanitize_single_line(&settings.ai_timeout_sec)),
        ("TIMELINE_AI_MODEL".into(), sanitize_single_line(&settings.ai_model)),
        ("TIMELINE_AI_BASE_URL".into(), sanitize_single_line(&settings.ai_base_url)),
        ("TIMELINE_AI_MODEL_ID".into(), sanitize_single_line(&settings.ai_model_id)),
        ("TIMELINE_AI_DEVICE".into(), sanitize_single_line(&settings.ai_device)),
        (
            "TIMELINE_AI_MAX_SEGMENTS_PER_ASSET".into(),
            sanitize_single_line(&settings.ai_max_segments_per_asset),
        ),
        ("TIMELINE_AI_MAX_KEYFRAMES".into(), sanitize_single_line(&settings.ai_max_keyframes)),
        (
            "TIMELINE_AI_KEYFRAME_MAX_WIDTH".into(),
            sanitize_single_line(&settings.ai_keyframe_max_width),
        ),
        ("TIMELINE_AI_CONCURRENCY".into(), sanitize_single_line(&settings.ai_concurrency)),
        (
            "TIMELINE_AI_CACHE".into(),
            if settings.ai_cache_enabled { "true".into() } else { "false".into() },
        ),
        (
            "TIMELINE_TRANSCRIPT_PROVIDER".into(),
            sanitize_single_line(&settings.transcript_provider),
        ),
        (
            "TIMELINE_TRANSCRIPT_MODEL_SIZE".into(),
            sanitize_single_line(&settings.transcript_model_size),
        ),
        (
            "TIMELINE_AI_AUDIO_ENABLED".into(),
            if settings.audio_enabled { "true".into() } else { "false".into() },
        ),
        (
            "TIMELINE_DEDUPLICATION_ENABLED".into(),
            if settings.deduplication_enabled { "true".into() } else { "false".into() },
        ),
        ("TIMELINE_DEDUP_THRESHOLD".into(), sanitize_single_line(&settings.dedup_threshold)),
        (
            "TIMELINE_AI_CLIP_ENABLED".into(),
            if settings.clip_enabled { "true".into() } else { "false".into() },
        ),
        ("TIMELINE_AI_CLIP_MIN_SCORE".into(), sanitize_single_line(&settings.clip_min_score)),
        ("TIMELINE_AI_VLM_BUDGET_PCT".into(), sanitize_single_line(&settings.vlm_budget_pct)),
        (
            "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT".into(),
            if settings.segment_boundary_refinement_enabled { "true".into() } else { "false".into() },
        ),
        (
            "TIMELINE_SEGMENT_LEGACY_FALLBACK".into(),
            if settings.segment_legacy_fallback_enabled { "true".into() } else { "false".into() },
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_VALIDATION".into(),
            if settings.segment_semantic_validation_enabled { "true".into() } else { "false".into() },
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD".into(),
            sanitize_single_line(&settings.segment_semantic_ambiguity_threshold),
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT".into(),
            sanitize_single_line(&settings.segment_semantic_validation_budget_pct),
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS".into(),
            sanitize_single_line(&settings.segment_semantic_validation_max_segments),
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_MAX_ADJUSTMENT_SEC".into(),
            sanitize_single_line(&settings.segment_semantic_max_adjustment_sec),
        ),
    ]
}

fn parse_env_assignment(line: &str) -> Option<(String, String)> {
    let trimmed = line.trim_start();
    if trimmed.is_empty() || trimmed.starts_with('#') {
        return None;
    }
    let (key, value) = trimmed.split_once('=')?;
    Some((key.trim().to_string(), value.trim().to_string()))
}

fn read_env_map(path: &Path) -> Result<std::collections::HashMap<String, String>, String> {
    let mut values = std::collections::HashMap::new();
    if !path.exists() {
        return Ok(values);
    }
    let content = fs::read_to_string(path)
        .map_err(|error| format!("Failed to read {}: {error}", path.display()))?;
    for line in content.lines() {
        if let Some((key, value)) = parse_env_assignment(line) {
            values.insert(key, value);
        }
    }
    Ok(values)
}

fn sanitize_single_line(value: &str) -> String {
    value
        .replace('\n', " ")
        .replace('\r', " ")
        .trim()
        .to_string()
}

fn parse_bool(value: &str, default: bool) -> bool {
    match value.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => true,
        "0" | "false" | "no" | "off" => false,
        _ => default,
    }
}

fn build_env(config: &RuntimeConfig, media_dir: Option<&str>) -> Vec<(String, String)> {
    let mut envs = vec![
        ("TIMELINE_AI_PROVIDER".into(), config.provider.clone()),
        ("TIMELINE_PROJECT_NAME".into(), config.project_name.clone()),
        ("TIMELINE_STORY_PROMPT".into(), config.story_prompt.clone()),
    ];

    if let Some(value) = media_dir.filter(|value| !value.trim().is_empty()) {
        envs.push(("TIMELINE_MEDIA_DIR".into(), value.to_string()));
    }

    match config.provider.as_str() {
        "lmstudio" => {
            envs.push(("TIMELINE_AI_MODEL".into(), config.ai_model.clone()));
            envs.push(("TIMELINE_AI_BASE_URL".into(), config.ai_base_url.clone()));
        }
        "mlx-vlm-local" => {
            envs.push(("TIMELINE_AI_MODEL_ID".into(), config.ai_model_id.clone()));
            envs.push(("TIMELINE_AI_MODEL_REVISION".into(), config.ai_model_revision.clone()));
            envs.push(("TIMELINE_AI_MODEL_CACHE_DIR".into(), config.ai_model_cache_dir.clone()));
            envs.push(("TIMELINE_AI_DEVICE".into(), config.ai_device.clone()));
        }
        _ => {}
    }

    envs
}

struct ScriptOutput {
    status: std::process::ExitStatus,
    stdout: String,
    stderr: String,
}

fn run_script_capture(
    root: &Path,
    script: &str,
    envs: &[(String, String)],
) -> Result<ScriptOutput, String> {
    let mut command = Command::new("bash");
    command.arg(script).current_dir(root);
    for (key, value) in envs {
        command.env(key, value);
    }
    let output = command
        .output()
        .map_err(|error| format!("Failed to run {script}: {error}"))?;
    Ok(ScriptOutput {
        status: output.status,
        stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
    })
}

fn parse_runtime_check_output(output: &str, success: bool) -> RuntimeCheckResult {
    let mut result = RuntimeCheckResult {
        available: success,
        output: output.trim().to_string(),
        ..RuntimeCheckResult::default()
    };
    for line in output.lines() {
        if let Some((key, value)) = line.split_once(':') {
            let value = value.trim().to_string();
            match key.trim() {
                "configured_provider" => result.configured_provider = value,
                "effective_provider" => result.effective_provider = value,
                "model" => result.model = value,
                "revision" => result.revision = value,
                "cache_dir" => result.cache_dir = value,
                "device" => result.device = value,
                "base_url" => result.base_url = value,
                "available" => result.available = value == "yes",
                "detail" => result.detail = value,
                _ => {}
            }
        }
    }
    result
}

fn spawn_process_run(
    root: &Path,
    envs: &[(String, String)],
    state: &Arc<Mutex<ProcessRunState>>,
    app: &AppHandle,
) -> Result<(), String> {
    let mut command = Command::new("bash");
    command
        .arg("scripts/process.sh")
        .current_dir(root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    for (key, value) in envs {
        command.env(key, value);
    }

    let mut child = command
        .spawn()
        .map_err(|error| format!("Failed to start process script: {error}"))?;

    let stdout = child.stdout.take().ok_or_else(|| "Missing process stdout".to_string())?;
    let stderr = child.stderr.take().ok_or_else(|| "Missing process stderr".to_string())?;

    let stdout_state = state.clone();
    let stderr_state = state.clone();
    let stdout_app = app.clone();
    let stderr_app = app.clone();

    let stdout_thread = thread::spawn(move || {
        read_process_stream(stdout, &stdout_state, &stdout_app);
    });
    let stderr_thread = thread::spawn(move || {
        read_process_stream(stderr, &stderr_state, &stderr_app);
    });

    let status = child
        .wait()
        .map_err(|error| format!("Failed to wait for process script: {error}"))?;
    let _ = stdout_thread.join();
    let _ = stderr_thread.join();

    let mut current = state
        .lock()
        .map_err(|_| "Process state lock poisoned".to_string())?;
    current.running = false;
    if status.success() {
        current.status = "completed".into();
        current.output_path = Some(root.join("generated/project.json").to_string_lossy().into_owned());
        current.logs.push("Process completed successfully.".into());
    } else {
        current.status = "failed".into();
        current.error = Some(format!("Process exited with status {status}"));
        current.logs.push(format!("Process exited with status {status}"));
    }
    drop(current);
    emit_process_state(app, state);

    Ok(())
}

fn read_process_stream<R: std::io::Read>(
    reader: R,
    state: &Arc<Mutex<ProcessRunState>>,
    app: &AppHandle,
) {
    let progress_re = Regex::new(
        r"^\[[=\.]+\]\s+(?P<done>\d+)/(?P<total>\d+)\s+assets\s+\|\s+elapsed\s+(?P<elapsed>[^|]+)\s+\|\s+eta\s+(?P<eta>[^|]+)\s+\|\s+(?P<asset>.+)$",
    )
    .expect("invalid regex");

    for line in BufReader::new(reader).lines() {
        let Ok(line) = line else {
            continue;
        };

        if let Ok(mut current) = state.lock() {
            push_log(&mut current.logs, &line);
            if let Some(captures) = progress_re.captures(&line) {
                current.processed = captures
                    .name("done")
                    .and_then(|value| value.as_str().parse::<usize>().ok())
                    .unwrap_or(current.processed);
                current.total = captures
                    .name("total")
                    .and_then(|value| value.as_str().parse::<usize>().ok())
                    .unwrap_or(current.total);
                current.elapsed = captures
                    .name("elapsed")
                    .map(|value| value.as_str().trim().to_string())
                    .unwrap_or_else(|| current.elapsed.clone());
                current.eta = captures
                    .name("eta")
                    .map(|value| value.as_str().trim().to_string())
                    .unwrap_or_else(|| current.eta.clone());
                current.current_asset = captures
                    .name("asset")
                    .map(|value| value.as_str().trim().to_string())
                    .unwrap_or_default();
            } else if line.starts_with("Discovered ") || line.starts_with("Matched ") {
                current.status = "running".into();
            }
        }

        emit_process_state(app, state);
    }
}

fn push_log(logs: &mut Vec<String>, line: &str) {
    logs.push(line.to_string());
    if logs.len() > 200 {
        let overflow = logs.len() - 200;
        logs.drain(0..overflow);
    }
}

fn emit_process_state(app: &AppHandle, state: &Arc<Mutex<ProcessRunState>>) {
    if let Ok(snapshot) = state.lock().map(|value| value.clone()) {
        let _ = app.emit("process-update", snapshot);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(ProcessController::default())
        .invoke_handler(tauri::generate_handler![
            check_runtime_ready,
            clean_generated,
            export_timeline,
            get_process_state,
            inspect_media_folder,
            load_app_settings,
            load_active_project,
            run_setup,
            save_app_settings,
            start_process,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn main() {
    run();
}
