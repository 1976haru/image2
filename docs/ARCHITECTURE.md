# Architecture & vetted upstream libraries (2026-10 research)

## Avoid building an image generator
Keep local ComfyUI as the inference backend. Build a thin Python orchestrator that understands the user assets, scene planning, model paths, exact-output contract and quality gates. Claude Code develops orchestration; it does **not** retrain diffusion models.

Architecture:
  GUI -> Input validation / mode router -> 4-scene storyboard -> engine-specific Comfy workflow builder
       -> local ComfyUI API (preflight /object_info, POST /prompt, GET /history, GET /view)
       -> per-scene draft review and retry -> (optional Real-ESRGAN) -> exact typography overlay
       -> 4 standalone JPEGs + 4-image ZIP + separate JSON manifest.

Modes:
| Mode | Inference engine | Reference | On-image text |
| STORY_ANIME | benchmark FLUX.2 Klein 4B FP8 multi-reference **vs** existing Animagine XL 3.1 SDXL+IPAdapter | separate male/female refs; only claim identity after user compares outputs | none |
| MIO_MORNING | Existing local Z-Image Turbo INT8 | optional visual mood reference only; do not include people | "mio's morning" + exact DISPLAY_TEXT via deterministic overlay |
| HARU_LITTLE_CAFE | Existing Z-Image Turbo INT8 | optional cafe mood reference only | "haru little cafe" + exact DISPLAY_TEXT via deterministic overlay |

The user has SDXL Animagine XL 3.1 + Z-Image Turbo INT8 on D: already. Do NOT redownload weights automatically. Benchmarks first at 1024x576, compare 1280x720 only after VRAM and latency readings; use one-at-a-time queue for 12GB VRAM.

## New quality-first candidate — FLUX.2 [klein] 4B (2026-10-20)

**P0 benchmark BEFORE spending more time debugging IPAdapter:** the official Black Forest Labs FLUX.2 [klein] 4B model supports text-to-image AND *single/multi-reference image editing* in one model, Apache-2.0 license. It may directly address the user's need to keep two anime characters while changing scenes, without the old SDXL IPAdapter plugin. But its anime style and identity consistency on these particular references are NOT verified.

Sources:
- https://github.com/black-forest-labs/flux2 (official model / commercial vs non-commercial license table)
- https://blog.comfy.org/p/flux2-klein-4b-fast-local-image-editing (official ComfyUI workflow)
- https://huggingface.co/black-forest-labs/FLUX.2-klein-4B (official model card)

**RTX 3060 12GB caveat:** BF16 model card quotes about 13GB VRAM, so full BF16 may OOM. BFL's FP8 release is designed for lower memory, but Qwen3 text encoder may require CPU offload into 32GB system RAM. Do NOT promise a working configuration before on-device ComfyUI test, measure generation latency and VRAM. The currently running ComfyUI v0.42.1 may need a separate/upgraded instance to load this 2026 workflow. Upgrade isolated instance only with user approval; do not break already working ComfyUI environment.

Recommended A/B test: keep **A = existing Animagine XL 3.1 + verified IPAdapter** and **B = FLUX.2 Klein 4B FP8 multi-reference edit**. Input same male/female reference + one EP009 scene, run one 1024x576 frame each, compare (a) consistent recognizable traits of BOTH characters, (b) anime rendering and scene story fidelity, (c) physical details, (d) VRAM/time. Choose based on actual outputs, not theoretical model rank. B can be first to test to avoid existing plugin failure.

**Alternative only if smaller model underperforms:** Qwen-Image-Edit-2511 improves multi-person image editing (official ComfyUI post https://blog.comfy.org/p/qwen-image-edit-2511-and-qwen-image), but its full precision/FP8 is too large for 12GB without quantization/offload; GGUF may be slow. Do not make it the first install.



1. ComfyUI official API examples:
   - https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/basic_api_example.py
   - https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/websockets_api_example.py
   - https://github.com/Comfy-Org/docs/blob/main/development/comfyui-server/comms_routes.mdx
   Use validated API graph JSON. /object_info is the actual truth for loaded nodes; models can exist on disk without being registered. A cached manager entry is NOT preflight proof. Persist prompt_id, capture /history errors; avoid blind timeout retries that make extra frames.

2. cubiq/ComfyUI_IPAdapter_plus: https://github.com/cubiq/ComfyUI_IPAdapter_plus
   - Current V1.3.1 references IPAdapterAdvanced and IPAdapterUnifiedLoader but local /object_info shows neither loaded. Solve extension loading/version/import path before use, not by reinstalling models repeatedly.
   - SDXL Plus weight: ip-adapter-plus_sdxl_vit-h.safetensors; CLIP Vision ViT-H file per upstream naming.
   - Reference conditions for separated male/female refs need actual acceptance tests; separate refs alone DO NOT guarantee identity. Role-specific masks/crops are optional experiment, not automatic guarantee.
   - With missing nodes: block identity-preserving mode, keep explicitly labeled text-only mode functional. Never auto-fallback identity to text-only.

3. SDXL checkpoint:
   - https://huggingface.co/cagliostrolab/animagine-xl-3.1
   - Model license described as CreativeML Open RAIL++-M by model card; verify intended commercial use and limitations at distribution time.
   - Compare real samples, not subjective text prompt modifiers only. Guidance, denoise, seed, composition and reference controls impact likeness.

4. Real-ESRGAN release (portable Vulkan binaries):
   - https://github.com/xinntao/Real-ESRGAN/releases
   - Prefer local realesrgan-ncnn-vulkan for optional anime 4x, tile when needed. A plain Lanczos image does NOT gain new detail. Keep originals in review cache; export final resized with truthful "4K UPSCALE" metadata.

5. optional face/detail correction only AFTER working base:
   - https://github.com/comfyorg/comfyui-impact-pack
   - Adds detectors/detailers but increases dependency burden. Do not introduce until GPU benchmark demonstrates quality gain. Its README warns about version-specific compatibility; get node names from server /object_info.

6. exact typography:
   - Python Pillow ImageDraw; Google Fonts Cormorant Garamond installed locally by user if desired (OFL).
   - https://github.com/google/fonts/tree/main/ofl/cormorantgaramond
   - Generate photographic background with forbidden letter/sign prompts, THEN overlay exact brand name and DISPLAY_TEXT; never rely on generated glyphs; no font files committed.

## Required model/runtime manifest
Each sample run logs (outside public git) engine, chosen checkpoint/UNet/CLIP/VAE, ComfyUI host+instance version, exact node class inventory, preset, seed, prompt hash, reference hashes and effective ref mode, native width x height, final dimensions, upscale engine, timing, warnings.
Preflight must report exactly:
- ComfyUI API reachable? correct instance? /object_info node registration?
- Checkpoint / encoder listed by the selected server?
- Reference selected? which files will actually be sent? if missing IPAdapter/weights fail before queue.
- Output target writable? fonts available? enough free disk?
- For Morning: base image generation must use photo-real model; "ANIME" endpoint for this mode is an explicit error.

## Robustness
- One queued frame at a time, with per-frame status and cancellation/stop semantics.
- Idempotent job IDs so history polling is not mistaken for a new queue request.
- Caches previews apart from finals; immutable reviewed outputs. Four-final-file package only.
- Retry a rejected scene using explicit updated prompt / reference weight / seed, not auto "quality" claims.
- Branch/protect main, Windows CI, no private creative assets in public repo.

## Next validation before adding any new dependency
- Render one Animagine XL (no reference) frame: verify anime fidelity/composition.
- Render one Animagine XL with verified IPAdapter for **two people** and compare against specific reference character traits.
- Render one Mio/Haru Z-Image Turbo background + exactly two deterministic text strings.
- Review in native 1024x576, then upscale candidates and assess extra artifacts; 4K should not be a blind automatic default.