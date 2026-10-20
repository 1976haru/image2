# Acceptance gates — don't ship images because a script returned PASS

## Test environments
A. static Python & unit tests (no GPU); B. ComfyUI simulated API test (no GPU);
C. **Windows RTX 3060 12GB real image test** (MANDATORY before declaring image quality improved).
Report separate pass/fail/N/A for each gate. A/B passing never implies C.

## Story anime (4 scenes)
- Parse all 15 songs and roles; plan setup/rising action/emotional peak/ending with clear timestamp/action/setting differences.
- Reference A (male) and B (female) distinct photos, choose scene reference separately. In identity mode both refs are uploaded to the current ComfyUI server, NOT text substituted.
- Subject count: intended man + woman where scene requires; no unexpected extra protagonists. If montage/triptych/contact sheet: FAIL.
- Anime quality: crisp eyes, clean lines, natural limbs/hands, coherent clothing/colors, no garbled signage, no unintended split-screen.
- Compare 4 outputs side by side: same male/female defining features across different camera angles; if not, flag NEEDS_REVIEW and regenerate frame (do not score it as ID preserved).
- No plot contradictions: avoid a kiss/holding hands/confession when source episode says relationship is not yet established.
- Exactly 4 independent 16:9 JPG files named no001.jpg..no004.jpg, ZIP with same four only.
- Reject duplicates using perceptual image hash as a **warning** plus visible review, not as definitive semantic similarity.

## Morning (Mio / Haru)
- Six fields mandatory and kept byte-identical, NO only selects previously saved input; unknown NO cannot invent a title.
- Four genuinely different 16:9 photoreal cafe scenes A/B/C/D; must include drink/table/morning daylight.
- NO humans, faces, silhouettes, anime styling, pseudo-lettering, branded signs.
- Mio airy editorial elegance vs Haru intimate small Japan cafe style kept distinct.
- Typography: EXACT TWO strings: channel name and unmodified DISPLAY_TEXT; same light serif family, weight, hierarchy, consistency across 4 scenes; overlay after inference.
- At 320x180 downsample title readable; check overlaps/edge safety.
- Exactly 4 JPGs named noNNN_A.jpg..noNNN_D.jpg, four-image ZIP only.

## Pipeline / privacy
- If custom node unavailable in selected /object_info: fail-before-queue with direct cause and remediation. Installed manager entry ≠ registered node.
- Distinguish detected node / downloaded weights / checkpoint from actual successful GPU render.
- If references requested but unavailable: require explicit user choice to proceed without them; no silent fallback.
- Store local evidence under user-selected D: location, not in GitHub public repository.
- First approved image required before bulk generation. Retry rejected scenes individually.
- Final manifest outside ZIP records hash of images and actual generation dimensions (native vs upscaled), model/checkpoint and seed.

## Tests Claude Code must write
- Simulate two servers: one has checkpoint but no IPAdapter, other has IPAdapter; choose only verified correct instance or fail.
- Simulate installed plugin metadata but /object_info absent; no queuing.
- Simulate missing CLIP Vision and IPAdapter weights; validation fails with explicit path.
- Simulate partial 3/4 images, wrong dimensions, duplicate filenames, corrupt JPG; do not package ZIP.
- Simulate unknown NO and overly long DISPLAY_TEXT; fail with useful Korean error.
- Scan all output JPGs and archive for exactly 4 unique images.
- On-device screenshot-based QA and reference-vs-output side-by-side test need human signoff.

## Delivery status definitions
- CODED: code exists
- UNIT_PASS: tests pass with mocks
- LOCAL_GPU_PASS: one real Windows GPU job succeeded
- VISUAL_APPROVED: reference and output image quality accepted by user
Don't use '100% done' until LOCAL_GPU_PASS and VISUAL_APPROVED are both true.