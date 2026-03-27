---
name: docs-update
description: Update this repo's documentation from committed implementation changes. Use when the user wants docs refreshed, README.md aligned with recent code, release docs reviewed, or documentation under docs/ synchronized with what shipped since the last recorded docs baseline.
---

Update repository documentation from committed implementation changes.

**Owned Scope**

- `README.md`
- everything under `docs/`
- `docs/documentation-update-state.json`

Do not edit non-documentation files unless the user explicitly expands scope.

**Baseline File**

- Use `docs/documentation-update-state.json` as the source of truth.
- `last_reviewed_commit` is the implementation commit up to which the docs have been reviewed.
- After completing a docs refresh for the current committed code, update the baseline file to the current `HEAD` commit.

**Workflow**

1. Resolve the baseline commit.

   Read the state file with:

   ```bash
   python3 .codex/skills/docs-update/scripts/docs_sync_state.py show
   ```

   If the file is missing and the task is to install or initialize the workflow, create it at the current `HEAD` and report that no docs diff was applied yet.

   If the file is missing during an actual docs-refresh request, prefer asking for a baseline only when there is no safe default. Otherwise initialize it to the current `HEAD`, tell the user, and stop.

2. Resolve the current implementation target.

   Use committed `HEAD`, not the dirty working tree:

   ```bash
   git rev-parse HEAD
   ```

   If `HEAD` equals `last_reviewed_commit`, there are no new committed implementation changes to document. Report that clearly and stop unless the user explicitly wants a docs-only editorial pass.

3. Inspect what shipped since the baseline.

   Start with:

   ```bash
   git log --oneline <baseline>..HEAD
   git diff --name-only <baseline>..HEAD
   ```

   Then inspect targeted diffs for implementation files that affect product behavior, commands, config, setup, pipeline, architecture, exports, or UI.

4. Inspect current documentation state.

   Read `README.md` and the relevant files under `docs/`. Focus on drift, missing behavior, stale commands, stale configuration defaults, and release notes that no longer match the code.

5. Update docs only where needed.

   Priorities:

   - user-facing workflow and product behavior
   - setup and command accuracy
   - configuration defaults and runtime flags
   - pipeline and architecture behavior
   - output artifacts and review/export behavior

   Keep changes concise and factual. Prefer updating existing docs over creating new docs files.

6. Advance the baseline.

   After the documentation changes are complete, write the current `HEAD` commit into the state file:

   ```bash
   python3 .codex/skills/docs-update/scripts/docs_sync_state.py write --commit "$(git rev-parse HEAD)"
   ```

   The baseline should represent the implementation commit that the docs now cover.

7. Report back.

   Summarize:

   - baseline commit used
   - current `HEAD`
   - which docs were updated
   - any intentional gaps or uncertainties

**Constraints**

- Treat the baseline as a committed-code boundary, not a docs-commit boundary.
- Do not infer "latest implementation" from memory; inspect the actual git range.
- Do not rewrite docs broadly when only a few sections drifted.
- If the code diff is large, prioritize files in `README.md`, `docs/setup.md`, `docs/commands.md`, `docs/configuration.md`, `docs/analyzer-pipeline.md`, and `docs/architecture.md`.

**State File Format**

Expected keys in `docs/documentation-update-state.json`:

- `schema_version`
- `tracked_paths`
- `last_reviewed_commit`
- `updated_at_utc`
- `notes`

Use the helper script instead of hand-editing the state file when possible.
