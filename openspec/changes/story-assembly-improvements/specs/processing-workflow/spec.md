## ADDED Requirements

### Requirement: Process SHALL preserve richer story-assembly diagnostics
When project-level story assembly is active, generated process artifacts SHALL preserve more than the final order alone. They SHALL also preserve the assembly rationale or diagnostics needed to understand why the final sequence was chosen.

#### Scenario: Process completes with enhanced story assembly
- **WHEN** `npm run process` finishes with richer story-assembly logic enabled
- **THEN** `generated/project.json` SHALL preserve sequence-level rationale for the final timeline
- **THEN** the generated diagnostics or summaries SHALL preserve enough assembly context to explain major sequencing tradeoffs
