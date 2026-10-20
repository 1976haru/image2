"""Smoke/integration test for v1.3 without contacting a real GPU server."""
import io
from pathlib import Path
import time
import zipfile
import tkinter as tk
from PIL import Image
import pytest


def fake_png():
    im=Image.new('RGB',(1024,576),(235,237,231))
    s=io.BytesIO();im.save(s,'PNG');return s.getvalue()


class FakeComfy:
    engines=[]
    def __init__(self,url):self.url=url
    def list_checkpoints(self):return []
    def render(self,*args,**kwargs):
        FakeComfy.engines.append(kwargs.get('engine'))
        return fake_png()


def test_gui_haru_four_files(monkeypatch,tmp_path,isolated_private_store):
    import story_image_studio.app as app
    masters=isolated_private_store/'masters';masters.mkdir(parents=True)
    fixture=Path(__file__).resolve().parent/'fixtures'/'HARU_SYNTHETIC_MASTER.txt'
    (masters/'HARU_MASTER.txt').write_text(fixture.read_text(encoding='utf-8'),encoding='utf-8')
    FakeComfy.engines=[]
    monkeypatch.setattr(app.Studio,'_startup_detect',lambda self:None)
    monkeypatch.setattr(app,'ComfyClient',FakeComfy)
    monkeypatch.setattr(app.messagebox,'askyesno',lambda *a,**k: True)
    try:ui=app.Studio()
    except tk.TclError as exc:pytest.skip('No GUI DISPLAY: '+str(exc))
    try:
        ui.withdraw();ui.update()
        assert ui.morning_brand.get()=='HARU'
        assert ui.morning_no.get()=='904'
        ui.engine.set('sdxl')  # story engine choice must NOT leak into photoreal Mio/Haru
        ui.upscaler.set('Lanczos')
        ui.morning_size.set('YouTube 1280x720')
        ui.output_dir.set(str(tmp_path))
        ui._morning_generate()
        deadline=time.time()+12
        while ui.working and time.time()<deadline:
            ui.update();time.sleep(.04)
        ui.update()
        assert not ui.working,ui.morning_status.get()
        assert ui.morning_status.get().startswith('4/4 완료'),ui.morning_status.get()
        assert len(ui.last_final_paths)==4
        folder=ui.last_output_dir
        assert folder.is_dir()
        assert sorted(p.name for p in folder.glob('*.jpg'))==[f'no904_{ch}.jpg' for ch in 'ABCD']
        with zipfile.ZipFile(folder/'HARU_no904_ABCD.zip') as z:
            assert sorted(z.namelist())==[f'no904_{ch}.jpg' for ch in 'ABCD']
        assert FakeComfy.engines==['zimage']*4
        assert list(folder.glob('*SOURCE*'))==[]
    finally:
        ui.destroy()
