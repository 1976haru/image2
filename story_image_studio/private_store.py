"""Locations for the user's private creative inputs, OUTSIDE the public repo.

Scene anchors per episode and the Mio/Haru master TXT files are the user's own
creative material: the app reads them from here, tests use synthetic fixtures.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

MASTER_FILES = {'MIO': 'MIO_MASTER.txt', 'HARU': 'HARU_MASTER.txt'}
# V1.3.1 shipped masters inside examples/; still honoured locally (gitignored).
LEGACY_MASTER_FILES = {'MIO': 'MIO_MASTER_V11_2.txt', 'HARU': 'HARU_LITTLE_CAFE_MASTER_V2_0_FINAL_6LINE.txt'}
APP_ROOT = Path(__file__).resolve().parent.parent


def private_root() -> Path:
    override = os.environ.get('CHILI_LAB_PRIVATE_DIR')
    if override:
        return Path(override)
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData'/'Local')))/'CHILI_LAB'/'StoryImageStudio'
    return Path.home()/'.config'/'chili_lab'/'story_image_studio'


def load_scene_anchors(episode_no) -> list[str] | None:
    no = re.sub(r'[^0-9A-Za-z_-]', '', str(episode_no or ''))
    if not no:
        return None
    path = private_root()/'scene_anchors'/f'EP{no}.json'
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    anchors = data.get('sceneAnchors') if isinstance(data, dict) else data
    if not isinstance(anchors, list) or len(anchors) != 4:
        raise ValueError(f'{path}: sceneAnchors는 문장 4개여야 합니다.')
    return [str(a) for a in anchors]


def find_master(brand: str) -> Path | None:
    candidates = [private_root()/'masters'/MASTER_FILES[brand],
                  APP_ROOT/'examples'/LEGACY_MASTER_FILES[brand]]
    return next((p for p in candidates if p.is_file()), None)
