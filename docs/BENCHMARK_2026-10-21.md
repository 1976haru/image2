# One-frame GPU comparison — 2026-10-21 (RTX 3060 12GB, ComfyUI 0.42.1 @127.0.0.1:8188)

Status legend from docs/QUALITY_GATES.md. Every row below is **LOCAL_GPU_PASS** (a real image was
rendered on the device). **None is VISUAL_APPROVED** — that is the user's decision.
Images, prompts and references stay in the gitignored `local_runs/compare/` on the user's PC.

## Setup
- Story input: the user's private 15-song episode JSON, scene 1 (opening / recognition), channel 남녀.
- References: user's private male + female anime references (~0.23 MP each), used only on localhost.
- Native size 1024×576 for all runs. No upscaling involved in any observation below.
- Tool: `tools/gpu_compare.py` (records engine, models, seed, prompt/reference hashes,
  `conditioned_reference_images` counted from the queued graph, wall time, peak whole-GPU memory).

## Results

| Run | Engine / reference mode | Refs actually in graph | Wall time | Peak whole-GPU mem* |
|---|---|---|---|---|
| A seed 20261020 | Animagine XL 3.1, STORY_TEXT (IPAdapter not registered) | 0 | ~25 s uncached (2.2 s re-run was a ComfyUI cache hit) | 7.7 GB |
| B seed 20261020 | FLUX.2 Klein 4B FP8, 2-image ReferenceLatent | 2 | 28.2 s (incl. first model load) | 11.2 GB |
| B seed 777 | same | 2 | 18.2 s | 10.3 GB |
| B seed 777 + "blank signs" prompt | same | 2 | 20.3 s | 11.7 GB |
| Haru episode A (before fix) | Z-Image Turbo INT8 | 0 | 16.2 s | — |
| Haru episode A (after fix) | Z-Image Turbo INT8 | 0 | 10.2 s | — |

\* `nvidia-smi memory.used` for the whole GPU, sampled every 0.5 s. ComfyUI keeps previously used
models resident (10.4 GB used while idle afterwards), so this is **not** a per-model requirement.
What it does show: FLUX.2 Klein 4B FP8 + Qwen3-4B FP8 + 2 references completed at 1024×576 on
12 GB without OOM.

## Observations (Claude's notes; user verdict pending)
**A — Animagine text-only.** Clean but generic flat anime; does not resemble the reference art
style. Woman faces away (face not verifiable), short tied hair and skirt instead of long wavy hair
and jeans. Recognition / raised-hand beat missing. Expected: no image enters the graph.

**B — FLUX.2 multi-reference.** Both protagonists carry the references' defining traits across two
seeds: man — black hair with bangs, white button shirt, bag strap; woman — long black hair, yellow
cardigan tied over shoulders, bag strap (T-shirt rendered white, reference is grey). Raised-hand
recognition beat present; crowd stays background. Defects:
1. Garbled pseudo-lettering on stall signs/awnings in every B run (systematic).
2. Seed 20261020: raised palms nearly touch — conflicts with the episode's no-contact boundary.
   Seed 777: no contact. → per-frame human review is required, not optional.
3. Adding "signs are blank, no lettering" to the prompt made signage **worse** (cfg 1 distilled
   model has no negative prompt; negations prime the concept). Reverted; comment left in code.

**Mio/Haru — Z-Image.** Before fix the model painted a garbled Japanese mood line onto the photo
(3 visible strings instead of exactly 2). Root cause: raw 状況/EMOTIONAL_LINE/MAIN_TEXT were pasted
into the prompt and the Qwen encoder typesets quoted text. Fixed by passing only English cues
(test reproduces it). After fix: no AI text, the seasonal flower motif kept, exactly the two overlay strings.
Remaining: fixed-position title overlaps the subject; font fell back to Georgia (approved serif
not installed).

## Decision proposal (needs user confirmation)
Use **B (FLUX.2 Klein 4B FP8 multi-reference)** as the STORY engine for the next step; keep A only
as text-only fallback that is explicitly labelled. Do not install IPAdapter until B is rejected.
Next experiment: scene anchors that avoid signage-heavy locations or describe stalls by fabric
canopies, then one approved frame per scene before any 4-frame batch.
