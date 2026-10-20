import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from story_image_studio.comfy import sdxl_graph, graph, ComfyClient, ComfyError, SDXL_CLASSES, IPADAPTER_CLASSES
from story_image_studio.quality import similarity, detect_duplicate
from story_image_studio.output import create_output
from story_image_studio.story import load_json, build_scenes
from test_studio import FakeComfySession, FakeResp, FILE

class TestQuality(unittest.TestCase):
    def to_img(self,color):
        f=io.BytesIO();Image.new('RGB',(320,180),color).save(f,'PNG');return f.getvalue()

    def test_duplicate_detection(self):
        a=self.to_img((140,140,140));b=self.to_img((2,200,15))
        self.assertIsNotNone(detect_duplicate(a,[a]))
        self.assertIsNone(detect_duplicate(b,[a]))

    def test_real_upscale_flag_does_not_fake_ai(self):
        raw=self.to_img((10,70,100))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                create_output(raw,d,'no001',enhancer='Real-ESRGAN',enhancer_path='')

class TestSDXL(unittest.TestCase):
    def test_sdxl_graph_valid(self):
        g=sdxl_graph('anime','bad hands','animeXL.safetensors',seed=77,quality='high')
        self.assertEqual(g['1']['class_type'],'CheckpointLoaderSimple')
        self.assertEqual(g['5']['inputs']['steps'],32)
        self.assertEqual(g['5']['inputs']['negative'],['3',0])
        self.assertEqual(g['5']['inputs']['model'],['1',0])
        self.assertEqual(g['7']['class_type'],'SaveImage')
        self.assertEqual(len(g),7)

    def test_two_separate_references_piped(self):
        g=sdxl_graph('anime','negative','animeXL.safetensors',uploaded_refs={'male':'male.png','female':'female.png'},seed=5)
        self.assertEqual(g['8']['class_type'],'IPAdapterUnifiedLoader')
        self.assertEqual(g['9']['inputs']['image'],'male.png')
        self.assertEqual(g['11']['inputs']['image'],'female.png')
        self.assertEqual(g['10']['inputs']['model'],['8',0])
        self.assertEqual(g['12']['inputs']['model'],['10',0])
        self.assertEqual(g['5']['inputs']['model'],['12',0])
        for n in g.values():
            for val in n['inputs'].values():
                if isinstance(val,list):self.assertIn(val[0],g)

    def test_reject_remote_and_invalid_engines(self):
        with self.assertRaises(ComfyError):
            ComfyClient().render('x',engine='zimage',reference_mode='ipadapter')

    def test_real_app_fake_sdxl_render(self):
        class SDXLSession(FakeComfySession):
            def request(self,method,url,timeout=10,**kwargs):
                if '/object_info' in url:
                    from conftest import core_object_info
                    info=core_object_info()
                    info['CheckpointLoaderSimple']['input']['required']['ckpt_name']=[['animeXL.safetensors']]
                    # Synthetic schemas mirroring cubiq IPAdapter_plus input names (not installed on the GPU box).
                    info['IPAdapterUnifiedLoader']={'input':{'required':{'model':['MODEL'],'preset':[['PLUS (high strength)']]}}}
                    info['IPAdapterAdvanced']={'input':{'required':{n:['X'] for n in ('model','ipadapter','image','weight',
                        'weight_type','combine_embeds','start_at','end_at','embeds_scaling')}}}
                    return FakeResp(info)
                return super().request(method,url,timeout=timeout,**kwargs)
        session=SDXLSession()
        with tempfile.TemporaryDirectory() as d:
            pic=Path(d)/'woman.png'
            pic.write_bytes(session.picture)
            result=ComfyClient(session=session).render('couple walk', engine='sdxl',
                      checkpoint='animeXL.safetensors',reference_mode='ipadapter',
                      references={'female':str(pic)},negative='blurry')
        self.assertEqual(result,session.picture)
        self.assertIn('IPAdapterAdvanced',[node['class_type'] for node in session.prompt.values()])
        self.assertEqual(session.prompt['11']['inputs']['model'] if '11' in session.prompt else session.prompt['5']['inputs']['model'], ['10',0])

    def test_turbo_high_not_overstep(self):
        g=graph('cinematic anime',quality='high')
        self.assertEqual(g['8']['inputs']['steps'],9)

class TestFourDifferentDirections(unittest.TestCase):
    def test_four_distinct_camera_specs(self):
        scenes=build_scenes(load_json(FILE),'남녀','anime')
        expected=['wide establishing shot','medium full shot','low-angle pier','street-level two-shot']
        for scene,t in zip(scenes,expected):
            self.assertIn(t,scene.prompt)
        self.assertTrue(all('No confession' in s.prompt for s in scenes))

if __name__=='__main__':unittest.main()

class TestPortableInstaller(unittest.TestCase):
    def test_can_install_safe_package_offline(self):
        from story_image_studio.tools_install import install_upscaler
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            zipfile_path=d/'release.zip'
            with zipfile.ZipFile(zipfile_path,'w') as z:
                z.writestr('release/realesrgan-ncnn-vulkan.exe',b'fake-executable')
                z.writestr('release/models/realesrgan-x4plus-anime.bin',b'fake-weights')
                z.writestr('release/models/realesrgan-x4plus-anime.param',b'fake-params')
            result=install_upscaler(d/'install',url=zipfile_path.as_uri())
            self.assertTrue(result.exists())
            self.assertEqual(result.name,'realesrgan-ncnn-vulkan.exe')

    def test_archive_path_traversal_rejected(self):
        from story_image_studio.tools_install import install_upscaler
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            bad=d/'bad.zip'
            with zipfile.ZipFile(bad,'w') as z:
                z.writestr('../escape.txt','bad')
            with self.assertRaises(ValueError):
                install_upscaler(d/'installed',url=bad.as_uri())
            self.assertFalse((d/'escape.txt').exists())

class TestFullFourSceneOfflineIntegration(unittest.TestCase):
    def test_four_scene_generator_pipeline_simulated(self):
        from story_image_studio.app import Studio
        from story_image_studio.story import summary
        from queue import Queue
        from threading import Event
        from unittest.mock import patch
        data=load_json(FILE)
        scenes=build_scenes(data,'남녀','anime')
        class MiniStudio:
            def __init__(self):
                self.data=data;self.event_q=Queue();self.stop_event=Event();self.logs=[]
            def _log(self,s):self.logs.append(s)
        class FakeClient:
            def __init__(self, _url):self.count=0
            def ping(self):return 'test server ready'
            def render(self, *args,**kwargs):
                self.count+=1
                b=io.BytesIO()
                Image.new('RGB',(1024,576),(30*self.count,25*self.count,10*self.count)).save(b,'PNG')
                return b.getvalue()
        with tempfile.TemporaryDirectory() as tmp:
            params={'address':'http://127.0.0.1:8188','width':1024,'height':576,'references':{},
                    'reference_mode':'story','denoise':.72,'ref_weight':.55,
                    'engine':'zimage','checkpoint':'','quality':'standard','upscaler':'Lanczos',
                    'upscale_model':'realesrgan-x4plus-anime','exe':'','export_mode':'2K',
                    'output_dir':tmp,'style':'anime','channel':'남녀'}
            stub=MiniStudio()
            with patch('story_image_studio.app.ComfyClient',FakeClient):
                Studio._worker(stub,scenes,params)
            folders=list(Path(tmp).glob('EP901_남녀_*'))
            self.assertEqual(len(folders),1)
            f=folders[0]
            self.assertEqual(len(list(f.glob('no???_SOURCE.png'))),4)
            self.assertEqual(len(list(f.glob('no???_2K.jpg'))),4)
            self.assertTrue((f/'CHILI_LAB_4SCENES.zip').exists())
            manifest=json.loads((f/'_review'/'storyboard_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['settings']['rendered_scenes'],4)
            self.assertFalse(any('오류:' in l for l in stub.logs))
