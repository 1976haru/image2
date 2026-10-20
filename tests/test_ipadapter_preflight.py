from pathlib import Path
from story_image_studio.ipadapter_diagnostics import inspect_ipadapter,format_ipadapter_report,ASSET_FILES
from story_image_studio.comfy import ComfyClient,ComfyError
from unittest.mock import Mock
import pytest


def test_missing_nodes_and_assets_report(tmp_path):
    check=inspect_ipadapter({'CheckpointLoaderSimple': {}},tmp_path)
    assert set(check['missing_nodes'])=={'IPAdapterUnifiedLoader','IPAdapterAdvanced'}
    assert not check['shared_root_ready']
    text=format_ipadapter_report(check,'http://127.0.0.1:8188')
    assert 'ComfyUI_IPAdapter_plus' in text and 'clip_vision' in text
    assert '100%' in text


def test_nodes_ready_assets_missing_other_model_path_not_assumed(tmp_path):
    info={node:{} for node in ('IPAdapterUnifiedLoader','IPAdapterAdvanced')}
    check=inspect_ipadapter(info,tmp_path)
    assert check['node_ready'] and not check['shared_root_ready']
    assert '다른 모델 경로' in format_ipadapter_report(check,'http://127.0.0.1:8188')


def test_two_assets_ready_with_nested_path(tmp_path):
    for folder,name in ASSET_FILES.items():
        d=tmp_path/folder/'subfolder';d.mkdir(parents=True)
        (d/name).write_bytes(b'model')
    check=inspect_ipadapter({'IPAdapterUnifiedLoader':{},'IPAdapterAdvanced':{}},tmp_path)
    assert check['node_ready'] and check['shared_root_ready']
    assert '두 모델 파일 확인됨' in format_ipadapter_report(check,'http://127.0.0.1:8188')


def test_existing_node_validation_detailed_missing_message():
    client=ComfyClient()
    client._object_info=Mock(return_value={'CheckpointLoaderSimple': {}, 'CLIPTextEncode': {},
        'EmptyLatentImage': {}, 'KSampler': {}, 'VAEDecode': {}, 'SaveImage': {},'LoadImage':{}})
    with pytest.raises(ComfyError, match='ComfyUI_IPAdapter_plus'):
        client.validate_nodes(engine='sdxl',checkpoint='mock.safetensors',reference_mode='ipadapter')


def test_no_false_missing_node_when_present():
    client=ComfyClient()
    info={node:{} for node in ('CheckpointLoaderSimple','CLIPTextEncode','EmptyLatentImage',
        'KSampler','VAEDecode','SaveImage','LoadImage','IPAdapterUnifiedLoader','IPAdapterAdvanced')}
    client._object_info=Mock(return_value=info)
    assert client.validate_nodes(engine='sdxl',checkpoint='mock.safetensors',reference_mode='ipadapter') is None
