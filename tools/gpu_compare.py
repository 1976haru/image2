"""One-frame real GPU comparison on the local ComfyUI (A/B engine benchmark).

Writes ONLY to a gitignored local folder: native PNG + run.json with engine,
models, seed, prompt hash, reference hashes, how many reference images actually
entered the graph, wall time and peak VRAM sampled from nvidia-smi. It does not
score likeness: identity/quality verdicts are a human review step.

  python tools/gpu_compare.py --story-json PRIVATE.json --scene 1 --engine flux2 \
      --male m.png --female f.png --seed 1234 --out local_runs/compare
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from story_image_studio import comfy  # noqa: E402
from story_image_studio.private_store import load_scene_anchors  # noqa: E402
from story_image_studio.story import build_scenes, load_json, reference_edit_prompt  # noqa: E402


class VramSampler(threading.Thread):
    """Peak *whole-GPU* memory.used while the job runs (includes other apps)."""

    def __init__(self, interval=0.5):
        super().__init__(daemon=True)
        self.interval, self.peak_mib, self.samples, self._halt = interval, 0, 0, threading.Event()

    def run(self):
        while not self._halt.is_set():
            try:
                out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                     capture_output=True, text=True, timeout=5).stdout
                self.peak_mib = max(self.peak_mib, int(out.split()[0]))
                self.samples += 1
            except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
                pass
            self._halt.wait(self.interval)

    def stop(self):
        self._halt.set()
        self.join(timeout=5)


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--story-json', required=True)
    ap.add_argument('--scene', type=int, default=1, choices=[1, 2, 3, 4])
    ap.add_argument('--channel', default='남녀', choices=['남자', '여자', '남녀'])
    ap.add_argument('--engine', required=True, choices=list(comfy.ENGINES))
    ap.add_argument('--checkpoint', default='animagine-xl-3.1.safetensors')
    ap.add_argument('--male', default='')
    ap.add_argument('--female', default='')
    ap.add_argument('--character-hint', default='')
    ap.add_argument('--seed', type=int, default=20261020)
    ap.add_argument('--width', type=int, default=1024)
    ap.add_argument('--height', type=int, default=576)
    ap.add_argument('--quality', default='high', choices=['fast', 'standard', 'high'])
    ap.add_argument('--flux2-steps', type=int, default=4)
    ap.add_argument('--label', default='')
    ap.add_argument('--address', default='http://127.0.0.1:8188')
    ap.add_argument('--out', default=str(ROOT/'local_runs'/'compare'))
    args = ap.parse_args(argv)

    data = load_json(args.story_json)
    anchors = load_scene_anchors((data.get('meta') or {}).get('episodeNo'))
    scene = build_scenes(data, args.channel, 'anime', args.character_hint, scene_anchors=anchors)[args.scene-1]
    refs = {k: v for k, v in (('male', args.male), ('female', args.female)) if v}
    if refs and args.engine == 'flux2':
        mode, prompt = 'flux2_multiref', reference_edit_prompt(scene, list(refs))
    elif refs:
        raise SystemExit('레퍼런스는 flux2(또는 IPAdapter 노드가 로드된 sdxl)에서만 실제 입력됩니다. 텍스트 대체 금지.')
    else:
        mode, prompt = 'story', scene.prompt

    client = comfy.ComfyClient(args.address)
    version = client.ping()
    sampler = VramSampler()
    sampler.start()
    started = time.monotonic()
    error = ''
    try:
        png = client.render(prompt, width=args.width, height=args.height, engine=args.engine,
                            checkpoint=args.checkpoint if args.engine == 'sdxl' else '',
                            references=refs, reference_mode=mode, negative=scene.negative,
                            quality=args.quality, seed=args.seed, flux2_steps=args.flux2_steps,
                            prefix='CHILI_COMPARE', callback=lambda m: print(' ', m, flush=True))
    except comfy.ComfyError as exc:
        png, error = None, str(exc)
    finally:
        seconds = round(time.monotonic()-started, 1)
        sampler.stop()

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f'{stamp}_{args.engine}_{mode}' + (f'_{args.label}' if args.label else '')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    evidence = dict(getattr(client, 'last_render', None) or {})
    graph = evidence.pop('graph', {})
    record = {
        'status': 'LOCAL_GPU_PASS' if png else 'FAILED', 'error': error,
        'visual_verdict': 'PENDING_USER_REVIEW', 'comfyui': version, 'address': args.address,
        'engine': args.engine, 'reference_mode': mode, 'scene': args.scene, 'seed': args.seed,
        'native_size': [args.width, args.height], 'seconds_wall': seconds,
        'peak_gpu_memory_used_mib': sampler.peak_mib, 'vram_samples': sampler.samples,
        'models': {n['class_type']: {k: v for k, v in n['inputs'].items() if k.endswith('_name')}
                   for n in graph.values() if n['class_type'].endswith('Loader') or n['class_type'] == 'CheckpointLoaderSimple'},
        'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'reference_sha256': {k: sha256(v) for k, v in refs.items()},
        **evidence,
    }
    if png:
        with Image.open(io.BytesIO(png)) as im:
            record['decoded_size'] = list(im.size)
        (out/f'{name}.png').write_bytes(png)
    (out/f'{name}.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    (out/f'{name}.prompt.txt').write_text(prompt, encoding='utf-8')
    print(json.dumps({k: record[k] for k in ('status', 'engine', 'reference_mode', 'seconds_wall',
                                               'peak_gpu_memory_used_mib', 'error')}, ensure_ascii=False))
    print(out/f'{name}.png' if png else 'no image')
    return 0 if png else 1


if __name__ == '__main__':
    raise SystemExit(main())
