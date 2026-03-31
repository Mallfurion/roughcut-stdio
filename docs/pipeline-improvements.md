# Pipeline Improvements

This note captures the runtime ideas from the latest cold-run analysis that are not being tracked as standalone OpenSpec proposals.

OpenSpec proposals:

- `runtime-mlx-batching` tracks MLX per-asset batching.
- `cross-asset-vlm-dedup` tracks global cross-asset dedup before VLM targeting.

Remaining improvements, ordered by likely runtime win:

1. Prune harder before VLM. The latest cold run sent 371 of 409 candidates to live VLM, so the cheap stages are not shrinking the expensive workload enough. The highest-value follow-up knobs are a tighter shortlist, a real global VLM budget, and stricter CLIP gating.
2. Stop building contact sheets unless the active provider truly needs them. Evidence generation currently pays for keyframe extraction and then another ffmpeg pass to stack those images. If the provider can consume multiple keyframes directly, removing contact-sheet generation should cut substantial subprocess overhead.
3. Reuse one CLIP scorer for the whole run. The current pipeline instantiates CLIP scoring inside the asset loop, which reloads the model repeatedly and throws away the scorer-level embedding cache between assets.
4. Enable Apple Silicon acceleration for CLIP if the dependency stack is stable on `mps`. The current scorer chooses only `cuda` or `cpu`, which likely leaves CLIP on the CPU for this machine.
5. Pipeline per-asset preprocessing with MLX inference. Even if MLX remains single-flight, later assets can still overlap frame sampling, audio screening, transcript decisions, and evidence extraction while the current asset is in model execution.
6. Parallelize deterministic preprocessing across assets for cold runs. The latest cold run rebuilt preprocessing artifacts for all 147 assets, so bounded worker parallelism for frame and audio screening should improve the front half of per-asset analysis.
7. Reduce transcript cold-path cost further. Transcript targeting already bounds work well, but targeted assets still block inline inside the main asset loop. Smaller default transcript models, stronger early skips, or background transcript preparation may still produce modest gains.
