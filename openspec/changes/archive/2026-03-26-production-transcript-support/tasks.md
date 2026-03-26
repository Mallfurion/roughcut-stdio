## 1. Analyzer Runtime

- [x] 1.1 Add transcript runtime configuration, including enabled/disabled/auto backend selection and model-size controls where needed.
- [x] 1.2 Implement a production transcript-provider factory and wire it into the process path instead of falling back unconditionally to `NoOpTranscriptProvider`.
- [x] 1.3 Persist transcript runtime status and transcript-related fallback details in generated analysis summary or project state.
- [x] 1.4 Add transcript caching and selective transcript probing so borderline assets can be promoted into full transcription only when a cheap probe finds real text.

## 2. Speech-Aware Analysis

- [x] 2.1 Update scoring and analysis-mode selection so transcript-backed excerpts activate speech mode and strong speech evidence can trigger a speech-aware fallback path when transcript text is missing.
- [x] 2.2 Update deterministic boundary refinement, segment evidence building, and review metadata to use transcript excerpts when present and explicit fallback context when absent.
- [x] 2.3 Add or update analyzer tests for transcript-enabled runs, transcript-unavailable fallback runs, and speech-heavy assets like `IMG_8660`.

## 3. Desktop And Runtime Feedback

- [x] 3.1 Expose transcript support settings in the desktop app and persist them through the Tauri backend into `.env` or process configuration.
- [x] 3.2 Surface transcript runtime availability in desktop process feedback and document how transcript support affects speech analysis.

## 4. Validation

- [x] 4.1 Verify transcript-enabled and transcript-disabled analyzer runs with `npm run process` and compare `generated/project.json` for speech-heavy assets.
- [x] 4.2 Run `python3 -m unittest discover services/analyzer/tests -v` and any relevant desktop checks such as `npm exec tsc -- -p apps/desktop/tsconfig.json --noEmit`.
- [x] 4.3 Update [README.md](/Users/florin/Projects/personal/roughcut-stdio/README.md), [docs/analyzer-pipeline.md](/Users/florin/Projects/personal/roughcut-stdio/docs/analyzer-pipeline.md), and [docs/configuration.md](/Users/florin/Projects/personal/roughcut-stdio/docs/configuration.md) to describe transcript support, fallback behavior, and setup requirements.
- [x] 4.4 Benchmark cold and warm transcript-enabled runs and record targeted, probed, skipped, and cached transcript counts in generated process artifacts.
