## 1. Provider Integration

- [ ] 1.1 Add `moondream-local` to AI provider configuration and status inspection
- [ ] 1.2 Implement a direct Moondream analyzer that plugs into the existing shortlisted-segment refinement path
- [ ] 1.3 Preserve deterministic fallback and LM Studio compatibility

## 2. Model Bootstrap And Setup

- [ ] 2.1 Add a bootstrap script that downloads and validates the configured Moondream model locally
- [ ] 2.2 Wire model bootstrap into `npm run setup`
- [ ] 2.3 Add env controls for model ID, revision, cache path, device, and skip-download behavior

## 3. AI Health Check

- [ ] 3.1 Extend `npm run check:ai` to validate `moondream-local`
- [ ] 3.2 Report effective backend, model identity, cache path, device, and readiness detail
- [ ] 3.3 Fail `check:ai` when `moondream-local` is configured but not ready

## 4. Runtime Reporting

- [ ] 4.1 Record `moondream-local` backend details in `generated/process.log`
- [ ] 4.2 Include live/cached/fallback counters and effective backend info in process summaries
- [ ] 4.3 Surface enough information to distinguish direct-model use from deterministic fallback

## 5. Validation

- [ ] 5.1 Add analyzer tests for provider selection, direct-model fallback, and runtime accounting
- [ ] 5.2 Add setup/check script coverage where practical
- [ ] 5.3 Verify `python3 -m unittest discover services/analyzer/tests -v`
- [ ] 5.4 Verify `npm run process` still produces valid generated outputs
- [ ] 5.5 Verify `npm run build:web`

## 6. Documentation

- [ ] 6.1 Update README for the new provider and setup flow
- [ ] 6.2 Update `.env.example` with `moondream-local` configuration
- [ ] 6.3 Keep LM Studio documented as an optional alternative backend
