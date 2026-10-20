"""FLUX.2 Klein multi-reference graph, /object_info schema gate, fail-closed refs."""
from pathlib import Path

import pytest

from conftest import core_object_info
from story_image_studio.comfy import (ComfyClient, ComfyError, flux2_graph, graph, sdxl_graph,
                                      reference_count, FLUX2_MODEL, FLUX2_VAE)
from story_image_studio.workflow_schema import validate_graph, GraphSchemaError, combo_options
from test_studio import FakeComfySession

ROOT = Path(__file__).resolve().parents[1]


def test_flux2_two_refs_follow_official_template_wiring():
    g = flux2_graph('scene', 1024, 576, seed=7, uploaded_refs={'male': 'm.png', 'female': 'f.png'})
    loads = [n['inputs']['image'] for n in g.values() if n['class_type'] == 'LoadImage']
    assert loads == ['m.png', 'f.png']
    refs = [k for k, n in g.items() if n['class_type'] == 'ReferenceLatent']
    assert len(refs) == 4  # each ref on positive AND zeroed negative chain
    guider = g['10']['inputs']
    pos, neg = g[guider['positive'][0]], g[guider['negative'][0]]
    assert pos['class_type'] == neg['class_type'] == 'ReferenceLatent'
    assert g['1']['inputs']['unet_name'] == FLUX2_MODEL and g['3']['inputs']['vae_name'] == FLUX2_VAE
    assert g['2']['inputs']['type'] == 'flux2' and guider['cfg'] == 1.0
    assert reference_count(g) == 2
    validate_graph(g, core_object_info())


def test_flux2_text_only_has_zero_conditioned_refs():
    g = flux2_graph('scene', 1024, 576, seed=1)
    assert reference_count(g) == 0
    assert g['10']['inputs']['positive'] == ['4', 0]
    validate_graph(g, core_object_info())


def test_flux2_rejects_non_16_multiple():
    with pytest.raises(ValueError, match='16'):
        flux2_graph('x', 1024, 568)


def test_existing_engine_graphs_match_real_server_schema():
    info = core_object_info()
    validate_graph(graph('photo', seed=1), info)
    validate_graph(sdxl_graph('anime', 'bad', 'animagine-xl-3.1.safetensors', seed=1), info)


@pytest.mark.parametrize('mutate,expected', [
    (lambda g: g.__setitem__('99', {'class_type': 'IPAdapterAdvanced', 'inputs': {}}), '등록되지 않은 노드'),
    (lambda g: g['8']['inputs'].pop('sampler_name'), '필수 입력 누락'),
    (lambda g: g['1']['inputs'].__setitem__('unet_name', 'missing.safetensors'), '서버 목록에 없는 값'),
    (lambda g: g['12']['inputs'].__setitem__('samples', ['77', 0]), '연결 대상 노드 없음'),
    (lambda g: g['6']['inputs'].__setitem__('bogus', 1), '스키마에 없는 입력'),
])
def test_schema_gate_rejects_bad_graphs(mutate, expected):
    g = flux2_graph('x', 1024, 576, seed=1)
    mutate(g)
    with pytest.raises(GraphSchemaError, match=expected):
        validate_graph(g, core_object_info())


def test_combo_options_both_encodings():
    assert combo_options([['a', 'b']]) == ['a', 'b']
    assert combo_options(['COMBO', {'options': ['euler', 'ddim']}]) == ['euler', 'ddim']
    assert combo_options(['INT', {'default': 1}]) is None


def test_v3_combo_model_list_missing_model_detected():
    client = ComfyClient()
    info = core_object_info()
    info['UNETLoader']['input']['required']['unet_name'] = ['COMBO', {'options': ['other.safetensors']}]
    client._object_info = lambda: info
    with pytest.raises(ComfyError, match=FLUX2_MODEL):
        client.validate_nodes(engine='flux2', reference_mode='flux2_multiref')


def _pic(tmp_path, name, session):
    p = tmp_path/name
    p.write_bytes(session.picture)
    return str(p)


def test_flux2_render_uploads_both_identity_refs_and_records_evidence(tmp_path):
    sess = FakeComfySession()
    client = ComfyClient(session=sess)
    out = client.render('two people at a harbor', engine='flux2', reference_mode='flux2_multiref', seed=3,
                        references={'male': _pic(tmp_path, 'm.png', sess), 'female': _pic(tmp_path, 'f.png', sess),
                                    'mood': _pic(tmp_path, 'mood.png', sess)})
    assert out == sess.picture
    uploads = [c for c in sess.calls if '/upload/image' in c[1]]
    assert len(uploads) == 2  # mood/scene reference is NOT mixed into identity conditioning
    assert client.last_render['conditioned_reference_images'] == 2
    assert sum(1 for n in sess.prompt.values() if n['class_type'] == 'ReferenceLatent') == 4


@pytest.mark.parametrize('refs', [{}, {'mood': 'MOOD'}])
def test_flux2_multiref_fails_closed_without_identity_refs(tmp_path, refs):
    sess = FakeComfySession()
    refs = {k: _pic(tmp_path, 'mood.png', sess) for k in refs}
    with pytest.raises(ComfyError, match='텍스트 전용으로 대체하지 않습니다'):
        ComfyClient(session=sess).render('x', engine='flux2', reference_mode='flux2_multiref', references=refs)
    assert not any('/prompt' in c[1] for c in sess.calls)


def test_flux2_multiref_requires_flux2_engine():
    with pytest.raises(ComfyError, match='FLUX.2'):
        ComfyClient().render('x', engine='sdxl', checkpoint='a.safetensors', reference_mode='flux2_multiref')


def test_schema_error_blocks_queue(tmp_path):
    class NoFlux(FakeComfySession):
        def request(self, method, url, timeout=10, **kwargs):
            if '/object_info' in url:
                from test_studio import FakeResp
                info = core_object_info()
                del info['Flux2Scheduler']
                return FakeResp(info)
            return super().request(method, url, timeout=timeout, **kwargs)
    sess = NoFlux()
    with pytest.raises(ComfyError, match='Flux2Scheduler'):
        ComfyClient(session=sess).render('x', engine='flux2', reference_mode='story')
    assert not any('/prompt' in c[1] for c in sess.calls)


def test_importer_script_has_utf8_bom_for_windows_powershell():
    # Without a BOM, Windows PowerShell 5.1 decodes the Korean .bat names as CP949
    # and silently skips them during import (observed 2026-10-20).
    assert (ROOT/'scripts'/'import_v131.ps1').read_bytes()[:3] == b'\xef\xbb\xbf'


def test_model_manifest_pins_match_code():
    import json
    from story_image_studio import comfy
    manifest = json.loads((ROOT/'config'/'model_manifest.json').read_text(encoding='utf-8'))
    names = {e: {f['name'] for f in v['files']} for e, v in manifest['engines'].items()}
    assert {comfy.FLUX2_MODEL, comfy.FLUX2_VAE, comfy.FLUX2_TEXT_ENCODER} <= names['flux2']
    assert {comfy.MODEL_NAME, comfy.TEXT_ENCODER, comfy.VAE_NAME} <= names['zimage']
    assert all(len(f['sha256']) == 64 for f in manifest['engines']['flux2']['files'] if f['sha256'])
