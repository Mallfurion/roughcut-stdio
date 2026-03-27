use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, Manager, State};

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
    #[serde(rename = "transcriptProvider")]
    transcript_provider: String,
    #[serde(rename = "transcriptModelSize")]
    transcript_model_size: String,
    #[serde(rename = "clipEnabled")]
    clip_enabled: bool,
    #[serde(rename = "projectName")]
    project_name: String,
    #[serde(rename = "storyPrompt")]
    story_prompt: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct RuntimeCheckResult {
    runtime_backend: String,
    configured_provider: String,
    effective_provider: String,
    model: String,
    revision: String,
    cache_dir: String,
    device: String,
    base_url: String,
    available: bool,
    detail: String,
    runtime_ready: bool,
    bundled_runtime_ready: bool,
    model_assets_ready: bool,
    bootstrap_required: bool,
    default_model_assets: Vec<String>,
    provider_model_assets: Vec<String>,
    missing_model_assets: Vec<String>,
    fallback_actions: Vec<String>,
    runtime_reliability_mode: String,
    ai_runtime_mode: String,
    transcript_runtime_mode: String,
    semantic_boundary_runtime_mode: String,
    cache_runtime_mode: String,
    transcript_provider_configured: String,
    transcript_provider_effective: String,
    transcript_model_size: String,
    transcript_enabled: bool,
    transcript_available: bool,
    transcript_status: String,
    transcript_detail: String,
    degraded: bool,
    degraded_reasons: Vec<String>,
    intentional_skip_reasons: Vec<String>,
    runtime_summary: String,
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
    #[serde(rename = "segmentSemanticFloorThreshold")]
    segment_semantic_floor_threshold: String,
    #[serde(rename = "segmentSemanticMinTargets")]
    segment_semantic_min_targets: String,
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

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct BestTakeOverrideStore {
    project_id: String,
    candidate_segment_ids: Vec<String>,
    overrides: HashMap<String, String>,
}

const CLEAR_BEST_TAKE_SENTINEL: &str = "__roughcut_clear_best_take__";

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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RuntimeMode {
    RepoDevelopment,
    PackagedApp,
}

impl RuntimeMode {
    fn as_str(self) -> &'static str {
        match self {
            Self::RepoDevelopment => "repo",
            Self::PackagedApp => "packaged",
        }
    }

    fn is_packaged(self) -> bool {
        matches!(self, Self::PackagedApp)
    }
}

#[derive(Debug, Clone)]
struct DesktopRuntime {
    mode: RuntimeMode,
    workspace_root: Option<PathBuf>,
    resource_dir: Option<PathBuf>,
    config_dir: PathBuf,
    data_dir: PathBuf,
    cache_dir: PathBuf,
    log_dir: PathBuf,
    temp_dir: PathBuf,
}

impl DesktopRuntime {
    fn detect(app: &AppHandle) -> Result<Self, String> {
        if let Some(root) = resolve_workspace_root() {
            return Ok(Self {
                mode: RuntimeMode::RepoDevelopment,
                workspace_root: Some(root.clone()),
                resource_dir: None,
                config_dir: root.clone(),
                data_dir: root.join("generated"),
                cache_dir: root.join(".cache"),
                log_dir: root.join("generated"),
                temp_dir: root.join("generated/tmp"),
            });
        }

        let paths = app.path();
        let config_dir = paths
            .app_config_dir()
            .map_err(|error| format!("Failed to resolve app config dir: {error}"))?;
        let data_dir = paths
            .app_data_dir()
            .map_err(|error| format!("Failed to resolve app data dir: {error}"))?;
        let cache_dir = paths
            .app_cache_dir()
            .map_err(|error| format!("Failed to resolve app cache dir: {error}"))?;
        let log_dir = paths
            .app_log_dir()
            .map_err(|error| format!("Failed to resolve app log dir: {error}"))?;
        let resource_dir = paths.resource_dir().ok();

        Ok(Self {
            mode: RuntimeMode::PackagedApp,
            workspace_root: None,
            resource_dir,
            config_dir,
            data_dir,
            cache_dir: cache_dir.clone(),
            log_dir,
            temp_dir: cache_dir.join("tmp"),
        })
    }

    fn ensure_storage_dirs(&self) -> Result<(), String> {
        let mut dirs = vec![
            self.generated_dir(),
            self.analysis_dir(),
            self.benchmark_root(),
            self.temp_dir.clone(),
        ];
        if self.mode.is_packaged() {
            dirs.extend([
                self.config_dir.clone(),
                self.data_dir.clone(),
                self.cache_dir.clone(),
                self.log_dir.clone(),
                self.model_storage_dir(),
                self.model_manifest_dir(),
            ]);
        }

        for dir in dirs {
            fs::create_dir_all(&dir)
                .map_err(|error| format!("Failed to create {}: {error}", dir.display()))?;
        }
        Ok(())
    }

    fn runtime_backend(&self) -> &'static str {
        self.mode.as_str()
    }

    fn generated_dir(&self) -> PathBuf {
        match &self.workspace_root {
            Some(root) => root.join("generated"),
            None => self.data_dir.join("generated"),
        }
    }

    fn analysis_dir(&self) -> PathBuf {
        self.generated_dir().join("analysis")
    }

    fn generated_project_path(&self) -> PathBuf {
        self.generated_dir().join("project.json")
    }

    fn best_take_override_path(&self) -> PathBuf {
        self.generated_dir().join("best-take-overrides.json")
    }

    fn timeline_export_path(&self) -> PathBuf {
        self.generated_dir().join("timeline.fcpxml")
    }

    fn process_log_path(&self) -> PathBuf {
        self.generated_dir().join("process.log")
    }

    fn process_summary_path(&self) -> PathBuf {
        self.generated_dir().join("process-summary.txt")
    }

    fn process_output_path(&self) -> PathBuf {
        self.generated_dir().join("process-output.txt")
    }

    fn vlm_debug_path(&self) -> PathBuf {
        self.analysis_dir().join("vlm-debug.jsonl")
    }

    fn benchmark_root(&self) -> PathBuf {
        self.generated_dir().join("benchmarks")
    }

    fn model_storage_dir(&self) -> PathBuf {
        match &self.workspace_root {
            Some(root) => root.join("models"),
            None => self.data_dir.join("models"),
        }
    }

    fn default_ai_model_cache_dir(&self) -> PathBuf {
        self.model_storage_dir().join("mlx-vlm")
    }

    fn hf_cache_dir(&self) -> PathBuf {
        self.model_storage_dir().join("hf")
    }

    fn torch_cache_dir(&self) -> PathBuf {
        self.model_storage_dir().join("torch")
    }

    fn model_manifest_dir(&self) -> PathBuf {
        self.model_storage_dir().join("manifests")
    }

    fn clip_manifest_path(&self) -> PathBuf {
        self.model_manifest_dir().join("clip-default.ready")
    }

    fn transcript_manifest_path(&self, model_size: &str) -> PathBuf {
        self.model_manifest_dir().join(format!(
            "transcript-{}.ready",
            sanitize_marker_component(model_size)
        ))
    }

    fn mlx_manifest_path(&self, model_id: &str) -> PathBuf {
        self.model_manifest_dir().join(format!(
            "mlx-vlm-{}.ready",
            sanitize_marker_component(model_id)
        ))
    }

    fn executable_runtime_bin_dir(&self) -> PathBuf {
        match self.mode {
            RuntimeMode::RepoDevelopment => self
                .resolve_relative_path("runtime/bin")
                .unwrap_or_else(|| self.cache_dir.join("runtime/bin")),
            RuntimeMode::PackagedApp => self.cache_dir.join("runtime/bin"),
        }
    }

    fn executable_runtime_lib_dir(&self) -> PathBuf {
        match self.mode {
            RuntimeMode::RepoDevelopment => self
                .resolve_relative_path("runtime/lib")
                .unwrap_or_else(|| self.cache_dir.join("runtime/lib")),
            RuntimeMode::PackagedApp => self.cache_dir.join("runtime/lib"),
        }
    }

    fn settings_env_path(&self) -> PathBuf {
        match &self.workspace_root {
            Some(root) => root.join(".env"),
            None => self.config_dir.join("runtime.env"),
        }
    }

    fn sample_project_path(&self) -> Option<PathBuf> {
        let repo_sample = self
            .workspace_root
            .as_ref()
            .map(|root| root.join("fixtures/sample-project.json"));
        if let Some(path) = repo_sample.filter(|path| path.exists()) {
            return Some(path);
        }

        self.resource_dir
            .as_ref()
            .map(|dir| dir.join("fixtures/sample-project.json"))
            .filter(|path| path.exists())
    }

    fn command_working_dir(&self) -> PathBuf {
        self.workspace_root
            .clone()
            .or_else(|| self.resource_dir.clone())
            .unwrap_or_else(|| self.data_dir.clone())
    }

    fn resolve_relative_path(&self, relative: &str) -> Option<PathBuf> {
        let candidates = [self.workspace_root.as_ref(), self.resource_dir.as_ref()];
        for base in candidates.into_iter().flatten() {
            let path = base.join(relative);
            if path.exists() {
                return Some(path);
            }
        }
        None
    }

    fn resolve_required_path(&self, relative: &str) -> Result<PathBuf, String> {
        self.resolve_relative_path(relative).ok_or_else(|| {
            format!(
                "Runtime backend '{}' is missing required path '{}'",
                self.runtime_backend(),
                relative
            )
        })
    }

    fn resolve_python_binary(&self) -> Option<PathBuf> {
        if let Some(path) = self.resolve_relative_path(".venv/bin/python3") {
            return Some(path);
        }

        if let Some(resource_dir) = &self.resource_dir {
            let bundled = resource_dir.join("runtime/python/bin/python3");
            if bundled.exists() {
                return Some(bundled);
            }
        }

        if matches!(self.mode, RuntimeMode::RepoDevelopment) && host_command_available("python3") {
            return Some(PathBuf::from("python3"));
        }

        None
    }

    fn bundled_runtime_ready(&self) -> bool {
        match self.mode {
            RuntimeMode::RepoDevelopment => {
                self.resolve_relative_path("scripts/check_ai.sh").is_some()
                    && self
                        .resolve_relative_path("services/analyzer/scripts/check_ai_provider.py")
                        .is_some()
                    && self.resolve_python_binary().is_some()
            }
            RuntimeMode::PackagedApp => {
                self.resolve_relative_path("runtime/python/bin/python3")
                    .is_some()
                    && self.resolve_relative_path("runtime/bin/ffmpeg").is_some()
                    && self.resolve_relative_path("runtime/bin/ffprobe").is_some()
                    && self
                        .resolve_relative_path("services/analyzer/scripts/check_ai_provider.py")
                        .is_some()
            }
        }
    }

    fn prepare_packaged_sidecars(&self) -> Result<(), String> {
        if !self.mode.is_packaged() {
            return Ok(());
        }

        let target_dir = self.executable_runtime_bin_dir();
        let target_lib_dir = self.executable_runtime_lib_dir();
        fs::create_dir_all(&target_dir)
            .map_err(|error| format!("Failed to create {}: {error}", target_dir.display()))?;
        fs::create_dir_all(&target_lib_dir)
            .map_err(|error| format!("Failed to create {}: {error}", target_lib_dir.display()))?;

        for binary_name in ["ffmpeg", "ffprobe"] {
            let source = self.resolve_required_path(&format!("runtime/bin/{binary_name}"))?;
            let target = target_dir.join(binary_name);
            let should_copy = match (fs::metadata(&source), fs::metadata(&target)) {
                (Ok(source_meta), Ok(target_meta)) => source_meta.len() != target_meta.len(),
                (Ok(_), Err(_)) => true,
                (Err(error), _) => {
                    return Err(format!(
                        "Failed to inspect bundled sidecar {}: {error}",
                        source.display()
                    ));
                }
            };
            if should_copy {
                fs::copy(&source, &target).map_err(|error| {
                    format!(
                        "Failed to stage bundled sidecar {} -> {}: {error}",
                        source.display(),
                        target.display()
                    )
                })?;
            }
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                fs::set_permissions(&target, fs::Permissions::from_mode(0o755)).map_err(
                    |error| {
                        format!(
                            "Failed to mark bundled sidecar {} executable: {error}",
                            target.display()
                        )
                    },
                )?;
            }
        }

        if let Some(source_lib_dir) = self.resolve_relative_path("runtime/lib") {
            let entries = fs::read_dir(&source_lib_dir).map_err(|error| {
                format!(
                    "Failed to read bundled runtime lib dir {}: {error}",
                    source_lib_dir.display()
                )
            })?;
            for entry in entries {
                let entry = entry.map_err(|error| {
                    format!(
                        "Failed to read bundled runtime lib entry in {}: {error}",
                        source_lib_dir.display()
                    )
                })?;
                let source = entry.path();
                if !source.is_file() {
                    continue;
                }
                let target = target_lib_dir.join(entry.file_name());
                let should_copy = match (fs::metadata(&source), fs::metadata(&target)) {
                    (Ok(source_meta), Ok(target_meta)) => {
                        source_meta.len() != target_meta.len()
                            || source_meta.modified().ok() != target_meta.modified().ok()
                    }
                    (Ok(_), Err(_)) => true,
                    (Err(error), _) => {
                        return Err(format!(
                            "Failed to inspect bundled runtime lib {}: {error}",
                            source.display()
                        ));
                    }
                };
                if should_copy {
                    fs::copy(&source, &target).map_err(|error| {
                        format!(
                            "Failed to stage bundled runtime lib {} -> {}: {error}",
                            source.display(),
                            target.display()
                        )
                    })?;
                }
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    fs::set_permissions(&target, fs::Permissions::from_mode(0o755)).map_err(
                        |error| {
                            format!(
                                "Failed to set bundled runtime lib permissions on {}: {error}",
                                target.display()
                            )
                        },
                    )?;
                }
            }
        }

        Ok(())
    }
}

fn sanitize_marker_component(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return "default".into();
    }
    let sanitized = trimmed
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() {
                ch.to_ascii_lowercase()
            } else {
                '-'
            }
        })
        .collect::<String>();
    let collapsed = sanitized
        .split('-')
        .filter(|segment| !segment.is_empty())
        .collect::<Vec<_>>()
        .join("-");
    if collapsed.is_empty() {
        "default".into()
    } else {
        collapsed
    }
}

fn resolve_workspace_root() -> Option<PathBuf> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let root = manifest_dir.join("../../..").canonicalize().ok()?;
    if root.join("scripts/setup.sh").exists()
        && root.join("scripts/process.sh").exists()
        && root.join("services/analyzer").exists()
    {
        Some(root)
    } else {
        None
    }
}

fn host_command_available(name: &str) -> bool {
    Command::new(name)
        .arg("--version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .output()
        .is_ok()
}

#[tauri::command]
fn load_app_settings(app: AppHandle) -> Result<AppSettings, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    read_app_settings(&runtime)
}

#[tauri::command]
fn save_app_settings(app: AppHandle, settings: AppSettings) -> Result<AppSettings, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    write_app_settings(&runtime, &settings)?;
    read_app_settings(&runtime)
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
fn check_runtime_ready(
    app: AppHandle,
    config: RuntimeConfig,
) -> Result<RuntimeCheckResult, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    perform_runtime_check(&runtime, &config)
}

#[tauri::command]
fn run_setup(app: AppHandle, config: RuntimeConfig) -> Result<RuntimeCheckResult, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    match runtime.mode {
        RuntimeMode::RepoDevelopment => {
            let envs = build_env(&runtime, &config, None);
            let setup_output = run_script_capture(&runtime, "scripts/setup.sh", &envs)?;
            let mut result = perform_runtime_check(&runtime, &config)?;
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
            if !result.output.trim().is_empty() {
                if !combined.is_empty() {
                    combined.push_str("\n---\n");
                }
                combined.push_str(&result.output);
            }
            result.output = combined;
            Ok(result)
        }
        RuntimeMode::PackagedApp => run_packaged_setup(&runtime, &config),
    }
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

    let runtime = DesktopRuntime::detect(&app)?;
    runtime.ensure_storage_dirs()?;
    let settings = read_app_settings(&runtime)?;
    let mut envs = build_process_env(&runtime, &settings);
    let media_dir = resolve_process_media_dir(&runtime, request.media_dir.trim())?;
    envs.push(("TIMELINE_MEDIA_DIR".into(), media_dir.clone()));
    let ai_mode = if request.ai_mode.trim().is_empty() {
        settings.ai_mode.clone()
    } else {
        request.ai_mode.clone()
    };
    envs.push(("TIMELINE_AI_MODE".into(), ai_mode));
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
        let result = spawn_process_run(
            &runtime,
            &settings.project_name,
            &settings.story_prompt,
            &media_dir,
            &envs,
            &process_state,
            &app_handle,
        );
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
fn load_active_project(app: AppHandle) -> Result<LoadedProjectPayload, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    load_active_project_payload(&runtime)
}

#[tauri::command]
fn export_timeline(app: AppHandle, target_path: String) -> Result<String, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    runtime.ensure_storage_dirs()?;
    let generated_path = runtime.generated_project_path();
    if !generated_path.exists() {
        return Err(format!(
            "Missing generated project at {}",
            generated_path.display()
        ));
    }

    let mut args = vec![generated_path.to_string_lossy().into_owned()];
    let override_path = runtime.best_take_override_path();
    if override_path.exists() {
        args.push(override_path.to_string_lossy().into_owned());
    }

    let output = run_python_script_capture(
        &runtime,
        "services/analyzer/scripts/export_fcpxml.py",
        &args,
    )?;
    if !output.status.success() {
        return Err(format!(
            "Export script failed:\n{}\n{}",
            output.stdout, output.stderr
        ));
    }
    let source_path = runtime.timeline_export_path();
    fs::write(&source_path, &output.stdout)
        .map_err(|error| format!("Failed to write {}: {error}", source_path.display()))?;
    let target = PathBuf::from(target_path);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Failed to create export directory: {error}"))?;
    }
    fs::copy(&source_path, &target)
        .map_err(|error| format!("Failed to write export target: {error}"))?;
    Ok(target.to_string_lossy().into_owned())
}

#[tauri::command]
fn select_best_take(
    app: AppHandle,
    asset_id: String,
    segment_id: String,
) -> Result<LoadedProjectPayload, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    update_best_take_override(&runtime, asset_id.trim(), Some(segment_id.trim()))?;
    load_active_project_payload(&runtime)
}

#[tauri::command]
fn clear_best_take_override(
    app: AppHandle,
    asset_id: String,
) -> Result<LoadedProjectPayload, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    update_best_take_override(&runtime, asset_id.trim(), None)?;
    load_active_project_payload(&runtime)
}

#[tauri::command]
fn clear_best_take(app: AppHandle, asset_id: String) -> Result<LoadedProjectPayload, String> {
    let runtime = DesktopRuntime::detect(&app)?;
    update_best_take_override(&runtime, asset_id.trim(), Some(CLEAR_BEST_TAKE_SENTINEL))?;
    load_active_project_payload(&runtime)
}

#[tauri::command]
fn clean_generated(app: AppHandle) -> Result<(), String> {
    let runtime = DesktopRuntime::detect(&app)?;
    let generated_dir = runtime.generated_dir();

    if generated_dir.exists() {
        fs::remove_dir_all(&generated_dir)
            .map_err(|error| format!("Failed to remove generated folder: {error}"))?;
    }

    Ok(())
}

fn load_active_project_payload(runtime: &DesktopRuntime) -> Result<LoadedProjectPayload, String> {
    let generated_path = runtime.generated_project_path();
    let (path, source) = if generated_path.exists() {
        (generated_path, "generated")
    } else if let Some(sample_path) = runtime.sample_project_path() {
        (sample_path, "sample")
    } else {
        return Err("No generated or sample project is available for the current runtime.".into());
    };

    let mut args = vec![path.to_string_lossy().into_owned()];
    let override_path = runtime.best_take_override_path();
    if source == "generated" && override_path.exists() {
        args.push(override_path.to_string_lossy().into_owned());
    }
    let output = run_python_script_capture(
        runtime,
        "services/analyzer/scripts/resolve_project.py",
        &args,
    )?;
    if !output.status.success() {
        return Err(format!(
            "Project resolve failed:\n{}\n{}",
            output.stdout, output.stderr
        ));
    }
    let value: serde_json::Value = serde_json::from_str(&output.stdout)
        .map_err(|error| format!("Failed to parse resolved project JSON: {error}"))?;
    Ok(LoadedProjectPayload {
        project: value,
        source: source.into(),
        file_path: path.to_string_lossy().into_owned(),
    })
}

fn load_project_signature(runtime: &DesktopRuntime) -> Result<BestTakeOverrideStore, String> {
    let path = runtime.generated_project_path();
    if !path.exists() {
        return Err(format!("Missing generated project at {}", path.display()));
    }
    let text = fs::read_to_string(&path)
        .map_err(|error| format!("Failed to read {}: {error}", path.display()))?;
    let value: serde_json::Value = serde_json::from_str(&text)
        .map_err(|error| format!("Failed to parse generated project JSON: {error}"))?;
    let project_id = value
        .get("project")
        .and_then(|project| project.get("id"))
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| "Generated project is missing project.id".to_string())?
        .to_string();
    let candidate_segments = value
        .get("candidate_segments")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| "Generated project is missing candidate_segments".to_string())?;
    let mut candidate_segment_ids = Vec::with_capacity(candidate_segments.len());
    for segment in candidate_segments {
        let segment_id = segment
            .get("id")
            .and_then(serde_json::Value::as_str)
            .ok_or_else(|| "Candidate segment is missing id".to_string())?;
        candidate_segment_ids.push(segment_id.to_string());
    }
    candidate_segment_ids.sort();
    Ok(BestTakeOverrideStore {
        project_id,
        candidate_segment_ids,
        overrides: HashMap::new(),
    })
}

fn update_best_take_override(
    runtime: &DesktopRuntime,
    asset_id: &str,
    segment_id: Option<&str>,
) -> Result<(), String> {
    if asset_id.is_empty() {
        return Err("Missing asset id for best-take override.".into());
    }

    let mut signature = load_project_signature(runtime)?;
    let generated_text = fs::read_to_string(runtime.generated_project_path())
        .map_err(|error| format!("Failed to read generated project JSON: {error}"))?;
    let generated_value: serde_json::Value = serde_json::from_str(&generated_text)
        .map_err(|error| format!("Failed to parse generated project JSON: {error}"))?;
    let candidate_segments = generated_value
        .get("candidate_segments")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| "Generated project is missing candidate_segments".to_string())?;

    let segment_matches_asset = |candidate_segment_id: &str, expected_asset_id: &str| -> bool {
        candidate_segments.iter().any(|segment| {
            segment.get("id").and_then(serde_json::Value::as_str) == Some(candidate_segment_id)
                && segment.get("asset_id").and_then(serde_json::Value::as_str)
                    == Some(expected_asset_id)
        })
    };

    let override_path = runtime.best_take_override_path();
    if override_path.exists() {
        if let Ok(text) = fs::read_to_string(&override_path) {
            if let Ok(existing) = serde_json::from_str::<BestTakeOverrideStore>(&text) {
                if existing.project_id == signature.project_id
                    && existing.candidate_segment_ids == signature.candidate_segment_ids
                {
                    signature.overrides = existing.overrides;
                }
            }
        }
    }

    match segment_id {
        Some(value) => {
            if value.is_empty() {
                return Err("Missing segment id for best-take override.".into());
            }
            if value != CLEAR_BEST_TAKE_SENTINEL && !segment_matches_asset(value, asset_id) {
                return Err("Selected segment does not belong to the requested asset.".into());
            }
            signature
                .overrides
                .insert(asset_id.to_string(), value.to_string());
        }
        None => {
            signature.overrides.remove(asset_id);
        }
    }

    if signature.overrides.is_empty() {
        if override_path.exists() {
            fs::remove_file(&override_path).map_err(|error| {
                format!("Failed to remove {}: {error}", override_path.display())
            })?;
        }
        return Ok(());
    }

    if let Some(parent) = override_path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Failed to create {}: {error}", parent.display()))?;
    }
    let content = serde_json::to_string_pretty(&signature)
        .map_err(|error| format!("Failed to serialize override state: {error}"))?;
    fs::write(&override_path, content)
        .map_err(|error| format!("Failed to write {}: {error}", override_path.display()))
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
        ai_provider: "mlx-vlm-local".into(),
        project_name: "Roughcut Stdio Project".into(),
        story_prompt: "Build a coherent rough cut from the strongest visual and spoken beats."
            .into(),
        ai_mode: "full".into(),
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
        clip_min_score: "0.1".into(),
        vlm_budget_pct: "100".into(),
        segment_boundary_refinement_enabled: true,
        segment_legacy_fallback_enabled: true,
        segment_semantic_validation_enabled: true,
        segment_semantic_ambiguity_threshold: "0.6".into(),
        segment_semantic_floor_threshold: "0.45".into(),
        segment_semantic_min_targets: "1".into(),
        segment_semantic_validation_budget_pct: "100".into(),
        segment_semantic_validation_max_segments: "2".into(),
        segment_semantic_max_adjustment_sec: "1.5".into(),
    }
}

fn read_app_settings(runtime: &DesktopRuntime) -> Result<AppSettings, String> {
    let env_path = runtime.settings_env_path();
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
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_SEMANTIC_FLOOR_THRESHOLD") {
        settings.segment_semantic_floor_threshold = value.clone();
    }
    if let Some(value) = env_map.get("TIMELINE_SEGMENT_SEMANTIC_MIN_TARGETS") {
        settings.segment_semantic_min_targets = value.clone();
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

fn write_app_settings(runtime: &DesktopRuntime, settings: &AppSettings) -> Result<(), String> {
    let env_path = runtime.settings_env_path();
    if let Some(parent) = env_path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Failed to create {}: {error}", parent.display()))?;
    }
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
        (
            "TIMELINE_AI_PROVIDER".into(),
            sanitize_single_line(&settings.ai_provider),
        ),
        (
            "TIMELINE_PROJECT_NAME".into(),
            sanitize_single_line(&settings.project_name),
        ),
        (
            "TIMELINE_STORY_PROMPT".into(),
            sanitize_single_line(&settings.story_prompt),
        ),
        (
            "TIMELINE_AI_MODE".into(),
            sanitize_single_line(&settings.ai_mode),
        ),
        (
            "TIMELINE_AI_TIMEOUT_SEC".into(),
            sanitize_single_line(&settings.ai_timeout_sec),
        ),
        (
            "TIMELINE_AI_MODEL".into(),
            sanitize_single_line(&settings.ai_model),
        ),
        (
            "TIMELINE_AI_BASE_URL".into(),
            sanitize_single_line(&settings.ai_base_url),
        ),
        (
            "TIMELINE_AI_MODEL_ID".into(),
            sanitize_single_line(&settings.ai_model_id),
        ),
        (
            "TIMELINE_AI_DEVICE".into(),
            sanitize_single_line(&settings.ai_device),
        ),
        (
            "TIMELINE_AI_MAX_SEGMENTS_PER_ASSET".into(),
            sanitize_single_line(&settings.ai_max_segments_per_asset),
        ),
        (
            "TIMELINE_AI_MAX_KEYFRAMES".into(),
            sanitize_single_line(&settings.ai_max_keyframes),
        ),
        (
            "TIMELINE_AI_KEYFRAME_MAX_WIDTH".into(),
            sanitize_single_line(&settings.ai_keyframe_max_width),
        ),
        (
            "TIMELINE_AI_CONCURRENCY".into(),
            sanitize_single_line(&settings.ai_concurrency),
        ),
        (
            "TIMELINE_AI_CACHE".into(),
            if settings.ai_cache_enabled {
                "true".into()
            } else {
                "false".into()
            },
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
            if settings.audio_enabled {
                "true".into()
            } else {
                "false".into()
            },
        ),
        (
            "TIMELINE_DEDUPLICATION_ENABLED".into(),
            if settings.deduplication_enabled {
                "true".into()
            } else {
                "false".into()
            },
        ),
        (
            "TIMELINE_DEDUP_THRESHOLD".into(),
            sanitize_single_line(&settings.dedup_threshold),
        ),
        (
            "TIMELINE_AI_CLIP_ENABLED".into(),
            if settings.clip_enabled {
                "true".into()
            } else {
                "false".into()
            },
        ),
        (
            "TIMELINE_AI_CLIP_MIN_SCORE".into(),
            sanitize_single_line(&settings.clip_min_score),
        ),
        (
            "TIMELINE_AI_VLM_BUDGET_PCT".into(),
            sanitize_single_line(&settings.vlm_budget_pct),
        ),
        (
            "TIMELINE_SEGMENT_BOUNDARY_REFINEMENT".into(),
            if settings.segment_boundary_refinement_enabled {
                "true".into()
            } else {
                "false".into()
            },
        ),
        (
            "TIMELINE_SEGMENT_LEGACY_FALLBACK".into(),
            if settings.segment_legacy_fallback_enabled {
                "true".into()
            } else {
                "false".into()
            },
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_VALIDATION".into(),
            if settings.segment_semantic_validation_enabled {
                "true".into()
            } else {
                "false".into()
            },
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD".into(),
            sanitize_single_line(&settings.segment_semantic_ambiguity_threshold),
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_FLOOR_THRESHOLD".into(),
            sanitize_single_line(&settings.segment_semantic_floor_threshold),
        ),
        (
            "TIMELINE_SEGMENT_SEMANTIC_MIN_TARGETS".into(),
            sanitize_single_line(&settings.segment_semantic_min_targets),
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

fn build_env(
    runtime: &DesktopRuntime,
    config: &RuntimeConfig,
    media_dir: Option<&str>,
) -> Vec<(String, String)> {
    let mut envs = vec![
        ("TIMELINE_AI_PROVIDER".into(), config.provider.clone()),
        ("TIMELINE_PROJECT_NAME".into(), config.project_name.clone()),
        ("TIMELINE_STORY_PROMPT".into(), config.story_prompt.clone()),
    ];

    if let Some(value) = media_dir.filter(|value| !value.trim().is_empty()) {
        envs.push(("TIMELINE_MEDIA_DIR".into(), value.to_string()));
    }

    envs.extend(runtime_support_envs(runtime));
    envs.push((
        "TIMELINE_TRANSCRIPT_PROVIDER".into(),
        config.transcript_provider.clone(),
    ));
    envs.push((
        "TIMELINE_TRANSCRIPT_MODEL_SIZE".into(),
        config.transcript_model_size.clone(),
    ));
    envs.push((
        "TIMELINE_AI_CLIP_ENABLED".into(),
        if config.clip_enabled {
            "true".into()
        } else {
            "false".into()
        },
    ));

    match config.provider.as_str() {
        "lmstudio" => {
            envs.push(("TIMELINE_AI_MODEL".into(), config.ai_model.clone()));
            envs.push(("TIMELINE_AI_BASE_URL".into(), config.ai_base_url.clone()));
        }
        "mlx-vlm-local" => {
            envs.push(("TIMELINE_AI_MODEL_ID".into(), config.ai_model_id.clone()));
            envs.push((
                "TIMELINE_AI_MODEL_REVISION".into(),
                config.ai_model_revision.clone(),
            ));
            envs.push((
                "TIMELINE_AI_MODEL_CACHE_DIR".into(),
                if config.ai_model_cache_dir.trim().is_empty() {
                    runtime
                        .default_ai_model_cache_dir()
                        .to_string_lossy()
                        .into_owned()
                } else {
                    config.ai_model_cache_dir.clone()
                },
            ));
            envs.push(("TIMELINE_AI_DEVICE".into(), config.ai_device.clone()));
        }
        _ => {}
    }

    envs
}

fn build_process_env(runtime: &DesktopRuntime, settings: &AppSettings) -> Vec<(String, String)> {
    let mut envs = managed_app_settings_entries(settings);
    envs.extend(runtime_support_envs(runtime));
    if settings.ai_provider == "mlx-vlm-local" {
        envs.push((
            "TIMELINE_AI_MODEL_CACHE_DIR".into(),
            runtime
                .default_ai_model_cache_dir()
                .to_string_lossy()
                .into_owned(),
        ));
    }
    envs
}

fn runtime_support_envs(runtime: &DesktopRuntime) -> Vec<(String, String)> {
    let mut envs = vec![
        (
            "HF_HOME".into(),
            runtime.hf_cache_dir().to_string_lossy().into_owned(),
        ),
        (
            "HF_HUB_CACHE".into(),
            runtime
                .hf_cache_dir()
                .join("hub")
                .to_string_lossy()
                .into_owned(),
        ),
        (
            "TORCH_HOME".into(),
            runtime.torch_cache_dir().to_string_lossy().into_owned(),
        ),
        (
            "XDG_CACHE_HOME".into(),
            runtime.cache_dir.to_string_lossy().into_owned(),
        ),
    ];
    let runtime_bin_dir = runtime.executable_runtime_bin_dir();
    let existing_path = std::env::var("PATH").unwrap_or_default();
    let staged_path = runtime_bin_dir.to_string_lossy();
    let combined = if existing_path.is_empty() {
        staged_path.into_owned()
    } else {
        format!("{staged_path}:{existing_path}")
    };
    envs.push(("PATH".into(), combined));
    envs
}

fn resolve_process_media_dir(
    runtime: &DesktopRuntime,
    requested_media_dir: &str,
) -> Result<String, String> {
    if !requested_media_dir.is_empty() {
        return Ok(requested_media_dir.to_string());
    }

    if let Some(root) = &runtime.workspace_root {
        let default_media_dir = root.join("media");
        if default_media_dir.exists() {
            return Ok(default_media_dir.to_string_lossy().into_owned());
        }
    }

    Err("No media folder selected for processing.".into())
}

fn write_model_manifest(path: &Path) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Failed to create {}: {error}", parent.display()))?;
    }
    fs::write(path, "ready\n")
        .map_err(|error| format!("Failed to write {}: {error}", path.display()))
}

fn remove_model_manifest(path: &Path) -> Result<(), String> {
    if path.exists() {
        fs::remove_file(path).map_err(|error| format!("Failed to remove {}: {error}", path.display()))?;
    }
    Ok(())
}

fn apply_packaged_manifest_updates(
    runtime: &DesktopRuntime,
    config: &RuntimeConfig,
    transcript_ready: bool,
    clip_ready: bool,
    mlx_ready: bool,
) -> Result<(), String> {
    if !runtime.mode.is_packaged() {
        return Ok(());
    }

    if config.transcript_provider != "disabled" {
        let path = runtime.transcript_manifest_path(&config.transcript_model_size);
        if transcript_ready {
            write_model_manifest(&path)?;
        } else {
            remove_model_manifest(&path)?;
        }
    }

    if config.clip_enabled {
        let path = runtime.clip_manifest_path();
        if clip_ready {
            write_model_manifest(&path)?;
        } else {
            remove_model_manifest(&path)?;
        }
    }

    if config.provider == "mlx-vlm-local" {
        let path = runtime.mlx_manifest_path(&config.ai_model_id);
        if mlx_ready {
            write_model_manifest(&path)?;
        } else {
            remove_model_manifest(&path)?;
        }
    }

    Ok(())
}

fn perform_runtime_check(
    runtime: &DesktopRuntime,
    config: &RuntimeConfig,
) -> Result<RuntimeCheckResult, String> {
    runtime.prepare_packaged_sidecars()?;
    let envs = build_env(runtime, config, None);
    let output = match runtime.mode {
        RuntimeMode::RepoDevelopment => run_script_capture(runtime, "scripts/check_ai.sh", &envs)?,
        RuntimeMode::PackagedApp => run_python_script_capture_with_env(
            runtime,
            "services/analyzer/scripts/check_ai_provider.py",
            &[],
            &envs,
        )?,
    };
    let mut result = parse_runtime_check_output(&output.stdout, output.status.success());
    enrich_runtime_check_result(&mut result, runtime, config);
    result.output = output.stdout.trim().to_string();
    Ok(result)
}

fn run_packaged_setup(
    runtime: &DesktopRuntime,
    config: &RuntimeConfig,
) -> Result<RuntimeCheckResult, String> {
    runtime.ensure_storage_dirs()?;
    runtime.prepare_packaged_sidecars()?;
    let mut notes = vec![
        "Packaged runtime setup uses bundled app resources.".to_string(),
        format!("Runtime backend: {}", runtime.runtime_backend()),
    ];

    if !runtime.bundled_runtime_ready() {
        notes.push(
            "Bundled runtime components are missing from the packaged build. Processing cannot start until the app bundle is repaired.".into(),
        );
        let mut result = RuntimeCheckResult {
            runtime_backend: runtime.runtime_backend().into(),
            bundled_runtime_ready: false,
            runtime_ready: false,
            output: notes.join("\n"),
            ..RuntimeCheckResult::default()
        };
        enrich_runtime_check_result(&mut result, runtime, config);
        result.output = notes.join("\n");
        return Ok(result);
    }

    notes.push("Bundled runtime components are available.".into());
    let mut mlx_ready = config.provider != "mlx-vlm-local";
    let transcript_ready;
    let clip_ready;

    if config.provider == "mlx-vlm-local" {
        let envs = build_env(runtime, config, None);
        let bootstrap = run_python_script_capture_with_env(
            runtime,
            "services/analyzer/scripts/bootstrap_mlx_vlm.py",
            &[],
            &envs,
        )?;
        if !bootstrap.stdout.trim().is_empty() {
            notes.push(bootstrap.stdout.trim().to_string());
        }
        if !bootstrap.stderr.trim().is_empty() {
            notes.push(bootstrap.stderr.trim().to_string());
        }
        mlx_ready = bootstrap.status.success();
    }

    if config.transcript_provider == "disabled" {
        transcript_ready = true;
        notes.push("Transcript runtime is disabled; skipping transcript bootstrap.".into());
    } else {
        let transcript_bootstrap = run_python_script_capture_with_env(
            runtime,
            "services/analyzer/scripts/bootstrap_transcript.py",
            &[],
            &build_env(runtime, config, None),
        )?;
        if !transcript_bootstrap.stdout.trim().is_empty() {
            notes.push(transcript_bootstrap.stdout.trim().to_string());
        }
        if !transcript_bootstrap.stderr.trim().is_empty() {
            notes.push(transcript_bootstrap.stderr.trim().to_string());
        }
        transcript_ready = transcript_bootstrap.status.success();
    }

    if config.clip_enabled {
        let clip_bootstrap = run_python_script_capture_with_env(
            runtime,
            "services/analyzer/scripts/bootstrap_clip.py",
            &[],
            &build_env(runtime, config, None),
        )?;
        if !clip_bootstrap.stdout.trim().is_empty() {
            notes.push(clip_bootstrap.stdout.trim().to_string());
        }
        if !clip_bootstrap.stderr.trim().is_empty() {
            notes.push(clip_bootstrap.stderr.trim().to_string());
        }
        clip_ready = clip_bootstrap.status.success();
    } else {
        clip_ready = true;
        notes.push("CLIP scoring is disabled; skipping CLIP bootstrap.".into());
    }

    apply_packaged_manifest_updates(runtime, config, transcript_ready, clip_ready, mlx_ready)?;

    let mut result = perform_runtime_check(runtime, config)?;
    if !result.output.trim().is_empty() {
        notes.push(result.output.trim().to_string());
    }
    result.output = notes.join("\n---\n");
    Ok(result)
}

struct ScriptOutput {
    status: std::process::ExitStatus,
    stdout: String,
    stderr: String,
}

fn run_script_capture(
    runtime: &DesktopRuntime,
    script: &str,
    envs: &[(String, String)],
) -> Result<ScriptOutput, String> {
    let script_path = runtime.resolve_required_path(script)?;
    let mut command = Command::new("bash");
    command
        .arg(&script_path)
        .current_dir(runtime.command_working_dir());
    for (key, value) in envs {
        command.env(key, value);
    }
    let output = command
        .output()
        .map_err(|error| format!("Failed to run {}: {error}", script_path.display()))?;
    Ok(ScriptOutput {
        status: output.status,
        stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
    })
}

fn run_python_script_capture(
    runtime: &DesktopRuntime,
    script: &str,
    args: &[String],
) -> Result<ScriptOutput, String> {
    run_python_script_capture_with_env(runtime, script, args, &[])
}

fn run_python_script_capture_with_env(
    runtime: &DesktopRuntime,
    script: &str,
    args: &[String],
    envs: &[(String, String)],
) -> Result<ScriptOutput, String> {
    runtime.prepare_packaged_sidecars()?;
    let python = runtime.resolve_python_binary().ok_or_else(|| {
        format!(
            "Runtime backend '{}' does not have an available Python interpreter.",
            runtime.runtime_backend()
        )
    })?;
    let script_path = runtime.resolve_required_path(script)?;

    let mut command = Command::new(&python);
    command
        .arg(&script_path)
        .args(args)
        .current_dir(runtime.command_working_dir());
    for (key, value) in envs {
        command.env(key, value);
    }
    let output = command.output().map_err(|error| {
        format!(
            "Failed to run {} {}: {error}",
            python.display(),
            script_path.display()
        )
    })?;
    Ok(ScriptOutput {
        status: output.status,
        stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
    })
}

fn parse_runtime_check_output(output: &str, success: bool) -> RuntimeCheckResult {
    let mut result = RuntimeCheckResult {
        runtime_backend: "repo".into(),
        available: success,
        runtime_ready: success,
        bundled_runtime_ready: success,
        model_assets_ready: success,
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
                "runtime_ready" => result.runtime_ready = value == "yes",
                "runtime_reliability_mode" => result.runtime_reliability_mode = value,
                "ai_runtime_mode" => result.ai_runtime_mode = value,
                "transcript_runtime_mode" => result.transcript_runtime_mode = value,
                "semantic_boundary_runtime_mode" => result.semantic_boundary_runtime_mode = value,
                "cache_runtime_mode" => result.cache_runtime_mode = value,
                "transcript_provider_configured" => result.transcript_provider_configured = value,
                "transcript_provider_effective" => result.transcript_provider_effective = value,
                "transcript_model_size" => result.transcript_model_size = value,
                "transcript_enabled" => result.transcript_enabled = value == "yes",
                "transcript_available" => result.transcript_available = value == "yes",
                "transcript_status" => result.transcript_status = value,
                "transcript_detail" => result.transcript_detail = value,
                "degraded" => result.degraded = value == "yes",
                "runtime_summary" => result.runtime_summary = value,
                "degraded_reasons" => result.degraded_reasons = parse_runtime_list_field(&value),
                "intentional_skip_reasons" => {
                    result.intentional_skip_reasons = parse_runtime_list_field(&value)
                }
                _ => {}
            }
        }
    }
    result
}

fn enrich_runtime_check_result(
    result: &mut RuntimeCheckResult,
    runtime: &DesktopRuntime,
    config: &RuntimeConfig,
) {
    let mut missing_assets = Vec::new();
    let mut default_assets = Vec::new();
    let mut provider_assets = Vec::new();
    let mut fallback_actions = Vec::new();

    if config.clip_enabled {
        default_assets.push("CLIP semantic scoring weights".to_string());
        if runtime.mode.is_packaged() && !runtime.clip_manifest_path().exists() {
            missing_assets.push("CLIP semantic scoring weights".to_string());
            fallback_actions.push("disable-clip".to_string());
        }
    }

    if result.transcript_enabled && !result.transcript_available {
        let transcript_asset = format!(
            "Transcript model ({})",
            if result.transcript_model_size.is_empty() {
                "default".to_string()
            } else {
                result.transcript_model_size.clone()
            }
        );
        default_assets.push(transcript_asset.clone());
        missing_assets.push(transcript_asset);
        fallback_actions.push("disable-transcript".to_string());
    } else if config.transcript_provider != "disabled" {
        default_assets.push(format!(
            "Transcript model ({})",
            if config.transcript_model_size.trim().is_empty() {
                "default".to_string()
            } else {
                config.transcript_model_size.clone()
            }
        ));
    }

    if config.provider == "mlx-vlm-local" && !result.available {
        let mlx_asset = format!(
            "MLX-VLM model ({})",
            if config.ai_model_id.trim().is_empty() {
                "default".to_string()
            } else {
                config.ai_model_id.clone()
            }
        );
        provider_assets.push(mlx_asset.clone());
        missing_assets.push(mlx_asset);
        fallback_actions.push("switch-provider-deterministic".to_string());
    } else if config.provider == "mlx-vlm-local" {
        provider_assets.push(format!(
            "MLX-VLM model ({})",
            if config.ai_model_id.trim().is_empty() {
                "default".to_string()
            } else {
                config.ai_model_id.clone()
            }
        ));
    }

    result.runtime_backend = runtime.runtime_backend().into();
    result.bundled_runtime_ready = runtime.bundled_runtime_ready();
    result.default_model_assets = default_assets;
    result.provider_model_assets = provider_assets;
    result.model_assets_ready = missing_assets.is_empty();
    result.bootstrap_required = runtime.mode.is_packaged() && !missing_assets.is_empty();
    result.missing_model_assets = missing_assets;
    result.fallback_actions = fallback_actions;
    if !result.bundled_runtime_ready {
        result.runtime_ready = false;
        if result.detail.is_empty() {
            result.detail = "Bundled runtime components are unavailable.".into();
        }
    }
}

fn parse_runtime_list_field(value: &str) -> Vec<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() || trimmed == "(none)" {
        return Vec::new();
    }
    trimmed
        .split('|')
        .map(|part| part.trim().to_string())
        .filter(|part| !part.is_empty())
        .collect()
}

fn current_utc_timestamp() -> String {
    let output = Command::new("date")
        .arg("-u")
        .arg("+%Y-%m-%dT%H:%M:%SZ")
        .output();
    match output {
        Ok(output) if output.status.success() => {
            String::from_utf8_lossy(&output.stdout).trim().to_string()
        }
        _ => {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default();
            now.as_secs().to_string()
        }
    }
}

fn generate_run_id() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    format!("{}-{:03x}", now.as_secs(), now.subsec_millis())
}

fn append_process_output_line(path: &Path, line: &str) {
    use std::io::Write;

    if let Ok(mut file) = fs::OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{line}");
    }
}

fn spawn_process_run(
    runtime: &DesktopRuntime,
    project_name: &str,
    story_prompt: &str,
    media_dir: &str,
    envs: &[(String, String)],
    state: &Arc<Mutex<ProcessRunState>>,
    app: &AppHandle,
) -> Result<(), String> {
    runtime.ensure_storage_dirs()?;
    runtime.prepare_packaged_sidecars()?;
    let python = runtime.resolve_python_binary().ok_or_else(|| {
        format!(
            "Runtime backend '{}' does not have an available Python interpreter.",
            runtime.runtime_backend()
        )
    })?;
    let scan_script =
        runtime.resolve_required_path("services/analyzer/scripts/scan_media_root.py")?;
    let write_artifacts_script =
        runtime.resolve_required_path("services/analyzer/scripts/write_process_artifacts.py")?;
    let generated_project_path = runtime.generated_project_path();
    let tmp_generated_project_path = runtime.generated_dir().join("project.json.tmp");
    let process_output_path = runtime.process_output_path();
    let process_summary_path = runtime.process_summary_path();
    let process_log_path = runtime.process_log_path();
    let benchmark_root = runtime.benchmark_root();
    let benchmark_history_path = benchmark_root.join("history.jsonl");
    let vlm_debug_path = runtime.vlm_debug_path();
    let run_id = generate_run_id();
    let started_at = current_utc_timestamp();
    let run_started = std::time::Instant::now();

    let _ = fs::remove_file(&generated_project_path);
    let _ = fs::remove_file(&tmp_generated_project_path);
    fs::write(&process_output_path, "").map_err(|error| {
        format!(
            "Failed to initialize {}: {error}",
            process_output_path.display()
        )
    })?;

    let output_file = fs::File::create(&tmp_generated_project_path).map_err(|error| {
        format!(
            "Failed to create temporary project output {}: {error}",
            tmp_generated_project_path.display()
        )
    })?;

    let mut command = Command::new(&python);
    command
        .arg(&scan_script)
        .arg(project_name)
        .arg(media_dir)
        .arg(story_prompt)
        .arg("--artifacts-root")
        .arg(runtime.analysis_dir())
        .current_dir(runtime.command_working_dir())
        .stdout(Stdio::from(output_file))
        .stderr(Stdio::piped());
    for (key, value) in envs {
        command.env(key, value);
    }

    let mut child = command
        .spawn()
        .map_err(|error| format!("Failed to start analyzer process: {error}"))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "Missing process stderr".to_string())?;

    let stderr_state = state.clone();
    let stderr_app = app.clone();
    let capture_path = process_output_path.clone();
    let stderr_thread = thread::spawn(move || {
        read_process_stream(stderr, Some(capture_path), &stderr_state, &stderr_app);
    });

    let status = child
        .wait()
        .map_err(|error| format!("Failed to wait for analyzer process: {error}"))?;
    let _ = stderr_thread.join();

    if !status.success() {
        let _ = fs::remove_file(&tmp_generated_project_path);
        let mut current = state
            .lock()
            .map_err(|_| "Process state lock poisoned".to_string())?;
        current.running = false;
        current.status = "failed".into();
        current.error = Some(format!("Process exited with status {status}"));
        current
            .logs
            .push(format!("Process exited with status {status}"));
        drop(current);
        emit_process_state(app, state);
        return Ok(());
    }

    fs::rename(&tmp_generated_project_path, &generated_project_path).map_err(|error| {
        format!(
            "Failed to finalize generated project {}: {error}",
            generated_project_path.display()
        )
    })?;

    let completed_at = current_utc_timestamp();
    let total_runtime_sec = run_started.elapsed().as_secs_f64();
    let run_benchmark_dir = benchmark_root.join(&run_id);
    let benchmark_path = run_benchmark_dir.join("benchmark.json");
    let run_process_output_path = run_benchmark_dir.join("process-output.txt");
    let args = vec![
        "--project-json".to_string(),
        generated_project_path.to_string_lossy().into_owned(),
        "--process-log".to_string(),
        process_log_path.to_string_lossy().into_owned(),
        "--process-summary".to_string(),
        process_summary_path.to_string_lossy().into_owned(),
        "--benchmark-root".to_string(),
        benchmark_root.to_string_lossy().into_owned(),
        "--process-output".to_string(),
        process_output_path.to_string_lossy().into_owned(),
        "--run-process-output".to_string(),
        run_process_output_path.to_string_lossy().into_owned(),
        "--run-id".to_string(),
        run_id.clone(),
        "--started-at".to_string(),
        started_at,
        "--completed-at".to_string(),
        completed_at,
        "--total-runtime-sec".to_string(),
        format!("{total_runtime_sec:.3}"),
        "--media-dir".to_string(),
        media_dir.to_string(),
        "--media-dir-input".to_string(),
        media_dir.to_string(),
        "--vlm-debug-file".to_string(),
        vlm_debug_path.to_string_lossy().into_owned(),
    ];
    let artifact_output =
        run_python_script_capture(runtime, &write_artifacts_script.to_string_lossy(), &args)?;
    if !artifact_output.status.success() {
        return Err(format!(
            "Failed to write process artifacts:\n{}\n{}",
            artifact_output.stdout, artifact_output.stderr
        ));
    }

    fs::create_dir_all(&run_benchmark_dir)
        .map_err(|error| format!("Failed to create {}: {error}", run_benchmark_dir.display()))?;
    fs::copy(&process_output_path, &run_process_output_path).map_err(|error| {
        format!(
            "Failed to write run process output {}: {error}",
            run_process_output_path.display()
        )
    })?;

    for line in summary_lines_after_process(
        &generated_project_path,
        &process_summary_path,
        &benchmark_path,
        &benchmark_history_path,
        &vlm_debug_path,
    ) {
        append_process_output_line(&process_output_path, &line);
        if let Ok(mut current) = state.lock() {
            push_log(&mut current.logs, &line);
        }
    }

    let mut current = state
        .lock()
        .map_err(|_| "Process state lock poisoned".to_string())?;
    current.running = false;
    current.status = "completed".into();
    current.output_path = Some(generated_project_path.to_string_lossy().into_owned());
    current.logs.push("Process completed successfully.".into());
    drop(current);
    emit_process_state(app, state);

    Ok(())
}

fn summary_lines_after_process(
    generated_project_path: &Path,
    process_summary_path: &Path,
    benchmark_path: &Path,
    benchmark_history_path: &Path,
    vlm_debug_path: &Path,
) -> Vec<String> {
    let mut lines = Vec::new();
    if let Ok(summary) = fs::read_to_string(process_summary_path) {
        for line in summary.lines() {
            lines.push(line.to_string());
        }
    }
    lines.push(format!(
        "Generated timeline project at {}",
        generated_project_path.display()
    ));
    lines.push(format!(
        "Process summary written to {}",
        process_summary_path.display()
    ));
    lines.push(format!(
        "Process benchmark written to {}",
        benchmark_path.display()
    ));
    lines.push(format!(
        "Process benchmark history updated at {}",
        benchmark_history_path.display()
    ));
    if vlm_debug_path.exists() {
        lines.push(format!(
            "VLM debug log written to {}",
            vlm_debug_path.display()
        ));
    }
    lines.push("Next:".into());
    lines.push("  npm run view".into());
    lines.push("  npm run export".into());
    lines
}

fn read_process_stream<R: std::io::Read>(
    reader: R,
    capture_path: Option<PathBuf>,
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

        if let Some(path) = capture_path.as_ref() {
            append_process_output_line(path, &line);
        }

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

#[cfg(test)]
mod tests {
    use super::{parse_runtime_check_output, parse_runtime_list_field};

    #[test]
    fn parse_runtime_list_field_handles_empty_marker() {
        assert!(parse_runtime_list_field("(none)").is_empty());
        assert!(parse_runtime_list_field("").is_empty());
    }

    #[test]
    fn parse_runtime_check_output_captures_reliability_fields() {
        let payload = "\
configured_provider: mlx-vlm-local
effective_provider: mlx-vlm-local
available: yes
detail: MLX runtime ready
runtime_ready: yes
runtime_reliability_mode: degraded
ai_runtime_mode: active
transcript_runtime_mode: partial
semantic_boundary_runtime_mode: degraded
cache_runtime_mode: active
degraded: yes
runtime_summary: AI active, transcript partial, semantic degraded, cache active
degraded_reasons: transcript fallback on 1 asset | semantic boundary fallback on 2 segments
intentional_skip_reasons: transcript targeting kept cost bounded: 3 transcript-target skips
";
        let parsed = parse_runtime_check_output(payload, true);
        assert!(parsed.available);
        assert!(parsed.runtime_ready);
        assert!(parsed.degraded);
        assert_eq!(parsed.runtime_reliability_mode, "degraded");
        assert_eq!(parsed.transcript_runtime_mode, "partial");
        assert_eq!(parsed.degraded_reasons.len(), 2);
        assert_eq!(parsed.intentional_skip_reasons.len(), 1);
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
            clear_best_take,
            clear_best_take_override,
            export_timeline,
            get_process_state,
            inspect_media_folder,
            load_app_settings,
            load_active_project,
            run_setup,
            save_app_settings,
            select_best_take,
            start_process,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn main() {
    run();
}
