# PHASE 1 — Claude Code implementation contract / quality-first migration

## Baseline
Old local app V1.3.1 *exists on the user's PC*. GitHub image2/main has only a README until a reviewed import. This document and other feature branch guidance DO NOT claim that V1.3.1's source was uploaded.
Machine: Windows, RTX 3060 12GB, RAM 32GB, Comfy Desktop instances may live on different ports. Existing models in user's D:\ai\Comfy Desktop\ComfyUI-Models; don't relocate or re-download.

## Stage 0 — safe code migration (highest priority)
1. Clone image2, check out branch feature/quality-first-foundation (or task branch).
2. Locate actual local legacy source directory with story_image_studio/app.py.
3. Use scripts/import_v131.ps1 with explicit -Source and -Target. Import code/tests only; optional private fixtures remain .gitignored.
4. Run Python compileall, pytest; generate synthetic fixture equivalents as needed so tests are self-contained and public-safe.
5. Replace any real episode lyrics, reference photos, master prompt TXT and images before committing. Keep them only in local ignored workspace.
6. Commit on feature branch; open draft PR; no main merge.

## Model strategy update (researched 2026-10-20)
The user priority is reference fidelity + sharp finished art, not maximum number of features. **First evaluate FLUX.2 Klein 4B FP8 multi-reference** instead of continuing an endless IPAdapter repair loop. This newer Apache-2.0 commercial model accepts male and female image references directly in one edit workflow. Official repo: https://github.com/black-forest-labs/flux2 and official ComfyUI edit workflow: https://blog.comfy.org/p/flux2-klein-4b-fast-local-image-editing. Before any new download/install, check compatibility with user's Comfy Desktop and RTX 3060 12GB, install only after approval, isolated from working instance, then compare ONE frame with Animagine baseline. BF16 approximately 13GB VRAM can exceed RTX 3060 12GB; FP8 and CPU encoder offload are candidate options, real performance unverified. If FLUX gives poor anime identity, retain Animagine/IPAdapter as candidate A.

## Stage 1 — eliminate root causes rather than patching screenshots
P0-1. Central engine registry with three workflows:
  - ZIMAGE_PHOTO_TEXT2IMG native/core nodes (MIO/HARU).
  - SDXL_ANIME_TEXT2IMG native/core nodes (smoke test only).
  - SDXL_ANIME_DUAL_REFERENCE requiring loaded IPAdapterAdvanced and IPAdapterUnifiedLoader + ViT-H/SDXL weights. No silent fallback.
P0-2. For each ComfyUI instance, inspect /system_stats and /object_info and selected model names; verify same-instance model availability. Distinguish installed/on disk vs LOADED.
P0-3. Write a preflight report that identifies all missing dependencies before queue. Missing external nodes must NOT block Morning or explicitly text-only smoke tests. No repeated calls to reinstall.
P0-4. Per image UI: preview, prompt/seed/weight, accept/regenerate buttons. Queue sequentially, record prompt ID, memory errors. Don't blindly render 4 every click.
P0-5. Four-final-JPEG-only mode, deterministic filenames, ZIP exactly four, cache drafts OUTSIDE delivery folder.
P0-6. Compare output with user-provided refs, compile failures: unintended 3rd character, different face/outfit, scene changes not matching plot, photo/anime wrong.

## Stage 2 — controlled reference improvement
P1-1. Male/female ref images resized/cropped individually, optional CLIP-aware masks. Research IPAdapterAdvanced optional attn_mask behavior in installed node version, from /object_info schema, never guess inputs.
P1-2. Ref weights calibration and per-scene soft guidance. Save at least 2-3 candidate weights for 1 representative sample. Quality over speed.
P1-3. Identify failure mode: text prompt vs character traits collision, pose variation, model-specific aesthetics, split-screen/collage. Fix each with real sample, not extra generic prompt adjectives.
P1-4. If IPAdapter version fails to load, query ComfyUI current instance logs, dependencies and extension compatible versions before changing any packages. User approval for installs.

## Stage 3 — Mio/Haru channel quality
P1-5. Parse user-provided 6-line per-episode content; separate their brand DNA. Store catalog locally, never create scene from NO alone if no entry.
P1-6. Render four photoreal background candidates A window-light / B curtain-space / C still life / D seasonal local view, no humans, fixed natural morning lighting.
P1-7. Post-process exactly two strings using locally installed approved Cormorant Garamond serif, place title in clear 16:9 negative space, validate size and small preview.
P1-8. 1280x720 JPEG <=2 MB preferred. Optional 2K/4K upscales remain separately labeled not extra final files.

## Stage 4 — evidence and CI
P1-9. Golden unit fixtures (synthetic) for preflight, two-instance disambiguation, interrupted queue, 4-out-only, six-line Japanese parsing, protected local file inputs, images.
P1-10. Windows CI, compileall, pytest, no image downloads, no unauthorized network.
P1-11. Actual RTX 3060 sample 1 frame baseline and 1 frame with true male/female reference; user approval BEFORE any batch of 4.
P1-12. Record before/after outcomes: image previews (private), selected models, original dims, 4 final files, duration, peak VRAM (if measured).

## Important immediate case
Current ComfyUI_IPAdapter_plus Manager says version 2.0.0 "installed", but API node probes on earlier current servers returned both IPAdapterAdvanced and IPAdapterUnifiedLoader NOT LOADED. This is not fixed by just downloading the SDXL weight again. Verify which instance contains it, import traceback, and actual nodes, BEFORE scheduling IPAdapter mode.

## Success requirements
The program must generate quality first, not merely "some images." No release claims until local GPU and user visual approval. If exact face consistency remains weak, display transparent limitation and propose proven alternate nodes with compatibility and VRAM costs rather than repeated unverified updates.