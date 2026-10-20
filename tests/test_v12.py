"""Regression cases for previously-reported persistent Comfy Desktop model issues."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from story_image_studio.diagnostics import (load_settings,save_settings,preferred_checkpoint,
    probe_local_models, compare_models, safe_copy_checkpoint,discover_servers,diagnostic_text)
from story_image_studio.comfy import ComfyClient, ComfyError
from test_studio import FakeResp

class FakeSession:
    def __init__(self,available,compact=True):
        self.available=available;self.compact=compact
    def request(self,method,url,timeout=30,**kwargs):
        if '/object_info/CheckpointLoaderSimple' in url:
            if not self.compact: raise ValueError('compact node endpoint unavailable')
            return FakeResp({'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [self.available]}}}})
        if '/object_info' in url:
            return FakeResp({'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [self.available]}}}})
        if '/system_stats' in url:
            return FakeResp({'system':{'comfyui_version':'0.42.1'}})
        raise ValueError('not mocked')

class CheckpointDiscoveryTests(unittest.TestCase):
    def test_server_list_shows_renamed_models_no_false_negative(self):
        actual=['my_custom_name.safetensors','animagineXL.safetensors','sdxl_more.safetensors']
        client=ComfyClient(session=FakeSession(actual))
        self.assertEqual(client.list_checkpoints(),sorted(actual,key=str.casefold))
        self.assertEqual(preferred_checkpoint(['my_custom_name.safetensors']),None)

    def test_supports_noncompact_response(self):
        self.assertEqual(ComfyClient(session=FakeSession(['animeCustom.safetensors'],False)).list_checkpoints(),['animeCustom.safetensors'])

    def test_missing_node_is_not_reported_as_empty_model_dir(self):
        with self.assertRaises(ComfyError):
            ComfyClient._extract_checkpoints({'AnotherNode':{'input':{'required':{}}}})

    def test_server_with_checkpoint_preferred_over_other_running_instance(self):
        class FakeClient:
            def __init__(self,address):self.address=address
            def ping(self,timeout=2):return '연결 성공 · 0.42.1'
            def list_checkpoints(self):
                if self.address.endswith('8081'):return ['MyCustomModel.safetensors']
                return []
        items=discover_servers(['http://127.0.0.1:8188','http://127.0.0.1:8081'],client_factory=FakeClient)
        self.assertEqual(items[0]['address'],'http://127.0.0.1:8081')
        self.assertEqual(len(items),2)

    def test_wrong_server_not_selected_if_expected_checkpoint_exists(self):
        class FakeClient:
            def __init__(self,address):self.address=address
            def ping(self,timeout=2):return '연결 성공 · 0.42.1'
            def list_checkpoints(self):
                return ['randomName.safetensors'] if self.address.endswith('8081') else ['anime.safetensors']
        items=discover_servers(['http://127.0.0.1:8188','http://127.0.0.1:8081'],preferred_name='randomName.safetensors',client_factory=FakeClient)
        self.assertEqual(items[0]['address'],'http://127.0.0.1:8081')

class ModelFolderAndRepairTests(unittest.TestCase):
    def test_find_nested_and_compare_api(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'ComfyUI-Models'
            ck=root/'checkpoints'; ck.mkdir(parents=True)
            (ck/'otherName.safetensors').write_bytes(b'x'*1050)
            found=probe_local_models(root)
            self.assertEqual(len(found),1)
            self.assertTrue(compare_models(['otherName.safetensors'],found)[0]['visible_in_api'])
            self.assertFalse(compare_models([],found)[0]['visible_in_api'])
            self.assertIn('현재 인스턴스',diagnostic_text('http://127.0.0.1:8188',str(root),[],found))

    def test_detect_misplaced_and_user_approved_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'ComfyUI-Models'
            wrong=root/'models'/'checkpoints';wrong.mkdir(parents=True)
            original=wrong/'renamed.safetensors';original.write_bytes(b'y'*2048)
            self.assertEqual(len(probe_local_models(root)),1)
            dest=safe_copy_checkpoint(original,root)
            self.assertEqual(dest,root/'checkpoints'/'renamed.safetensors')
            self.assertEqual(original.stat().st_size,dest.stat().st_size)
            with self.assertRaises(FileExistsError):safe_copy_checkpoint(original,root)

    def test_save_and_restore_connection_and_model(self):
        with tempfile.TemporaryDirectory() as d:
            filename=Path(d)/'user.json'
            save_settings({'address':'http://127.0.0.1:8081','checkpoint':'Other.safetensors','model_root':'D:/ai/models'},filename)
            loaded=load_settings(filename)
            self.assertEqual(loaded['address'],'http://127.0.0.1:8081')
            self.assertEqual(loaded['checkpoint'],'Other.safetensors')
            self.assertEqual(loaded['model_root'],'D:/ai/models')
            filename.write_text('{invalid',encoding='utf-8')
            self.assertEqual(load_settings(filename),{})

if __name__=='__main__':unittest.main()

class GUIModelSelectionTests(unittest.TestCase):
    def test_any_model_is_visible_in_selection_even_if_name_is_custom(self):
        from story_image_studio.app import Studio
        import tkinter as tk
        try:
            app=Studio()
        except tk.TclError as exc:
            self.skipTest('GUI display not available: '+str(exc))
        try:
            app.sdxl_checkpoint.set('')  # clean GUI fixture independent of persisted user settings
            app.event_q.put(('models',['custom_personal_filename.safetensors']))
            app._poll()
            self.assertIn('custom_personal_filename.safetensors',app.model_combo['values'])
            self.assertEqual(app.sdxl_checkpoint.get(),'')
            app.sdxl_checkpoint.set('custom_personal_filename.safetensors')
            app._on_model_selected()
            self.assertEqual(app.sdxl_checkpoint.get(),'custom_personal_filename.safetensors')
        finally:app.destroy()

class RuntimeRecoveryTests(unittest.TestCase):
    def test_run_switches_to_instance_with_requested_checkpoint(self):
        import io
        from queue import Queue
        from threading import Event
        from PIL import Image
        from story_image_studio.app import Studio
        from story_image_studio.story import load_json, build_scenes
        from test_studio import FILE
        class FakeClient:
            def __init__(self,url):self.url=url
            def ping(self):return '연결 성공 · 0.42.1'
            def list_checkpoints(self):
                return ['other.safetensors'] if self.url.endswith('8188') else ['custom_anime.safetensors']
            def render(self,*a,**kw):
                b=io.BytesIO();Image.new('RGB',(1024,576),(100,160,190)).save(b,'PNG');return b.getvalue()
        class FakeStudio:
            def __init__(self):
                self.data=load_json(FILE);self.event_q=Queue();self.stop_event=Event();self.logs=[]
            def _log(self,s):self.logs.append(str(s))
        stub=FakeStudio()
        scenes=build_scenes(stub.data)[:1]
        with tempfile.TemporaryDirectory() as tmp:
            params={'address':'http://127.0.0.1:8188',
                    'candidate_addresses':['http://127.0.0.1:8188','http://127.0.0.1:8081'],
                    'width':1024,'height':576,'references':{},'reference_mode':'story',
                    'denoise':.72,'ref_weight':.55,'engine':'sdxl','checkpoint':'custom_anime.safetensors',
                    'quality':'standard','upscaler':'Lanczos','upscale_model':'realesrgan-x4plus-anime',
                    'exe':'','export_mode':'2K','output_dir':tmp,'style':'anime','channel':'남녀'}
            discovery=[{'address':'http://127.0.0.1:8081','checkpoints':['custom_anime.safetensors']}]
            with patch('story_image_studio.app.ComfyClient',FakeClient),patch('story_image_studio.app.discover_servers',return_value=discovery):
                Studio._worker(stub,scenes,params)
            self.assertTrue(any('자동 복구: ComfyUI 주소 http://127.0.0.1:8081' in l for l in stub.logs))
            self.assertFalse(any(x.startswith('오류:') for x in stub.logs))
            self.assertEqual(len(list(Path(tmp).rglob('no001_SOURCE.png'))),1)
