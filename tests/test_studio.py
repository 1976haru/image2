import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from story_image_studio.story import load_json, get_tracks, track_splits, build_scenes, summary
from story_image_studio.comfy import graph, ComfyClient, ComfyError, REQUIRED_CLASSES, MODEL_NAME, TEXT_ENCODER, VAE_NAME
from story_image_studio.output import create_output,zip_outputs,save_manifest,SIZES

FILE = Path(__file__).resolve().parent/'fixtures'/'synthetic_15songs.json'

class TestStories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=load_json(FILE)

    def test_roles(self):
        stats=summary(self.data)
        self.assertEqual(stats['song_count'],15)
        self.assertEqual(stats['vocal_roles'],{'남자':6,'여자':6,'듀엣':3})

    def test_four_scenes_grounded(self):
        scenes=build_scenes(self.data,'남녀','anime','short-haired man and long-haired woman')
        self.assertEqual(len(scenes),4)
        self.assertEqual([s.track_numbers for s in scenes],[[1,2,3],[4,5,6,7],[8,9,10,11,12],[13,14,15]])
        self.assertTrue(all(s.prompt and s.lyric_signals for s in scenes))
        self.assertIn('ferry leaves the gate',scenes[1].prompt)
        self.assertIn('wooden pier',scenes[2].prompt)
        self.assertIn('small wave',scenes[3].prompt)
        self.assertIn('No confession',scenes[0].prompt)
        self.assertIn('short-haired man',scenes[0].prompt)

    def test_channels(self):
        for mode in ('남자','여자','남녀'):
            scenes=build_scenes(self.data,mode,'anime')
            self.assertEqual(len(scenes),4)
        self.assertIn('man is the clear foreground',build_scenes(self.data,'남자')[0].prompt)
        self.assertIn('woman is the clear foreground',build_scenes(self.data,'여자')[0].prompt)
        self.assertIn('equal presence',build_scenes(self.data,'남녀')[0].prompt)

    def test_other_lengths(self):
        for n in [2,4,6,10,20]:
            d={'meta':{},'songs':[{'trackNo':i+1,'lyrics':'We walk on the road','title':'Song'} for i in range(n)]}
            scenes=build_scenes(d)
            self.assertEqual(len(scenes),4)
            self.assertEqual(sum(len(x.track_numbers) for x in scenes),n)

    def test_lyrics_source_not_music_instructions(self):
        scenes=build_scenes(self.data)
        joined=' '.join(' '.join(x.lyric_signals) for x in scenes)
        self.assertNotIn('[RAP POCKET',joined)
        self.assertIn('yellow',joined.lower())

    def test_reject_wrong(self):
        with tempfile.TemporaryDirectory() as d:
            bad=Path(d)/'bad.json'
            bad.write_text('{bad',encoding='utf-8')
            with self.assertRaises(ValueError):load_json(bad)

class TestGraph(unittest.TestCase):
    def test_correct_official_classes(self):
        g=graph('a woman at a street',1024,576,seed=123,prefix='TEST')
        self.assertEqual(g['1']['inputs']['unet_name'],'z_image_turbo_int8_convrot.safetensors')
        self.assertEqual(g['2']['inputs']['type'],'lumina2')
        self.assertEqual(g['8']['inputs']['sampler_name'],'res_multistep')
        self.assertEqual(g['8']['inputs']['steps'],8)
        self.assertEqual(g['8']['inputs']['cfg'],1)
        self.assertEqual(g['8']['inputs']['latent_image'],['6',0])
        self.assertEqual(g['10']['class_type'],'SaveImage')
        self.assertEqual(g['4']['inputs']['text'],'a woman at a street')
        self.assertNotIn('11',g)
        self._validate_links(g)

    def test_img2img(self):
        g=graph('evening',reference_filename='face.png',denoise=0.45)
        self.assertEqual(g['11']['class_type'],'LoadImage')
        self.assertEqual(g['12']['inputs']['crop'],'center')
        self.assertEqual(g['13']['class_type'],'VAEEncode')
        self.assertEqual(g['8']['inputs']['latent_image'],['13',0])
        self.assertEqual(g['8']['inputs']['denoise'],0.45)
        self.assertNotIn('6',g)
        self._validate_links(g)

    def _validate_links(self,g):
        for node in g.values():
            for v in node['inputs'].values():
                if isinstance(v,list):self.assertIn(v[0],g)

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):graph('x',1023,576)

    def test_no_remote(self):
        for url in ('https://localhost:8188','http://example.com:8188','http://192.168.0.3:8188'):
            with self.assertRaises(ComfyError):ComfyClient(url)

class FakeResp:
    def __init__(self,payload=None,raw=b''):
        self.payload=payload
        self.content=raw
        self.text=json.dumps(payload or {})
    def raise_for_status(self): pass
    def json(self):return self.payload

class FakeComfySession:
    def __init__(self):
        self.calls=[]
        image=io.BytesIO()
        Image.new('RGB',(256,256),(32,52,71)).save(image,'PNG')
        self.picture=image.getvalue()
    def request(self,method,url,timeout=10,**kwargs):
        self.calls.append((method,url,kwargs))
        if '/system_stats' in url:return FakeResp({'system':{'comfyui_version':'0.42'}})
        if '/object_info' in url:
            from conftest import core_object_info
            return FakeResp(core_object_info())
        if '/upload/image' in url:return FakeResp({'name':'ref.png'})
        if '/prompt' in url:
            self.prompt=kwargs['json']['prompt']
            return FakeResp({'prompt_id':'job123'})
        if '/history/' in url:
            return FakeResp({'job123':{'status':{'status_str':'success','completed':True},
                  'outputs':{'10':{'images':[{'filename':'test.png','subfolder':'','type':'output'}]}}}})
        if '/view?' in url:return FakeResp(raw=self.picture)
        raise RuntimeError('unexpected endpoint '+url)

class TestMockIntegration(unittest.TestCase):
    def test_mock_full_generation(self):
        sess=FakeComfySession()
        client=ComfyClient('http://127.0.0.1:8188',session=sess)
        self.assertIn('연결 성공',client.ping())
        b=client.render('couple at ginkgo market',None,width=1024,height=576)
        self.assertEqual(b,sess.picture)
        self.assertEqual(sess.prompt['1']['inputs']['unet_name'],MODEL_NAME)

    def test_mock_reference_uploaded(self):
        sess=FakeComfySession()
        client=ComfyClient('http://127.0.0.1:8188',session=sess)
        with tempfile.TemporaryDirectory() as d:
            pic=Path(d)/'ref.png'
            pic.write_bytes(sess.picture)
            b=client.render('sunny market',str(pic),denoise=0.45)
        self.assertEqual(b,sess.picture)
        self.assertEqual(sess.prompt['11']['inputs']['image'],'ref.png')
        self.assertEqual(sess.prompt['8']['inputs']['denoise'],0.45)

class TestSave(unittest.TestCase):
    def test_both_res_both_formats_and_zip(self):
        raw=io.BytesIO()
        Image.new('RGB',(1024,576),(142,184,205)).save(raw,'PNG')
        with tempfile.TemporaryDirectory() as d:
            files=create_output(raw.getvalue(),d,'no01')
            self.assertEqual(len(files),5)
            for file in files:
                self.assertTrue(file.exists())
                with Image.open(file) as image:
                    if '_SOURCE' in file.name:
                        self.assertEqual(image.size,(1024,576))
                    else:
                        self.assertEqual(image.size,SIZES['2K' if '_2K' in file.name else '4K'])
            m=save_manifest(d,{'episode':'009'},[{'a':1}],{'upscaler':'Lanczos'})
            archive=zip_outputs(d)
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(len(z.namelist()),6)
                self.assertIn(m.name,z.namelist())

if __name__=='__main__':unittest.main()
