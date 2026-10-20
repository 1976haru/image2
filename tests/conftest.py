import json
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent/'fixtures'
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def isolated_private_store(tmp_path, monkeypatch):
    """Tests never read the user's private masters/anchors or write their catalog."""
    private = tmp_path/'private_store'
    monkeypatch.setenv('CHILI_LAB_PRIVATE_DIR', str(private))
    import story_image_studio.app as app
    monkeypatch.setattr(app, 'CATALOG_PATH', private/'morning_catalog.json')
    import story_image_studio.private_store as store
    monkeypatch.setattr(store, 'APP_ROOT', tmp_path/'no_legacy_examples')
    return private


def core_object_info() -> dict:
    """Real ComfyUI 0.42.1 schemas for our nodes; model lists are public names only."""
    return json.loads((FIXTURES/'object_info_core.json').read_text(encoding='utf-8'))
