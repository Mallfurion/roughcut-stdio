## 1. Prefilter Architecture

- [ ] 1.1 Add domain-model support for prefilter evidence, screening scores, and shortlist status in generated project state
- [ ] 1.2 Add a dedicated prefilter stage in the analyzer pipeline before any LM Studio segment analysis

## 2. Cheap Visual Feature Extraction

- [ ] 2.1 Implement sparse frame or window sampling utilities for each asset
- [ ] 2.2 Implement low-cost visual features such as sharpness, blur, motion, stability, and distinctiveness
- [ ] 2.3 Add optional hooks for lightweight learned scoring without making them hard dependencies

## 3. Candidate Region Construction

- [ ] 3.1 Combine scene boundaries with prefilter scores to build stronger candidate regions
- [ ] 3.2 Collapse or suppress repetitive near-identical runs before shortlist generation
- [ ] 3.3 Select a bounded shortlist per asset for downstream VLM refinement

## 4. AI Stage Rewire

- [ ] 4.1 Change LM Studio analysis so it runs only on prefilter-shortlisted candidate segments
- [ ] 4.2 Preserve deterministic structured analysis for non-shortlisted segments and provider-failure fallback
- [ ] 4.3 Fix cache behavior so repeated VLM analyses are actually written and reused

## 5. Runtime Visibility And Review

- [ ] 5.1 Extend process logging and summaries with prefilter metrics and VLM reduction statistics
- [ ] 5.2 Surface shortlist status and prefilter evidence in generated project state and the review UI where useful
- [ ] 5.3 Update README and docs for the new screening-first pipeline

## 6. Validation

- [ ] 6.1 Add or update analyzer tests for prefilter scoring, shortlist construction, and fallback behavior
- [ ] 6.2 Verify `python3 -m unittest discover services/analyzer/tests -v`
- [ ] 6.3 Verify `npm run process` still produces `generated/project.json` and `generated/process.log`
- [ ] 6.4 Verify `npm run build:web`
