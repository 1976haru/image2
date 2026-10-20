# AGENTS.md — Codex review checklist

The code owner is Claude Code; Codex independently reviews changes on a feature branch or PR. Do not merge or force push. Read CLAUDE.md and docs/QUALITY_GATES.md.

1. Distinguish completed mocked tests from **actually verified GPU image quality**.
2. Is selected ComfyUI server discovered and validated per-instance? Does /object_info list required custom nodes (not just plugin manager installed status)?
3. Do reference files really enter the diffusion workflow? Is silently falling back to text-only prohibited?
4. Are male and female reference images independent? Are weights/crops/masks verified against installed node schemas?
5. No use of anime checkpoint for Mio/Haru photoreal outputs; no humans in morning scenes.
6. Ensure exact brand labels and unmodified DISPLAY_TEXT, exactly two strings, composited after generation with consistent serif font.
7. Exactly four final JPEGs in folder+ZIP, no duplicate source/format/resolution copies.
8. Fail cleanly on missing weights, node imports, OOM, interrupted queue, corrupt generated file and stale result.
9. No user creative JSON, private reference images, model weights, secrets, output screenshots pushed to public GitHub.
10. Include tests for bugfix and Windows CI; report SHA, changed files, test count, verified vs unverified.
11. Discuss only actual tested quality; generic high-resolution resize is not real detail restoration.
12. Never update main without user approval.