"""Private creative inputs stay outside the repo; modes stay separated."""
import json
import subprocess
from pathlib import Path

import pytest

from story_image_studio.private_store import load_scene_anchors, find_master
from story_image_studio.story import build_scenes, load_json
from story_image_studio.comfy import PHOTO_ENGINES

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests'/'fixtures'/'synthetic_15songs.json'


def test_private_anchors_override_json_and_generic(isolated_private_store):
    folder = isolated_private_store/'scene_anchors'
    folder.mkdir(parents=True)
    private = [f'private anchor {i}' for i in range(4)]
    (folder/'EP901.json').write_text(json.dumps({'sceneAnchors': private}), encoding='utf-8')
    anchors = load_scene_anchors('901')
    scenes = build_scenes(load_json(FIXTURE), scene_anchors=anchors)
    assert [s.prompt.count(a) for s, a in zip(scenes, private)] == [1, 1, 1, 1]


def test_missing_private_anchor_returns_none():
    assert load_scene_anchors('123') is None
    assert load_scene_anchors('') is None


def test_bad_anchor_count_rejected():
    data = load_json(FIXTURE)
    data['meta']['sceneAnchors'] = ['only one']
    with pytest.raises(ValueError, match='4개'):
        build_scenes(data)


def test_generic_anchors_without_episode_data():
    data = load_json(FIXTURE)
    del data['meta']['sceneAnchors']
    scenes = build_scenes(data)
    assert 'Opening scene' in scenes[0].prompt


def test_masters_come_only_from_private_store(isolated_private_store):
    assert find_master('MIO') is None
    (isolated_private_store/'masters').mkdir(parents=True)
    (isolated_private_store/'masters'/'MIO_MASTER.txt').write_text('x', encoding='utf-8')
    assert find_master('MIO').name == 'MIO_MASTER.txt'


def test_source_has_no_episode_specific_story_text():
    code = '\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'story_image_studio').glob('*.py'))
    for leaked in ('가을의 그녀와 만남', 'roasted chestnuts', 'ep009_anchors'):
        assert leaked not in code


def test_morning_photo_engine_is_only_zimage():
    assert PHOTO_ENGINES == ('zimage',)


def test_tracked_files_have_no_images_weights_or_private_examples():
    try:
        out = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip('git unavailable')
    banned = ('.png', '.jpg', '.jpeg', '.webp', '.safetensors', '.ckpt', '.pt', '.zip')
    tracked = out.splitlines()
    assert not [f for f in tracked if f.lower().endswith(banned)]
    assert not [f for f in tracked if f.startswith(('examples/', 'local_runs/', 'user_data/'))]
