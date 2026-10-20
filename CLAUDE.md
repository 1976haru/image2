# CLAUDE.md — image2 principal engineering instructions

Read README.md, docs/ARCHITECTURE.md, docs/QUALITY_GATES.md, docs/PHASE1.md BEFORE changing code.

## Primary outcome
Ship **four genuinely different, approved images** for either a 15-song Korean/Japanese romance playlist or a Japanese photo-real morning cafe brand. The sole success metric is quality and consistency of outputs on the user's **RTX 3060 12GB / 32GB RAM**, not the count of features or passing mocked API tests.

## Process / safety
- Source-of-truth GitHub: https://github.com/1976haru/image2
- Windows working directory target: D:\ai\image2. Existing models under D:\ai\Comfy Desktop\ComfyUI-Models are shared; NEVER move/delete/re-download without approval.
- All generation must use localhost ComfyUI HTTP. No paid remote image APIs. Never send private refs or lyrics to remote services.
- Public repo: DO NOT commit copyrighted song JSON, user reference images, huge .safetensors/.ckpt/.pt/.onnx models, rendered images, logs, personal names/paths, keys, image metadata with user secrets. Synthetic fixtures only.
- Keep main unchanged during development. Branch + tests + draft PR. No force push, reset, rebase, clean, or merges without user approval.
- Consult upstream maintained GitHub source before adding custom nodes. Pin extensions and model compatibility in a machine-readable manifest, never install uncertain forks.
- Do not assume presence of IPAdapter nodes because manager UI says "installed". /object_info MUST confirm node registration in *the same instance/port*.

## Mandatory design
- Modes separate: STORY_ANIME with people, MIO_MORNING no people, HARU_LITTLE_CAFE no people.
- Engine separation: STORY first A/B-benchmark (A) Animagine XL SDXL+verified IPAdapter against (B) **FLUX.2 Klein 4B FP8 multi-reference edit**, Apache-2.0. Existing IPAdapter plugin is NOT loaded in observed servers. Verify RTX 3060 12GB viability, compatible ComfyUI version, memory/offload and anime similarity before installs/claims. Morning remains Z-Image Turbo photoreal; never apply SDXL anime to morning photos.
- Reference modes: STORY_TEXT (no image-conditioned identity, explicit acknowledgment), SDXL_IPADAPTER (requires nodes/assets), IMG2IMG (keeps composition; NOT identity guarantee).
- Never silently revert to unconditioned image generation if references requested; fail closed with actionable prerequisite report.
- Male and female must have separate images; optionally use face crops + regional masks. Identity reference ≠ scene/mood reference.
- Four-scene plot: distinct foreground/action/camera/background, no montage, no collage, no triptych, no unintended extra protagonists.
- Morning fields EXACT: NO, PLAYLIST_CODE P01-P08, 状況, MAIN_TEXT, DISPLAY_TEXT, EMOTIONAL_LINE. Exactly two visible strings on exported image: brand name and exact DISPLAY_TEXT. No visible Japanese mood line.
- Typography must be rendered AFTER image generation via explicit approved local font; don't trust AI to render text. Never bundle proprietary fonts.
- Export mode defaults to exactly four JPEGs in output directory and four JPEGs in ZIP. Source images held under hidden/review workspace if needed, not alongside deliverables.
- Persist presets/workflow IDs/seed/model fingerprint. A failed render must be retryable without discarding good images.
- Use 1024x576 base before benchmarking higher memory use. Real-ESRGAN upscaling is not native 4K.

## Required pipeline quality checks
- Preflight ComfyUI URL, node types, checkpoints, IPAdapter weights, CLIP Vision, upscaler; report exact machine-specific problem.
- Before any four-frame batch, produce and visually approve 1 frame per engine/reference mode.
- Verify image count=4, unique image hashes/frames, file extension JPEG, decode, 16:9, title text placement, duplicate checks; warning when semantic image checks require human review.
- No arbitrary 'good quality' scores; use user-reviewed before/after reference collage, record measured results.

## Preferred implementation
Keep existing Python architecture during initial import. Refactor large GUI module into UI/services incrementally. Avoid rewriting to new framework until quality pipeline passes GPU acceptance. Build minimal ComfyUI API JSON workflows, validate against /object_info before queue; use /prompt, /history, /view (or websocket); capture prompt ID and error information.
 
## Engineering gates / reporting
- pytest, Python compileall, Windows CI.
- Reproduce failure in test before fix, all preexisting tests pass.
- No success claims based on mocked GPUs. Mark as UNVERIFIED until on-device comparison accepted.
- Every user report includes: verified work, estimated whole-project completion, what remains in priority order, ONE immediate next action.
- Codex reviews the PR after Claude Code commits, particularly GPU assumptions, privacy, workflow schemas, test gaps.

## Latest evidence-based model decision
FLUX.2 [klein] 4B (https://github.com/black-forest-labs/flux2) combines commercial Apache-2.0 licensing and multiple reference images in one editing workflow, so evaluate on the user's dual anime references before further IPAdapter repairs. The official full-BF16 card quotes ~13GB VRAM; use model-specific FP8/offload if supported, with user's approval and in a NEW/isolated ComfyUI instance. Do not call it proven until real 3060 success.
Qwen-Image-Edit-2511 may achieve stronger edit consistency, but memory footprint and quantization requirements make it a secondary research option. Never claim it is free of local GPU limits.

## Phase 1 priorities
P0 restore code to image2 privately sanitized; P0 real preflight; P0 reference input effectiveness; P0 four-final-file export; P1 compare independent story frame images; P1 morning accurate 2-string photo previews; P2 performance and UX.