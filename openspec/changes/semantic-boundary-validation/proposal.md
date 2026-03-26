## Why

Deterministic refinement and narrative assembly cover the majority of structural segmentation problems, but some boundaries remain ambiguous even after those stages. The analyzer needs a bounded semantic validation step that can ask the configured VLM about incomplete actions or thoughts without turning the whole pipeline into an always-on model-dependent system.

## What Changes

- Add optional semantic boundary validation for ambiguous segments only.
- Add runtime limits so only a bounded subset of segments receives extra semantic validation.
- Persist semantic boundary outcomes, skipped-validation reasons, and fallback behavior in generated project state.
- Keep deterministic refined output unchanged when semantic validation is disabled, unavailable, or over budget.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `context-complete-segmentation`: Ambiguous segments can receive optional semantic boundary validation after deterministic refinement.
- `ai-segment-understanding`: AI analysis supports a separate, bounded boundary-validation pass with deterministic fallback.

## Impact

- Analyzer AI integration in `services/analyzer/app/ai.py` and `analysis.py`
- Generated project schema in `generated/project.json`
- Runtime reporting and config handling
- Tests for budget caps, fallback behavior, and semantic result parsing
