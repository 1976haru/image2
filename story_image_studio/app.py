"""CHILI LAB Story Image Studio — dependency-light Korean Windows GUI."""
from __future__ import annotations
import json
import os
import queue
import re
import threading
import webbrowser
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from .story import load_json, build_scenes, summary, reference_edit_prompt
from .comfy import ComfyClient, ComfyError, PHOTO_ENGINES
from .ipadapter_diagnostics import inspect_ipadapter, format_ipadapter_report
from .output import create_output, zip_outputs, save_manifest, REVIEW_DIRNAME
from .quality import detect_duplicate
from .final_exports import export_final, archive_exact, find_serif_font, SIZE_MAP
from .private_store import load_scene_anchors, find_master
from .morning import BRANDS, parse_six_lines, master_profile, morning_prompts, load_catalog, save_catalog_episode, import_catalog_json
from .tools_install import install_upscaler, RELEASE_URL
from .diagnostics import (load_settings, save_settings, recommended_root,
                          preferred_checkpoint, probe_local_models, diagnostic_text,
                          safe_copy_checkpoint, discover_servers)

CATALOG_PATH = Path.home()/'.chili_lab_story_image_studio'/'morning_catalog.json'
APP_ROOT = Path(__file__).resolve().parent.parent
HOME_OUTPUT = Path('D:/ai/CHILI_LAB_Images') if os.name=='nt' else Path.home()/'CHILI_LAB_Images'

class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('CHILI LAB Story Image Studio v1.3.1 | 4장 최종본 + Mio/Haru 6줄 마스터')
        self.geometry('1260x900')
        self.minsize(1050,750)
        self.configure(bg='#101724')
        self.style = ttk.Style(self)
        try: self.style.theme_use('clam')
        except tk.TclError: pass
        self.style.configure('TFrame',background='#101724')
        self.style.configure('TLabel',background='#101724',foreground='#e7eef8',font=('Malgun Gothic',10))
        self.style.configure('Header.TLabel',font=('Malgun Gothic',16,'bold'),foreground='#e7eef8')
        self.style.configure('Hint.TLabel',foreground='#9baac4')
        self.style.configure('TButton',font=('Malgun Gothic',10),padding=7)
        self.style.configure('TCombobox',padding=4)
        self.style.configure('TNotebook',background='#101724')
        self.style.configure('TNotebook.Tab',font=('Malgun Gothic',10),padding=(18,10))
        self.style.configure('TCheckbutton',background='#101724',foreground='#e7eef8')
        self.saved_config=load_settings()
        self.server_checkpoints=[]
        self.last_diagnostic='아직 진단하지 않았습니다.'
        self.last_local_models=[]
        self.data=None; self.scenes=[]; self.source_path=''; self.reference_path=''
        self.refs={'male':'','female':'','mood':''}
        self.selected_idx=0; self.event_q=queue.Queue(); self.stop_event=threading.Event(); self.working=False
        self.last_output_dir=None; self.last_final_paths=[]; self.photo=None;self.thumb_photos={};self.scene_image_paths={}
        self.channel=tk.StringVar(value='남녀')
        self.image_style=tk.StringVar(value='anime')
        self.character_hint=tk.StringVar(value='Japanese man in his early 20s, short black hair, cream shirt, dark jeans; Japanese woman in her early 20s, long dark hair, white blouse, soft yellow sweater, blue jeans. Keep design coherent.')
        self.use_reference=tk.BooleanVar(value=False) # legacy toggle not used in v1.1 reference strategy
        self.strength=tk.StringVar(value='0.72')
        self.ref_weight=tk.StringVar(value='0.55')
        self.reference_mode=tk.StringVar(value='story')
        self.require_actual_refs=tk.BooleanVar(value=True)
        self.engine=tk.StringVar(value='sdxl' if self.saved_config.get('checkpoint') else 'zimage')
        self.sdxl_checkpoint=tk.StringVar(value=self.saved_config.get('checkpoint',''))
        self.quality_mode=tk.StringVar(value='standard')
        self.export_mode=tk.StringVar(value='final_4_jpg')
        self.final_size=tk.StringVar(value='YouTube 1280x720')  # 4K would be an upscale, never the default
        self.morning_brand=tk.StringVar(value='HARU')
        self.morning_font=tk.StringVar(value='')
        self.morning_no=tk.StringVar(value='004')
        self.morning_size=tk.StringVar(value='YouTube 1280x720')
        self.morning_fmt=tk.StringVar(value='JPG')
        self.morning_scenes=[];self.morning_selected=0
        self.morning_brand_inputs={}
        self.upscale_model=tk.StringVar(value='realesrgan-x4plus-anime')
        self.address=tk.StringVar(value=self.saved_config.get('address','http://127.0.0.1:8188'))
        self.model_root=tk.StringVar(value=self.saved_config.get('model_root',str(recommended_root())))
        self.width=tk.StringVar(value='1024');self.height=tk.StringVar(value='576')
        self.output_dir=tk.StringVar(value=str(HOME_OUTPUT))
        self.upscaler=tk.StringVar(value='Lanczos')
        self.realesr_exe=tk.StringVar(value='')
        self.test_text=tk.StringVar(value='ComfyUI 연결 전')
        self.report=tk.StringVar(value='1. JSON 파일을 선택하세요.')
        self.progress=tk.StringVar(value='대기 중')
        self._build()
        self.after(100,self._poll)
        self.after(700,self._startup_detect)

    def _build(self):
        outer=ttk.Frame(self,padding=14);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='CHILI LAB  ·  Story Image Studio',style='Header.TLabel').pack(anchor='w',pady=(0,9))
        self.tabs=ttk.Notebook(outer);self.tabs.pack(fill='both',expand=True)
        self.page_project=ttk.Frame(self.tabs,padding=15)
        self.page_scenes=ttk.Frame(self.tabs,padding=15)
        self.page_render=ttk.Frame(self.tabs,padding=15)
        self.page_settings=ttk.Frame(self.tabs,padding=15)
        self.page_diagnostic=ttk.Frame(self.tabs,padding=15)
        self.page_morning=ttk.Frame(self.tabs,padding=15)
        for t,n in [(self.page_project,'① 가사 JSON/레퍼런스'),(self.page_scenes,'② 4장 스토리/프롬프트'),
                    (self.page_render,'③ 생성/저장'),(self.page_settings,'④ ComfyUI/화질 설정'),
                    (self.page_diagnostic,'⑤ 연결·모델 진단'),(self.page_morning,'⑥ Mio/Haru 모닝칠랩')]:
            self.tabs.add(t,text=n)
        self._project_ui();self._scenes_ui();self._render_ui();self._settings_ui();self._diagnostic_ui();self._morning_ui()
        ttk.Label(outer,textvariable=self.report,style='Hint.TLabel').pack(anchor='w',pady=(8,0))

    def _line(self,parent,title,widget_class=tk.Entry,var=None,browse=None,**kw):
        row=ttk.Frame(parent);row.pack(fill='x',pady=7)
        ttk.Label(row,text=title,width=22).pack(side='left')
        if widget_class is tk.Entry:
            entry=ttk.Entry(row,textvariable=var,**kw);entry.pack(side='left',fill='x',expand=True)
        if browse:
            ttk.Button(row,text='찾기',command=browse).pack(side='left',padx=(8,0))
        return row

    def _project_ui(self):
        p=self.page_project
        ttk.Label(p,text='JSON 15곡 → 기승전결 4장 · 남녀 레퍼런스 분리',style='Header.TLabel').pack(anchor='w',pady=(0,12))
        r=ttk.Frame(p);r.pack(fill='x')
        self.source_label=ttk.Label(r,text='선택한 JSON 없음',style='Hint.TLabel');self.source_label.pack(side='left',fill='x',expand=True)
        ttk.Button(r,text='JSON 파일 열기',command=self._load_json).pack(side='right')
        self.json_summary=ttk.Label(p,text='곡 수 및 역할 구성은 JSON을 읽으면 표시됩니다.',style='Hint.TLabel')
        self.json_summary.pack(anchor='w',pady=(9,11))
        r=ttk.Frame(p);r.pack(fill='x',pady=5)
        ttk.Label(r,text='채널/시점',width=22).pack(side='left')
        for ch in ('남자','여자','남녀'):
            ttk.Radiobutton(r,text=ch,value=ch,variable=self.channel).pack(side='left',padx=8)
        r=ttk.Frame(p);r.pack(fill='x',pady=5)
        ttk.Label(r,text='이미지 스타일',width=22).pack(side='left')
        ttk.Radiobutton(r,text='일본 애니메이션',variable=self.image_style,value='anime').pack(side='left',padx=8)
        ttk.Radiobutton(r,text='영화 실사',variable=self.image_style,value='realistic').pack(side='left',padx=8)
        self.ref_vars={key:tk.StringVar(value='선택 안 함') for key in ('male','female','mood')}
        for key,caption in [('male','남자 캐릭터 레퍼런스'),('female','여자 캐릭터 레퍼런스'),('mood','장면/분위기 레퍼런스')]:
            self._line(p,caption,var=self.ref_vars[key],browse=lambda k=key:self._browse_ref(k))
        ttk.Label(p,text='각 레퍼런스는 별도 저장됩니다. Z-Image Turbo는 남녀 얼굴을 직접 고정할 수 없습니다.',style='Hint.TLabel').pack(anchor='w',pady=5)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='레퍼런스 처리 방식',width=22).pack(side='left')
        ttk.Radiobutton(r,text='스토리 우선 (텍스트)',variable=self.reference_mode,value='story').pack(side='left',padx=3)
        ttk.Radiobutton(r,text='장면 원본 편집',variable=self.reference_mode,value='img2img').pack(side='left',padx=3)
        ttk.Radiobutton(r,text='SDXL IPAdapter',variable=self.reference_mode,value='ipadapter').pack(side='left',padx=3)
        ttk.Radiobutton(r,text='FLUX.2 남녀 레퍼런스',variable=self.reference_mode,value='flux2_multiref').pack(side='left',padx=3)
        ttk.Label(p,text='스토리 우선=레퍼런스 전송 안 함 | 원본 편집=1장만 | SDXL IPAdapter=추가 노드 필요 | FLUX.2=남/녀 이미지를 실제 입력 (얼굴 고정 보장 아님)',style='Hint.TLabel').pack(anchor='w')
        ttk.Checkbutton(p,text='레퍼런스 업로드 시 실제 이미지 미전달 모드에서 생성 차단 (권장)',variable=self.require_actual_refs).pack(anchor='w',pady=5)
        self._line(p,'인물 외형 설명(선택)',var=self.character_hint)
        ttk.Label(p,text='정확한 얼굴 고정은 보장하지 않습니다. 레퍼런스는 캐릭터 특징 유지의 보조 수단입니다.',style='Hint.TLabel').pack(anchor='w',pady=(4,9))
        controls=ttk.Frame(p);controls.pack(anchor='w',pady=11)
        ttk.Button(controls,text='① 분석 → 4장 프롬프트 생성',command=self._analyze).pack(side='left')
        ttk.Button(controls,text='참조 이미지 확대 (방식은 ④ 설정)',command=self._upscale_reference).pack(side='left',padx=8)

    def _scenes_ui(self):
        p=self.page_scenes
        ttk.Label(p,text='기승전결을 확인하고 프롬프트를 자유롭게 수정하세요',style='Header.TLabel').pack(anchor='w',pady=(0,12))
        frame=ttk.Frame(p);frame.pack(fill='both',expand=True)
        left=ttk.Frame(frame,width=275);left.pack(side='left',fill='y');left.pack_propagate(False)
        self.scenelist=tk.Listbox(left,font=('Malgun Gothic',11),background='#1b2638',foreground='white',
                             selectbackground='#335d93',border=0,highlightthickness=0)
        self.scenelist.pack(fill='both',expand=True)
        self.scenelist.bind('<<ListboxSelect>>',self._scene_changed)
        right=ttk.Frame(frame);right.pack(side='left',fill='both',expand=True,padx=(14,0))
        self.scene_meta=ttk.Label(right,text='JSON을 분석해 주세요.',style='Hint.TLabel');self.scene_meta.pack(anchor='w',pady=(0,7))
        self.scene_story=tk.Text(right,height=5,wrap='word',font=('Malgun Gothic',10),background='#1b2638',foreground='#e7eef8',border=0)
        self.scene_story.pack(fill='x',pady=(0,8));self.scene_story.config(state='disabled')
        ttk.Label(right,text='이미지 생성 프롬프트 (영문 · 수정 가능)').pack(anchor='w')
        self.scene_prompt=tk.Text(right,height=15,wrap='word',font=('Consolas',10),background='#1b2638',foreground='#ebf3ff',insertbackground='white',border=0)
        self.scene_prompt.pack(fill='both',expand=True,pady=5)
        btns=ttk.Frame(right);btns.pack(fill='x')
        ttk.Button(btns,text='현재 프롬프트 저장',command=self._save_prompt).pack(side='left')
        ttk.Button(btns,text='프롬프트 JSON 저장',command=self._export_prompts).pack(side='left',padx=8)
        ttk.Button(btns,text='생성 화면으로',command=lambda:self.tabs.select(self.page_render)).pack(side='right')

    def _render_ui(self):
        p=self.page_render
        ttk.Label(p,text='ComfyUI 연결 → 4장 순차 생성 → 2K/4K 저장',style='Header.TLabel').pack(anchor='w',pady=(0,12))
        row=ttk.Frame(p);row.pack(fill='x')
        self.btn_four=ttk.Button(row,text='4장 순차 생성 시작',command=lambda:self._begin_generate(False))
        self.btn_four.pack(side='left',padx=(0,9))
        self.btn_single=ttk.Button(row,text='현재 선택 장면 1장만',command=lambda:self._begin_generate(True));self.btn_single.pack(side='left')
        self.btn_cancel=ttk.Button(row,text='대기 중지',command=self._cancel,state='disabled');self.btn_cancel.pack(side='left',padx=(9,0))
        ttk.Label(p,textvariable=self.progress,style='Hint.TLabel').pack(anchor='w',pady=(12,8))
        body=ttk.Frame(p);body.pack(fill='both',expand=True)
        left=ttk.Frame(body);left.pack(side='left',fill='both',expand=True)
        self.log=tk.Text(left,height=18,wrap='word',font=('Consolas',10),background='#111b29',foreground='#dae9fe',state='disabled',border=0)
        self.log.pack(fill='both',expand=True)
        self.preview=tk.Label(body,text='생성 결과 미리보기',background='#1b2638',foreground='#e7eef8',width=53)
        self.preview.pack(side='right',fill='both',expand=True,padx=(10,0))
        gallery=ttk.Frame(p);gallery.pack(fill='x',pady=(9,0))
        ttk.Label(gallery,text='완료한 장면',width=12).pack(side='left')
        self.thumbs={}
        for no in ['01','02','03','04']:
            lbl=tk.Label(gallery,text='no'+no+'\n대기 중',width=20,height=5,background='#1b2638',foreground='#e7eef8')
            lbl.pack(side='left',padx=6)
            lbl.bind('<Button-1>',lambda event,n=no:self._open_thumb(n))
            self.thumbs[no]=lbl
        buttons=ttk.Frame(p);buttons.pack(fill='x',pady=(8,0))
        ttk.Button(buttons,text='결과 폴더 열기',command=self._open_folder).pack(side='left')
        ttk.Button(buttons,text='최종 4장 ZIP 다시 저장',command=self._zip_now).pack(side='left',padx=8)
        ttk.Label(buttons,text='참조 얼굴 완전 고정은 보장되지 않습니다.',style='Hint.TLabel').pack(side='right')

    def _settings_ui(self):
        p=self.page_settings
        ttk.Label(p,text='RTX 3060 12GB / RAM 32GB · 화질·엔진 설정',style='Header.TLabel').pack(anchor='w',pady=(0,8))
        self._line(p,'ComfyUI 로컬 주소',var=self.address)
        r=ttk.Frame(p);r.pack(fill='x',pady=(0,10))
        ttk.Button(r,text='연결 테스트',command=self._ping).pack(side='left')
        ttk.Button(r,text='로컬 포트 자동 찾기',command=self._auto_find_port).pack(side='left',padx=(8,0))
        ttk.Button(r,text='종합 진단',command=self._run_diagnostics).pack(side='left',padx=(8,0))
        ttk.Label(r,textvariable=self.test_text,style='Hint.TLabel').pack(side='left',padx=12)
        self._line(p,'최종 저장 폴더',var=self.output_dir,browse=self._browse_output)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='이미지 생성 모델',width=22).pack(side='left')
        ttk.Radiobutton(r,text='기존 Z-Image Turbo INT8',variable=self.engine,value='zimage').pack(side='left',padx=5)
        ttk.Radiobutton(r,text='SDXL 애니메이션 체크포인트',variable=self.engine,value='sdxl').pack(side='left',padx=5)
        ttk.Radiobutton(r,text='FLUX.2 Klein 4B (다중 레퍼런스)',variable=self.engine,value='flux2').pack(side='left',padx=5)
        self._line(p,'SDXL 체크포인트 파일명',var=self.sdxl_checkpoint)
        r=ttk.Frame(p);r.pack(fill='x',pady=3)
        ttk.Label(r,text='서버 인식 모델 선택',width=22).pack(side='left')
        self.model_combo=ttk.Combobox(r,values=[],textvariable=self.sdxl_checkpoint,state='readonly',width=65)
        self.model_combo.pack(side='left',fill='x',expand=True)
        self.model_combo.bind('<<ComboboxSelected>>',self._on_model_selected)
        ttk.Label(r,text='목록을 모두 표시 (이름 필터 없음)',style='Hint.TLabel').pack(side='left',padx=8)
        r=ttk.Frame(p);r.pack(fill='x',pady=(0,7))
        ttk.Button(r,text='설치된 SDXL 모델 찾기',command=self._list_models).pack(side='left')
        ttk.Button(r,text='Animagine XL 공식 다운로드',command=lambda:webbrowser.open_new_tab('https://huggingface.co/cagliostrolab/animagine-xl-3.1/tree/main')).pack(side='left',padx=7)
        ttk.Label(r,text='SDXL 사용 시 ComfyUI models/checkpoints에 모델을 먼저 설치해야 합니다.',style='Hint.TLabel').pack(side='left',padx=10)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='생성 품질 프리셋',width=22).pack(side='left')
        ttk.Combobox(r,values=['fast','standard','high'],textvariable=self.quality_mode,width=12,state='readonly').pack(side='left')
        ttk.Label(r,text='high = SDXL 32단계 / Turbo 9단계 (더 좋은 결과 보장은 아님)',style='Hint.TLabel').pack(side='left',padx=10)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='원본 생성 해상도',width=22).pack(side='left')
        ttk.Entry(r,textvariable=self.width,width=9).pack(side='left')
        ttk.Label(r,text='×').pack(side='left',padx=8)
        ttk.Entry(r,textvariable=self.height,width=9).pack(side='left')
        ttk.Label(r,text='기본 1024×576 · 16:9 / 1280×720은 메모리 상황에 따라',style='Hint.TLabel').pack(side='left',padx=10)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='결과 파일 종류',width=22).pack(side='left')
        ttk.Combobox(r,values=['final_4_jpg','final_4_png','both','2K','4K'],textvariable=self.export_mode,width=12,state='readonly').pack(side='left')
        ttk.Label(r,text='기본 final_4_jpg = 장면별 JPG 한 장씩, ZIP에도 4장만 (both는 구버전 다중 저장)',style='Hint.TLabel').pack(side='left',padx=10)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='최종 1장 해상도',width=22).pack(side='left')
        ttk.Combobox(r,values=list(SIZE_MAP),textvariable=self.final_size,width=22,state='readonly').pack(side='left')
        ttk.Label(r,text='스토리 final_4 모드 적용 · 실제 생성은 1024×576, 확대본은 네이티브 4K 아님',style='Hint.TLabel').pack(side='left',padx=9)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='업스케일 방법',width=22).pack(side='left')
        ttk.Combobox(r,values=['Lanczos','Real-ESRGAN'],textvariable=self.upscaler,width=15,state='readonly').pack(side='left')
        ttk.Label(r,text='Lanczos는 화소만 확대합니다. 선명도 개선은 Real-ESRGAN을 권장.',style='Hint.TLabel').pack(side='left',padx=10)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='AI 업스케일 모델',width=22).pack(side='left')
        ttk.Combobox(r,values=['realesrgan-x4plus-anime','realesr-animevideov3'],textvariable=self.upscale_model,width=26,state='readonly').pack(side='left')
        ttk.Label(r,text='애니 일러스트는 x4plus-anime 우선 테스트',style='Hint.TLabel').pack(side='left',padx=10)
        self._line(p,'Real-ESRGAN 실행파일',var=self.realesr_exe,browse=self._browse_realesr)
        r=ttk.Frame(p);r.pack(fill='x',pady=(0,7))
        ttk.Button(r,text='Real-ESRGAN 공식판 설치 (선택)',command=self._install_upscaler).pack(side='left')
        ttk.Label(r,text='버튼을 누를 때만 공식 GitHub에서 무료 파일을 받습니다.',style='Hint.TLabel').pack(side='left',padx=10)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='원본 편집 변화 강도',width=22).pack(side='left')
        ttk.Combobox(r,values=['0.55','0.65','0.72','0.82'],state='readonly',textvariable=self.strength,width=9).pack(side='left')
        ttk.Label(r,text='낮으면 비슷한 장면 반복 / 높으면 얼굴 드리프트 증가',style='Hint.TLabel').pack(side='left',padx=10)
        r=ttk.Frame(p);r.pack(fill='x',pady=6)
        ttk.Label(r,text='IPAdapter 참조 영향도',width=22).pack(side='left')
        ttk.Combobox(r,values=['0.35','0.45','0.55','0.70'],state='readonly',textvariable=self.ref_weight,width=9).pack(side='left')
        ttk.Label(r,text='SDXL + IPAdapter Plus 노드·가중치·CLIP Vision 설치 후 사용',style='Hint.TLabel').pack(side='left',padx=10)
        ttk.Label(p,text='품질 경고: Turbo + 단일 img2img 소스 4번 반복은 장면이 거의 똑같아질 수 있습니다.',style='Hint.TLabel').pack(anchor='w',pady=(13,3))
        ttk.Label(p,text='생성 결과 중복 의심 시 로그에 경고합니다. 원본 PNG와 실제 해상도도 보존합니다.',style='Hint.TLabel').pack(anchor='w')
        ttk.Button(p,text='⑤ 모델 미인식 원인 자세히 보기',command=lambda:self.tabs.select(self.page_diagnostic)).pack(anchor='w',pady=5)

    def _diagnostic_ui(self):
        p=self.page_diagnostic
        ttk.Label(p,text='ComfyUI 연결 / SDXL 체크포인트 원인 진단',style='Header.TLabel').pack(anchor='w',pady=(0,10))
        ttk.Label(p,text='Comfy Desktop Storage의 Shared Models 루트( checkpoints 하위폴더가 아닌 상위 폴더 )를 선택하세요.',style='Hint.TLabel').pack(anchor='w')
        self._line(p,'공유 모델 루트',var=self.model_root,browse=self._browse_model_root)
        r=ttk.Frame(p);r.pack(fill='x',pady=(0,10))
        ttk.Button(r,text='연결+모델 종합 진단',command=self._run_diagnostics).pack(side='left')
        ttk.Button(r,text='모델 파일 위치 복구',command=self._repair_model).pack(side='left',padx=9)
        ttk.Button(r,text='체크포인트 파일 직접 선택',command=self._choose_and_repair_model).pack(side='left',padx=9)
        ttk.Button(r,text='진단 보고서 저장',command=self._export_diagnostics).pack(side='left')
        ttk.Button(p,text='IPAdapter 설치·보조모델 사전 점검',command=self._check_ipadapter).pack(anchor='w',pady=(0,6))
        ttk.Label(p,text='복구는 확인을 받은 뒤 복사만 합니다. 파일 삭제·덮어쓰기·임의 설정 수정은 하지 않습니다.',style='Hint.TLabel').pack(anchor='w',pady=(0,7))
        self.diagnostic_view=tk.Text(p,wrap='word',font=('Consolas',10),background='#1b2638',foreground='#e7eef8',border=0)
        self.diagnostic_view.pack(fill='both',expand=True)
        self._show_diagnostic(self.last_diagnostic)

    def _show_diagnostic(self,message):
        self.diagnostic_view.config(state='normal')
        self.diagnostic_view.delete('1.0','end')
        self.diagnostic_view.insert('1.0',message)
        self.diagnostic_view.config(state='disabled')

    def _save_connection_settings(self):
        try:
            save_settings({'address':self.address.get().strip(),
                           'checkpoint':self.sdxl_checkpoint.get().strip(),
                           'model_root':self.model_root.get().strip()})
        except Exception as exc:
            self._append_log('설정 저장 실패: '+str(exc))

    def _on_model_selected(self,event=None):
        self._save_connection_settings()
        self.test_text.set('서버 인식 모델 선택됨 · '+self.sdxl_checkpoint.get())

    def _browse_model_root(self):
        folder=filedialog.askdirectory(title='Comfy Desktop Shared Models 최상위 폴더 선택',initialdir=self.model_root.get())
        if folder:
            self.model_root.set(folder)
            self._save_connection_settings()

    def _startup_detect(self):
        """Restore a working API endpoint, choosing a server with models."""
        if self.working:return
        candidates=self._candidate_addresses();preferred=self.sdxl_checkpoint.get()
        def job():
            servers=discover_servers(candidates,preferred_name=preferred)
            if servers:
                best=servers[0]
                self.event_q.put(('found_port',best['address']))
                self.event_q.put(('ping',best['status']+' · 모델 인식 서버 자동 연결'))
                if best['checkpoints']:self.event_q.put(('models',best['checkpoints']))
            else:
                self.event_q.put(('ping','ComfyUI를 실행한 뒤 연결 테스트 또는 종합 진단을 누르세요.'))
        threading.Thread(target=job,daemon=True).start()

    def _candidate_addresses(self):
        """Prefer a previously working endpoint; enumerate local listen ports if available."""
        import subprocess
        from urllib.parse import urlparse
        ordered=[]
        def add(addr):
            if addr not in ordered:ordered.append(addr)
        addr=self.address.get().strip()
        if addr.startswith('http://127.0.0.1:') or addr.startswith('http://localhost:'):
            add(addr.rstrip('/'))
        for port in (8188,8081,8189,8190,8191,8192,8193,8187,8000):
            add(f'http://127.0.0.1:{port}')
        if os.name=='nt':
            try:
                cp=subprocess.run(['netstat','-ano','-p','TCP'],capture_output=True,text=True,timeout=4,
                                  encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                ports=set()
                for line in cp.stdout.splitlines():
                    bits=line.split()
                    if len(bits)>=4 and bits[0].upper()=='TCP' and bits[3].upper()=='LISTENING':
                        local=bits[1]
                        if local.startswith(('127.0.0.1:','0.0.0.0:','[::1]:')):
                            port=int(local.rsplit(':',1)[-1])
                            if 1000<=port<=65535:ports.add(port)
                for port in sorted(ports):add(f'http://127.0.0.1:{port}')
            except Exception:pass
        return ordered[:100]

    def _run_diagnostics(self):
        self.test_text.set('로컬 서버·모델 종합 진단 중...')
        self.tabs.select(self.page_diagnostic)
        current_url=self.address.get();root=self.model_root.get();preferred=self.sdxl_checkpoint.get()
        candidates=self._candidate_addresses()
        def job():
            local=probe_local_models(Path(root),extra_roots=[Path('D:/ai/Comfy Desktop/ComfyUI-Models')])
            servers=discover_servers(candidates,preferred_name=preferred)
            best=servers[0] if servers else None
            address=best['address'] if best else ''
            server=best['checkpoints'] if best else []
            errors=[]
            if not best:errors.append('ComfyUI 서버에 연결하지 못했습니다. Desktop 인스턴스 실행을 확인하세요.')
            if best and best['model_error']:errors.append('모델 API: '+best['model_error'])
            message=diagnostic_text(address or current_url,root,server,local,'; '.join(errors))
            if servers:
                message+='\n실행 중인 ComfyUI 서버 목록 (모델 보유 서버 우선):\n'
                for item in servers:
                    message+=f" - {item['address']} / 체크포인트 {len(item['checkpoints'])}개\n"
                if len(servers)>1:
                    message+='주의: ComfyUI 인스턴스가 여러 개면 특정 서버에서만 모델이 보일 수 있습니다.\n'
            if address:self.event_q.put(('found_port',address))
            self.event_q.put(('diagnostic',(message,server,local,address,best['status'] if best else '')))
        threading.Thread(target=job,daemon=True).start()

    def _check_ipadapter(self):
        # Read-only: distinguish missing custom nodes from absent model weights.
        url=self.address.get().strip();root=self.model_root.get().strip()
        self.tabs.select(self.page_diagnostic)
        self.test_text.set('IPAdapter 확장/보조모델 점검 중...')
        def task():
            try:
                client=ComfyClient(url)
                client.ping(timeout=5)
                data=inspect_ipadapter(client._object_info(),root)
                report=format_ipadapter_report(data,url)
            except Exception as exc:
                report=('IPAdapter 점검 실패: '+str(exc)+'\n현재 ComfyUI 서버를 실행하고 ⑤ 연결·모델 종합 진단으로 올바른 서버를 먼저 선택하세요.')
            self.event_q.put(('ipadapter_report',report))
        threading.Thread(target=task,daemon=True).start()

    def _export_diagnostics(self):
        path=filedialog.asksaveasfilename(defaultextension='.txt',filetypes=[('텍스트','*.txt')],title='모델 진단 보고서 저장')
        if path:
            Path(path).write_text(self.last_diagnostic,encoding='utf-8')
            self.report.set('진단 보고서를 저장했습니다: '+path)

    def _choose_and_repair_model(self):
        """Use explicit file chosen by user, for files outside known model roots."""
        root=Path(self.model_root.get())
        if not root.is_dir():
            messagebox.showerror('모델 루트','⑤에서 Comfy Desktop Storage에 등록한 공유 모델 루트를 먼저 선택하세요.');return
        source_path=filedialog.askopenfilename(title='다운로드한 SDXL 체크포인트 파일 선택',
                filetypes=[('SDXL / 체크포인트 파일','*.safetensors *.ckpt *.pt')])
        if not source_path:return
        source=Path(source_path)
        target=root/'checkpoints'/source.name
        if source.resolve()==target.resolve():
            messagebox.showinfo('이미 제 위치에 있음',
                '파일은 공유 모델 루트의 checkpoints 폴더에 있습니다.\n'
                '파일을 다시 복사하지 않습니다. ⑤ 종합 진단에서 서버가 인식하는지 확인하세요.\n'
                '서버 미인식 시 Comfy Desktop의 현재 인스턴스가 Shared Models를 사용하는지 확인해야 합니다.')
            return
        self._copy_model_after_confirmation(source,root)

    def _copy_model_after_confirmation(self,source,root):
        target=root/'checkpoints'/source.name
        if not messagebox.askyesno('모델 복사 승인',
                '선택 모델을 다음 위치에 복사합니다.\n(원본 보존, 파일 덮어쓰기 없음)\n\n'+
                str(source)+'\n→ '+str(target)+'\n\n계속할까요?'):
            return
        def job():
            try:self.event_q.put(('repair_complete',str(safe_copy_checkpoint(source,root))))
            except Exception as exc:self.event_q.put(('repair_error',str(exc)))
        threading.Thread(target=job,daemon=True).start()

    def _repair_model(self):
        root=Path(self.model_root.get())
        if not root.is_dir():
            messagebox.showerror('모델 루트','먼저 ⑤ 탭에서 실제 Shared Models 폴더를 지정하세요.');return
        local=probe_local_models(root,extra_roots=[Path('D:/ai/Comfy Desktop/ComfyUI-Models')])
        # Primary recovery is correcting a model in root/models/checkpoints to root/checkpoints.
        misplaced=[m for m in local if Path(m['path']).parent.resolve()!= (root/'checkpoints').resolve()]
        if not misplaced:
            messagebox.showinfo('복사할 파일 없음',
                '모델이 이미 지정한 checkpoints 폴더 안에 있습니다.\n'
                '현재 인스턴스의 공유 모델 사용 설정을 Comfy Desktop에서 확인하세요.\n'
                '복구 작업으로 모델을 중복 복사하지 않습니다.')
            return
        if len(misplaced)>1:
            chosen=filedialog.askopenfilename(title='올바른 폴더로 복사할 모델 선택',
                                              initialdir=str(Path(misplaced[0]['path']).parent),
                                              filetypes=[('체크포인트','*.safetensors *.ckpt *.pt')])
            if not chosen:return
            source=Path(chosen)
            if str(source) not in [m['path'] for m in misplaced]:
                messagebox.showerror('복사 거부','검색된 파일 중 하나를 선택해야 합니다.');return
        else:source=Path(misplaced[0]['path'])
        target=root/'checkpoints'/source.name
        self._copy_model_after_confirmation(source,root)

    def _install_upscaler(self):
        if self.working:
            messagebox.showwarning('작업 중','생성이 끝난 뒤 설치해 주세요.');return
        location=Path('D:/ai/CHILI_LAB_Tools/RealESRGAN') if os.name=='nt' else Path.home()/'CHILI_LAB_Tools'/'RealESRGAN'
        if not messagebox.askyesno('공식 Real-ESRGAN 설치',
                '공식 GitHub에서 무료 Windows ZIP 파일을 다운로드하여\n' + str(location) + '\n에 압축 해제합니다.\n계속할까요?'):
            return
        self.test_text.set('Real-ESRGAN 다운로드·설치 중...')
        def job():
            try:
                exe=install_upscaler(location,notify=self._log)
                self.event_q.put(('installed_upscaler',str(exe)))
            except Exception as exc:self.event_q.put(('log','Real-ESRGAN 설치 실패: '+str(exc)))
        threading.Thread(target=job,daemon=True).start()

    def _list_models(self):
        self.test_text.set('ComfyUI 모델 목록 조회 중...')
        url=self.address.get()
        def job():
            try:
                client=ComfyClient(url)
                client.ping(timeout=3)
                models=client.list_checkpoints()
                self.event_q.put(('models',models))
            except Exception as exc:
                self.event_q.put(('models_error',str(exc)))
        threading.Thread(target=job,daemon=True).start()

    def _load_json(self):
        file=filedialog.askopenfilename(title='Suno/CHILI LAB JSON',filetypes=[('JSON','*.json')])
        if not file:return
        try:
            data=load_json(file);s=summary(data)
        except Exception as e:
            messagebox.showerror('JSON 오류',str(e));return
        self.data=data;self.source_path=file;self.scenes=[]
        self.source_label.config(text=Path(file).name)
        self.json_summary.config(text=f"EP {s['episode']} · {s['title']} · {s['song_count']}곡 | 남 {s['vocal_roles']['남자']} / 여 {s['vocal_roles']['여자']} / 듀엣 {s['vocal_roles']['듀엣']}")
        self.report.set('JSON 로드 성공. 아래 분석 버튼을 누르면 장면 4개를 만듭니다.')

    def _browse_ref(self,key):
        file=filedialog.askopenfilename(title={'male':'남자 캐릭터','female':'여자 캐릭터','mood':'장면/분위기'}[key]+' 이미지 선택',
                     filetypes=[('이미지','*.png *.jpg *.jpeg *.webp')])
        if file:
            self.refs[key]=file
            self.ref_vars[key].set(file)
            self.reference_path=file
            self.report.set('레퍼런스 선택 완료 · '+key+' / 실제 모델 반영은 참조 처리 방식에 따라 달라집니다.')

    def _upscale_reference(self):
        if self.working:
            messagebox.showwarning('작업 중','현재 생성이 끝난 후 실행하세요.');return
        path=self.refs.get('mood') or self.refs.get('male') or self.refs.get('female')
        if not path:
            messagebox.showwarning('이미지 필요','먼저 ①에서 남/여/무드 참조 이미지 중 하나를 선택하세요.');return
        if self.upscaler.get()=='Real-ESRGAN' and not Path(self.realesr_exe.get()).is_file():
            messagebox.showwarning('설치 필요','Real-ESRGAN 경로를 설정하거나 Lanczos를 선택하세요.');return
        with open(path,'rb') as f: raw=f.read()
        self.working=True;self.btn_four.config(state='disabled');self.btn_single.config(state='disabled')
        def task():
            try:
                folder=Path(self.output_dir.get())/('REFERENCE_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
                self.event_q.put(('folder',str(folder)))
                files=create_output(raw,folder,'reference',enhancer=self.upscaler.get(),enhancer_path=self.realesr_exe.get(),upscale_model=self.upscale_model.get())
                self._log('참조 원본 확대 완료: '+', '.join(x.name for x in files))
                self.event_q.put(('preview',str(files[1] if len(files)>1 else files[0])))
                self.event_q.put(('status','참조 원본 확대 완료 · '+str(folder)))
            except Exception as exc:self._log('이미지 확대 오류: '+str(exc))
            finally:self.event_q.put(('finished',None))
        self.tabs.select(self.page_render)
        self.progress.set('참조 원본 확대 작업 중...')
        threading.Thread(target=task,daemon=True).start()

    def _browse_output(self):
        p=filedialog.askdirectory(title='출력 폴더 선택')
        if p:self.output_dir.set(p)

    def _browse_realesr(self):
        p=filedialog.askopenfilename(title='realesrgan-ncnn-vulkan.exe 선택',filetypes=[('Windows exe','*.exe')])
        if p:self.realesr_exe.set(p)

    def _analyze(self):
        if not self.data:
            messagebox.showwarning('입력 필요','먼저 JSON 파일을 선택하세요.');return
        try:
            anchors=load_scene_anchors((self.data.get('meta') or {}).get('episodeNo'))
            self.scenes=build_scenes(self.data,self.channel.get(),self.image_style.get(),self.character_hint.get(),
                                     scene_anchors=anchors)
        except ValueError as exc:
            messagebox.showerror('장면 구성 오류',str(exc));return
        self.scenelist.delete(0,'end')
        for scene in self.scenes:
            self.scenelist.insert('end',f'{scene.number}  {scene.phase}  ·  {len(scene.track_numbers)}곡')
        self.selected_idx=0;self.scenelist.selection_set(0);self._set_scene(0)
        self.tabs.select(self.page_scenes)
        self.report.set('4장 스토리 생성 완료. 장면별 프롬프트 수정 후 저장할 수 있습니다.')

    def _save_prompt(self):
        if not self.scenes:return
        self.scenes[self.selected_idx].prompt=self.scene_prompt.get('1.0','end-1c').strip()

    def _set_scene(self,index):
        if not self.scenes or index >= len(self.scenes):return
        s=self.scenes[index]
        self.scene_meta.config(text=f"{s.phase}  |  {', '.join(str(n) for n in s.track_numbers)}번 곡  |  {', '.join(s.track_titles)}")
        self.scene_story.config(state='normal');self.scene_story.delete('1.0','end')
        self.scene_story.insert('1.0',s.narrative+'\n\n가사 신호: '+' / '.join(s.lyric_signals))
        self.scene_story.config(state='disabled')
        self.scene_prompt.delete('1.0','end');self.scene_prompt.insert('1.0',s.prompt)

    def _scene_changed(self,_event):
        selection=self.scenelist.curselection()
        if selection and self.scenes:
            self._save_prompt();self.selected_idx=selection[0];self._set_scene(self.selected_idx)

    def _export_prompts(self):
        if not self.scenes:return
        self._save_prompt()
        path=filedialog.asksaveasfilename(title='프롬프트 JSON 내보내기',defaultextension='.json',filetypes=[('JSON','*.json')])
        if path:
            Path(path).write_text(json.dumps([s.to_dict() for s in self.scenes],indent=2,ensure_ascii=False),encoding='utf-8')
            self.report.set('프롬프트 저장: '+path)

    def _ping(self):
        url=self.address.get()
        def job():
            try: status=ComfyClient(url).ping()
            except Exception as exc:status='실패: '+str(exc)
            self.event_q.put(('ping',status))
            if status.startswith('연결 성공'):
                try:self.event_q.put(('models',ComfyClient(url).list_checkpoints()))
                except Exception as exc:self.event_q.put(('models_error',str(exc)))
        threading.Thread(target=job,daemon=True).start()
        self.test_text.set('연결 확인 중...')

    def _auto_find_port(self):
        candidates=self._candidate_addresses();preferred=self.sdxl_checkpoint.get()
        def work():
            servers=discover_servers(candidates,preferred_name=preferred)
            if servers:
                best=servers[0]
                self.event_q.put(('found_port',best['address']))
                self.event_q.put(('ping',best['status']+' · '+best['address']))
                if best['checkpoints']:self.event_q.put(('models',best['checkpoints']))
            else:
                self.event_q.put(('ping','자동 검색 실패. ⑤ 종합 진단을 실행해 주세요.'))
        self.test_text.set('로컬 포트 검색 중...')
        threading.Thread(target=work,daemon=True).start()

    def _log(self,message):self.event_q.put(('log',message))

    def _begin_generate(self,single:bool):
        if self.working:return
        if not self.scenes:
            messagebox.showwarning('장면 없음','먼저 JSON 분석으로 4장 프롬프트를 만드세요.');return
        self._save_prompt()
        mode=self.reference_mode.get();engine=self.engine.get()
        if mode=='ipadapter' and engine!='sdxl':
            messagebox.showwarning('모델 선택 필요','남녀 참조 이미지를 실제 모델에 전달하는 IPAdapter는 SDXL 전용입니다. ④에서 SDXL 모델을 선택하세요.');return
        if mode=='img2img' and engine!='zimage':
            messagebox.showwarning('모델 선택 필요','원본 장면 편집(img2img)은 Z-Image Turbo 모드에서만 사용합니다.');return
        if mode=='flux2_multiref' and engine!='flux2':
            messagebox.showwarning('모델 선택 필요','FLUX.2 남녀 레퍼런스는 ④에서 FLUX.2 Klein 엔진을 선택해야 합니다.');return
        if mode=='flux2_multiref' and not (self.refs.get('male') or self.refs.get('female')):
            messagebox.showwarning('참조 필요','FLUX.2 남녀 레퍼런스는 ①에서 남자 또는 여자 이미지를 지정하세요.');return
        if mode=='img2img' and not self.refs.get('mood'):
            messagebox.showwarning('참조 필요','원본 장면 편집은 ①의 장면/분위기 레퍼런스를 지정하세요.');return
        if mode=='ipadapter' and not any(self.refs.values()):
            messagebox.showwarning('참조 필요','IPAdapter는 남자·여자·분위기 이미지 중 하나 이상 선택하세요.');return
        if engine=='sdxl' and not self.sdxl_checkpoint.get().strip():
            messagebox.showwarning('모델 필요','④에서 설치된 SDXL 체크포인트 파일명을 지정하세요.');return
        try:
            w,h=int(self.width.get()),int(self.height.get())
            if w%8 or h%8 or not 256<=w<=2048 or not 256<=h<=2048:raise ValueError('이미지 해상도')
            d=float(self.strength.get()); weight=float(self.ref_weight.get())
            if not .1<=d<=1 or not .1<=weight<=1.2:raise ValueError('참조 강도')
        except Exception:
            messagebox.showerror('설정 오류','해상도 256~2048 사이 8의 배수, 강도는 범위 내 숫자여야 합니다.');return
        if self.upscaler.get()=='Real-ESRGAN' and not Path(self.realesr_exe.get()).is_file():
            messagebox.showwarning('AI 모델 필요','Real-ESRGAN 실행파일을 먼저 선택하세요. Lanczos는 AI 복원이 아닙니다.');return
        if mode=='story' and any(self.refs.values()):
            if self.require_actual_refs.get():
                messagebox.showwarning('레퍼런스 미전달 차단','남녀 참조 이미지가 선택돼 있지만 스토리 우선은 이미지를 AI에 전달하지 않습니다.\n정말 같은 인물의 특징을 반영하려면 SDXL IPAdapter를 선택하고 노드/모델을 설치해야 합니다.\n텍스트만으로 제작하려면 ①의 참조 이미지 미전달 차단 체크를 직접 해제하세요.')
                return
            if not messagebox.askyesno('레퍼런스 미전달 확인','선택한 인물 이미지를 AI에 전혀 전송하지 않습니다.\n얼굴/의상 일치가 보장되지 않으며 참고 설명만 사용합니다. 계속할까요?'):
                return
        if mode=='img2img' and not single:
            messagebox.showwarning('4장 중복 방지','동일 레퍼런스 img2img 4장 반복은 중복 결과를 만듭니다.\n4장 서로 다른 장면은 SDXL IPAdapter(실제 레퍼런스 전달) 또는 스토리 우선으로 만드세요.\nimg2img는 단일 장면 시험만 허용합니다.')
            return
        self._save_connection_settings()
        self.working=True;self.stop_event.clear()
        self.scene_image_paths.clear();self.thumb_photos.clear();self.last_final_paths=[]
        for no,lbl in self.thumbs.items():lbl.config(image='',text='no'+no+'\n대기 중')
        self.btn_four.config(state='disabled');self.btn_single.config(state='disabled');self.btn_cancel.config(state='normal')
        self.tabs.select(self.page_render)
        scenes=deepcopy(self.scenes if not single else [self.scenes[self.selected_idx]])
        params={'address':self.address.get(),'candidate_addresses':self._candidate_addresses(),'width':w,'height':h,'references':dict(self.refs),
                'reference_mode':mode,'denoise':d,'ref_weight':weight,
                'engine':engine,'checkpoint':self.sdxl_checkpoint.get().strip(),
                'quality':self.quality_mode.get(),'upscaler':self.upscaler.get(),
                'upscale_model':self.upscale_model.get(),'exe':self.realesr_exe.get(),
                'export_mode':self.export_mode.get(),'final_size':self.final_size.get(),'output_dir':self.output_dir.get(),
                'style':self.image_style.get(),'channel':self.channel.get()}
        self.progress.set('작업 준비 중...')
        threading.Thread(target=self._worker,args=(scenes,params),daemon=True).start()

    def _worker(self,scenes,params):
        generated=[]; final_paths=[]; completed=0; job_dir=None
        try:
            client=ComfyClient(params['address'])
            try:
                status=client.ping()
                if params.get('engine')=='sdxl' and hasattr(client,'list_checkpoints'):
                    names=client.list_checkpoints()
                    if params['checkpoint'] not in names:
                        raise ComfyError('선택한 체크포인트를 현재 인스턴스가 인식하지 못합니다: '+params['checkpoint'])
            except Exception as initial_error:
                self._log('기존 ComfyUI 주소·모델 인식 오류. 서버 자동 재탐색: '+str(initial_error)[:300])
                candidates=params.get('candidate_addresses') or [params['address']]
                servers=discover_servers(candidates, preferred_name=params.get('checkpoint',''))
                if not servers:raise ComfyError('ComfyUI를 실행한 뒤 ⑤ 연결·모델 진단을 확인하세요.') from initial_error
                if params.get('engine')=='sdxl':
                    usable=next((s for s in servers if params['checkpoint'] in s['checkpoints']),None)
                    if not usable:
                        visible='; '.join(s['address']+' : '+(', '.join(s['checkpoints'][:4]) or '체크포인트 없음') for s in servers)
                        raise ComfyError('실행 중인 ComfyUI 인스턴스 어디에서도 모델을 찾지 못했습니다: '+
                                         params['checkpoint']+'\n⑤ 종합 진단과 Shared Models 설정 확인 필요. 서버 목록: '+visible)
                else:usable=servers[0]
                client=ComfyClient(usable['address'])
                status=client.ping()
                self.event_q.put(('found_port',usable['address']))
                self._log('자동 복구: ComfyUI 주소 '+usable['address'])
            self._log(status)
            # A job must not start its four-image pipeline while a required custom
            # node is absent; fail before creating an empty output directory.
            if hasattr(client,'validate_nodes'):
                client.validate_nodes(engine=params['engine'],checkpoint=params['checkpoint'],
                                      reference_mode=params['reference_mode'],
                                      reference=params['reference_mode']=='img2img')
            now=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            episode=(self.data.get('meta') or {}).get('episodeNo') or 'unknown'
            job_dir=Path(params['output_dir'])/f'EP{re.sub("[^A-Za-z0-9_-]","",str(episode))}_{params["channel"]}_{now}'
            job_dir.mkdir(parents=True,exist_ok=True)
            self.event_q.put(('folder',str(job_dir)))
            settings={k:v for k,v in params.items() if k!='references'}
            settings['reference_files']={k:Path(v).name for k,v in params['references'].items() if v}
            settings['character_id_warning']='IPAdapter is soft conditioning, not exact face ID lock.'
            settings['upscale_warning']='Lanczos is interpolation, not AI detail restoration.' if params['upscaler']=='Lanczos' else 'Real-ESRGAN external enhancement selected.'
            settings['rendered_scenes']=0
            review_dir=job_dir/REVIEW_DIRNAME
            settings['renders']=[]
            save_manifest(review_dir,summary(self.data),scenes,settings)
            for i,scene in enumerate(scenes,1):
                if self.stop_event.is_set():break
                self.event_q.put(('status',f'{i}/{len(scenes)} · {scene.phase} 생성 중...'))
                self._log(f'[{i}/{len(scenes)}] {scene.phase}: {", ".join(scene.track_titles)}')
                basename=f'no{int(scene.number):03d}'
                # Variation gate: a near-copy is never silently counted as a new scene.
                picture=None
                for retry in range(3):
                    variant_prompt=scene.prompt
                    if params['reference_mode']=='flux2_multiref':
                        roles=[k for k in ('male','female') if params['references'].get(k)]
                        variant_prompt=reference_edit_prompt(scene,roles)
                    if retry:
                        variant_prompt += (' Alternative independent anime scene composition: clearly new '
                                           'camera angle, distinct staging, different subject distance and '
                                           f'unique foreground/background separation. Composition iteration {retry+1}.')
                    picture=client.render(variant_prompt,
                        reference=params['references'].get('mood') if params['reference_mode']=='img2img' else None,
                        denoise=params['denoise'],width=params['width'],height=params['height'],
                        prefix='CHILI_'+basename,callback=self._log,cancelled=self.stop_event.is_set,
                        engine=params['engine'],checkpoint=params['checkpoint'],
                        references=params['references'],reference_mode=params['reference_mode'],
                        negative=scene.negative,quality=params['quality'],ref_weight=params['ref_weight'])
                    duplicate=detect_duplicate(picture,generated) if generated else None
                    if not duplicate:break
                    previous,similarity=duplicate
                    if retry<2:
                        self._log(f'유사 이미지 검출: 기존 {previous+1}번과 {similarity:.1%}. 새 구도로 자동 재시도 {retry+1}/2')
                    else:
                        raise ComfyError('3회 시도한 장면이 이전 이미지와 지나치게 유사하여 중단합니다. '
                                         '참조 강도를 낮추거나 IPAdapter 인물별 마스크 설정을 개선해 주세요.')
                generated.append(picture)
                evidence=dict(getattr(client,'last_render',None) or {})
                evidence.pop('graph',None)
                settings['renders'].append({'scene':scene.number,**evidence})
                if evidence.get('reference_mode') in ('ipadapter','flux2_multiref'):
                    self._log(f"레퍼런스 실제 입력 이미지 수: {evidence.get('conditioned_reference_images')} (얼굴 고정 판정은 사용자 육안 검수 필요)")
                if params['export_mode'].startswith('final_4_'):
                    ext='JPG' if params['export_mode']=='final_4_jpg' else 'PNG'
                    final=export_final(picture,job_dir,basename,size_label=params['final_size'],fmt=ext,
                        upscaler=params['upscaler'],upscaler_path=params['exe'],upscale_model=params['upscale_model'])
                    files=[final]
                else:
                    resolutions=('2K','4K') if params['export_mode']=='both' else (params['export_mode'],)
                    files=create_output(picture,job_dir,basename,resolutions=resolutions,
                           enhancer=params['upscaler'],enhancer_path=params['exe'],upscale_model=params['upscale_model'])
                self._log('완료: '+', '.join(f.name for f in files))
                view_path=str(files[0]) if params['export_mode'].startswith('final_4_') else str(files[1] if len(files)>1 else files[0])
                final_paths.extend(files if params['export_mode'].startswith('final_4_') else [])
                self.event_q.put(('preview',view_path))
                self.event_q.put(('thumbnail',(scene.number,view_path)))
                completed+=1
            settings['rendered_scenes']=completed
            settings['cancelled']=self.stop_event.is_set()
            save_manifest(review_dir,summary(self.data),scenes,settings)
            if params['export_mode'].startswith('final_4_'):
                if len(scenes)==4 and completed==4:
                    archive=archive_exact(final_paths,job_dir)
                    self._log('최종본 4장만 포함된 ZIP: '+str(archive))
                elif len(scenes)==1:
                    self._log('1장 시험 완료 · ZIP은 4장 완성 후 생성됩니다.')
            else:
                archive=zip_outputs(job_dir)
                self._log('구형 다중출력 ZIP: '+str(archive))
            self.event_q.put(('final_paths',final_paths))
            self.event_q.put(('status',f'{completed}/{len(scenes)}장 완료 · '+str(job_dir)))
        except Exception as exc:
            self._log('오류: '+str(exc))
            if job_dir is not None and job_dir.exists():
                try:
                    if not params['export_mode'].startswith('final_4_'):
                        partial=zip_outputs(job_dir,'CHILI_LAB_PARTIAL.zip')
                        self._log('부분 작업 ZIP 보존: '+str(partial))
                    else:self._log('부분 작업은 폴더에만 보관하며 4장 ZIP은 생성하지 않습니다.')
                except Exception as zip_exc:self._log('부분 ZIP 보존 실패: '+str(zip_exc))
            self.event_q.put(('status',f'{completed}/{len(scenes)}장 완료 후 오류: '+str(exc)[:220]))
        finally:
            self.event_q.put(('finished',None))

    def _cancel(self):
        self.stop_event.set();self._log('대기 중지 요청 · ComfyUI에 이미 전달된 작업은 계속될 수 있습니다.')

    def _append_log(self,s):
        self.log.config(state='normal');self.log.insert('end',datetime.now().strftime('%H:%M:%S ') + s+'\n');self.log.see('end');self.log.config(state='disabled')

    def _show_preview(self,path):
        try:
            with Image.open(path) as image:
                preview=image.convert('RGB');preview.thumbnail((475,365),Image.Resampling.LANCZOS)
                self.photo=ImageTk.PhotoImage(preview)
            self.preview.config(image=self.photo,text='')
        except Exception as exc:self._append_log('미리보기 오류: '+str(exc))

    def _add_thumbnail(self,number,path):
        self.scene_image_paths[number]=path
        try:
            with Image.open(path) as im:
                thumb=im.convert('RGB');thumb.thumbnail((160,85),Image.Resampling.LANCZOS)
                photo=ImageTk.PhotoImage(thumb)
            self.thumb_photos[number]=photo
            self.thumbs[number].config(image=photo,text='')
        except Exception as exc:self._append_log('썸네일 미리보기 오류: '+str(exc))

    def _open_thumb(self,number):
        path=self.scene_image_paths.get(number)
        if path:self._show_preview(path)

    def _poll(self):
        try:
            while True:
                tag,payload=self.event_q.get_nowait()
                if tag=='ping':
                    self.test_text.set(payload)
                    if payload.startswith('연결 성공'):
                        self._save_connection_settings()
                elif tag=='found_port':
                    self.address.set(payload)
                    self._save_connection_settings()
                elif tag=='log':self._append_log(payload)
                elif tag=='folder':self.last_output_dir=Path(payload)
                elif tag=='final_paths':self.last_final_paths=list(map(Path,payload))
                elif tag=='morning_status':self.morning_status.set(payload)
                elif tag=='status':self.progress.set(payload)
                elif tag=='preview':self._show_preview(payload)
                elif tag=='thumbnail':self._add_thumbnail(*payload)
                elif tag=='installed_upscaler':
                    self.realesr_exe.set(payload);self.upscaler.set('Real-ESRGAN')
                    self.test_text.set('Real-ESRGAN 설치 완료')
                    self._append_log('AI 업스케일러 설정 완료: '+payload)
                elif tag=='models':
                    self.server_checkpoints=payload
                    self.model_combo['values']=payload
                    if payload:
                        existing=self.sdxl_checkpoint.get().strip()
                        preferred=existing if existing in payload else preferred_checkpoint(payload)
                        if preferred:self.sdxl_checkpoint.set(preferred)
                        self._append_log('ComfyUI가 인식한 모든 체크포인트: '+', '.join(payload))
                        text=('모델 선택됨' if preferred else ('기존 선택 모델 미인식 · ⑤ 진단' if existing else '아래 목록에서 선택하세요'))
                        self.test_text.set(f'모델 {len(payload)}개 인식 · '+text)
                        self._save_connection_settings()
                    else:
                        self.test_text.set('API 모델 0개 · 이전 선택은 보존 · ⑤ 자동 진단')
                        self.after(50,self._run_diagnostics)
                elif tag=='models_error':
                    self.test_text.set('모델 목록 조회 실패 · ⑤ 진단 확인')
                    self._append_log('모델 목록 오류: '+payload)
                elif tag=='ipadapter_report':
                    self.last_diagnostic=payload
                    self._show_diagnostic(payload)
                    self.test_text.set('IPAdapter 진단 완료 · ⑤ 결과 확인')
                elif tag=='diagnostic':
                    message,server,local,address,version=payload
                    self.last_diagnostic=message
                    self.last_local_models=local
                    self._show_diagnostic(message)
                    self.test_text.set(f'진단: 서버 체크포인트 {len(server)}개 / 로컬 파일 {len(local)}개')
                    if server:
                        self.event_q.put(('models',server))
                    if address:self._save_connection_settings()
                elif tag=='repair_complete':
                    self.test_text.set('모델 파일 복사 완료 · ComfyUI 인스턴스 재시작 후 재진단')
                    self._append_log('체크포인트 복사 완료: '+payload)
                    messagebox.showinfo('모델 복사 완료','다음 위치에 복사했습니다.\n'+payload+
                        '\n\nComfyUI 인스턴스를 재시작하고 ⑤ 종합 진단을 다시 실행하세요.')
                elif tag=='repair_error':
                    self._append_log('모델 복사 실패: '+payload)
                    messagebox.showerror('모델 복사 오류',payload)
                elif tag=='finished':
                    self.working=False
                    self.btn_four.config(state='normal');self.btn_single.config(state='normal');self.btn_cancel.config(state='disabled')
                    self.btn_morning.config(state='normal')
        except queue.Empty:pass
        self.after(120,self._poll)

    def _open_folder(self):
        if not self.last_output_dir or not self.last_output_dir.exists():
            messagebox.showinfo('안내','먼저 이미지를 생성하세요.');return
        if os.name=='nt':os.startfile(str(self.last_output_dir))
        else:messagebox.showinfo('출력 폴더',str(self.last_output_dir))

    def _zip_now(self):
        if not self.last_output_dir or not self.last_output_dir.exists():
            messagebox.showinfo('안내','먼저 이미지를 생성하세요.');return
        try:
            if self.last_final_paths:
                archive=archive_exact(self.last_final_paths,self.last_output_dir)
            else:
                archive=zip_outputs(self.last_output_dir)
            messagebox.showinfo('ZIP 완료',str(archive))
        except Exception as exc:messagebox.showerror('ZIP 오류',str(exc))


    def _morning_ui(self):
        p=self.page_morning
        ttk.Label(p,text='Mio / Haru Morning Chill · 마스터 고정 + 6줄 / 번호로 장면 4장',style='Header.TLabel').pack(anchor='w',pady=(0,6))
        ttk.Label(p,text='사진에는 인물 없음. 이미지는 글자 없이 생성하고 마지막에 정확한 2개 텍스트를 합성합니다.',style='Hint.TLabel').pack(anchor='w',pady=(0,8))
        r=ttk.Frame(p);r.pack(fill='x')
        ttk.Label(r,text='채널',width=15).pack(side='left')
        for ch,caption in [('MIO',"mio's morning"),('HARU','haru little cafe')]:
            ttk.Radiobutton(r,text=caption,variable=self.morning_brand,value=ch,command=self._morning_switch).pack(side='left',padx=7)
        ttk.Button(r,text='마스터 TXT 열기',command=self._morning_open_master).pack(side='left',padx=12)
        ttk.Button(r,text='동봉된 마스터 불러오기',command=self._morning_load_bundled).pack(side='left')
        r=ttk.Frame(p);r.pack(fill='x',pady=5)
        ttk.Label(r,text='이번 영상 NO',width=15).pack(side='left')
        ttk.Entry(r,textvariable=self.morning_no,width=9).pack(side='left')
        ttk.Button(r,text='번호로 불러오기',command=self._morning_by_no).pack(side='left',padx=6)
        ttk.Button(r,text='현재 6줄을 번호별 보관',command=self._morning_save_entry).pack(side='left',padx=6)
        ttk.Button(r,text='회차 목록 JSON 가져오기',command=self._morning_import_catalog).pack(side='left',padx=6)
        ttk.Label(p,text='번호만 변경하려면 해당 회차의 실제 6줄 정보가 먼저 목록에 있어야 합니다. 번호만으로 제목·계절을 새로 만들지 않습니다.',style='Hint.TLabel').pack(anchor='w')
        ttk.Label(p,text='이번 영상 입력: 정확한 6줄을 붙여넣거나 아래 값을 수정하세요.').pack(anchor='w',pady=(5,0))
        self.morning_input=tk.Text(p,height=7,wrap='none',font=('Consolas',10),background='#1b2638',foreground='#f1f3ff',insertbackground='white')
        self.morning_input.pack(fill='x',pady=5)
        r=ttk.Frame(p);r.pack(fill='x',pady=(1,6))
        ttk.Button(r,text='6줄 분석 → A/B/C/D 생성',command=self._morning_analyze).pack(side='left')
        ttk.Label(r,text='결과: 서로 다른 사진 4장 · 채널명+DISPLAY_TEXT만 표기 · 원본 이미지 추가 저장 안 함',style='Hint.TLabel').pack(side='left',padx=11)
        body=ttk.Frame(p);body.pack(fill='both',expand=True)
        left=ttk.Frame(body);left.pack(side='left',fill='y')
        self.morning_list=tk.Listbox(left,width=28,height=10,background='#1b2638',foreground='white',selectbackground='#335d93',font=('Consolas',11))
        self.morning_list.pack(fill='y')
        self.morning_list.bind('<<ListboxSelect>>',self._morning_scene_change)
        right=ttk.Frame(body);right.pack(side='left',fill='both',expand=True,padx=8)
        self.morning_prompt=tk.Text(right,wrap='word',height=10,background='#1b2638',foreground='#edf1ff',insertbackground='white',font=('Consolas',10))
        self.morning_prompt.pack(fill='both',expand=True)
        r=ttk.Frame(p);r.pack(fill='x',pady=(5,3))
        ttk.Button(r,text='현재 장면 프롬프트 수정 저장',command=self._morning_save_prompt).pack(side='left')
        ttk.Label(r,text='최종 해상도',style='Hint.TLabel').pack(side='left',padx=(15,3))
        ttk.Combobox(r,values=list(SIZE_MAP),textvariable=self.morning_size,width=21,state='readonly').pack(side='left')
        ttk.Combobox(r,values=['JPG','PNG'],textvariable=self.morning_fmt,width=6,state='readonly').pack(side='left',padx=6)
        r=ttk.Frame(p);r.pack(fill='x',pady=4)
        ttk.Label(r,text='얇은 세리프 .ttf (선택)',width=22).pack(side='left')
        ttk.Entry(r,textvariable=self.morning_font).pack(side='left',fill='x',expand=True)
        ttk.Button(r,text='폰트 선택',command=self._morning_browse_font).pack(side='left',padx=7)
        r=ttk.Frame(p);r.pack(fill='x',pady=5)
        self.btn_morning=ttk.Button(r,text='모닝칠랩 4장 생성 + 정확히 4장 ZIP',command=self._morning_generate)
        self.btn_morning.pack(side='left')
        ttk.Label(r,text='④ 설정의 Z-Image Turbo/SDXL 선택과 로컬 ComfyUI를 사용합니다.',style='Hint.TLabel').pack(side='left',padx=11)
        self.morning_status=tk.StringVar(value='마스터를 불러오세요.')
        ttk.Label(p,textvariable=self.morning_status,style='Hint.TLabel').pack(anchor='w')
        self._morning_load_bundled()

    def _morning_switch(self):
        self._morning_load_bundled()

    def _morning_load_bundled(self):
        p=find_master(self.morning_brand.get())
        if p:self._morning_set_from_master(p)
        else:self.morning_status.set('마스터 TXT를 선택해주세요.')

    def _morning_open_master(self):
        path=filedialog.askopenfilename(filetypes=[('Master text','*.txt'),('All files','*.*')])
        if path:
            try:self._morning_set_from_master(Path(path))
            except Exception as exc:messagebox.showerror('마스터 오류',str(exc))

    def _morning_set_from_master(self,path):
        text=Path(path).read_text(encoding='utf-8-sig')
        brand=master_profile(text)
        ep=parse_six_lines(text)
        self.morning_brand.set(brand)
        self.morning_input.delete('1.0','end');self.morning_input.insert('1.0',ep.as_input())
        self.morning_no.set(ep.no)
        save_catalog_episode(CATALOG_PATH,brand,ep)
        self.morning_status.set(f'{BRANDS[brand]} 마스터 읽기 완료 · 현재 NO={ep.no} · 6줄 입력 검증됨')
        self._morning_analyze()

    def _morning_by_no(self):
        try:
            no=str(int(self.morning_no.get())).zfill(3)
            ep=load_catalog(CATALOG_PATH,self.morning_brand.get()).get(no)
            if not ep:raise ValueError(f'NO {no}의 실제 6줄이 등록되지 않았습니다. 6줄을 붙여넣고 번호별 보관을 누르세요.')
            self.morning_input.delete('1.0','end');self.morning_input.insert('1.0',ep.as_input())
            self._morning_analyze()
        except Exception as exc:messagebox.showerror('번호 조회',str(exc))

    def _morning_save_entry(self):
        try:
            ep=parse_six_lines(self.morning_input.get('1.0','end'))
            save_catalog_episode(CATALOG_PATH,self.morning_brand.get(),ep)
            self.morning_no.set(ep.no)
            self.morning_status.set(f'NO {ep.no} 보관 완료 · 번호만 바꿔 다시 불러올 수 있습니다.')
        except Exception as exc:messagebox.showerror('6줄 확인',str(exc))

    def _morning_import_catalog(self):
        path=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if path:
            try:
                count=import_catalog_json(Path(path),self.morning_brand.get(),CATALOG_PATH)
                self.morning_status.set(f'{count}개 회차 목록 가져옴 · 이제 번호로 불러올 수 있습니다.')
            except Exception as exc:messagebox.showerror('목록 가져오기',str(exc))

    def _morning_analyze(self):
        try:
            ep=parse_six_lines(self.morning_input.get('1.0','end'))
            self.morning_ep=ep
            self.morning_no.set(ep.no)
            self.morning_scenes=morning_prompts(self.morning_brand.get(),ep)
            self.morning_list.delete(0,'end')
            for s in self.morning_scenes:self.morning_list.insert('end',s['code']+' / '+s['title'])
            self.morning_selected=0;self.morning_list.selection_set(0)
            self.morning_prompt.delete('1.0','end');self.morning_prompt.insert('1.0',self.morning_scenes[0]['prompt'])
            self.morning_status.set(f'{BRANDS[self.morning_brand.get()]} · NO {ep.no} · 4개 독립 프롬프트 준비 완료')
        except Exception as exc:messagebox.showerror('6줄 분석 실패',str(exc))

    def _morning_save_prompt(self):
        if self.morning_scenes:
            self.morning_scenes[self.morning_selected]['prompt']=self.morning_prompt.get('1.0','end').strip()
            self.morning_status.set('현재 장면 프롬프트 수정 내용 저장됨')

    def _morning_scene_change(self,event):
        selection=self.morning_list.curselection()
        if selection and self.morning_scenes and selection[0]!=self.morning_selected:
            self._morning_save_prompt()
            self.morning_selected=selection[0]
            self.morning_prompt.delete('1.0','end');self.morning_prompt.insert('1.0',self.morning_scenes[self.morning_selected]['prompt'])

    def _morning_browse_font(self):
        path=filedialog.askopenfilename(filetypes=[('Serif font','*.ttf *.otf')])
        if path:self.morning_font.set(path)

    def _morning_generate(self):
        if self.working:return
        try:
            self._morning_save_prompt()
            ep=parse_six_lines(self.morning_input.get('1.0','end'))
            if not self.morning_scenes or self.morning_ep!=ep:
                raise ValueError('6줄 입력이 변경되었습니다. 먼저 6줄 분석 → A/B/C/D 생성을 눌러주세요.')
            if len(self.morning_scenes)!=4:raise ValueError('프롬프트 4개가 필요합니다.')
            font_file=find_serif_font(self.morning_font.get().strip())
            # Mio/Haru are photoreal: the story engine choice (SDXL anime / FLUX.2) never applies here.
            engine='zimage';checkpoint=''
            upscaler=self.upscaler.get()
            if upscaler=='Real-ESRGAN' and not Path(self.realesr_exe.get()).is_file():
                raise ValueError('④에서 Real-ESRGAN 실행 파일을 선택하거나 Lanczos로 변경하세요.')
            if not messagebox.askyesno('모닝칠랩 최종 4장','글자 없는 사진을 생성한 뒤 채널명+DISPLAY_TEXT 2개를 합성합니다. 4장의 JPG/PNG만 전달합니다.\nAI 사진에 원치 않는 글자가 그려지는 경우는 별도 검수가 필요합니다. 계속할까요?'):
                return
            settings={'address':self.address.get().strip(),'checkpoint':checkpoint,'size':self.morning_size.get(),
                      'fmt':self.morning_fmt.get(),'font':str(font_file),'upscaler':upscaler,
                      'exe':self.realesr_exe.get().strip(),'upscale_model':self.upscale_model.get(),
                      'output_dir':self.output_dir.get(),'quality':self.quality_mode.get(),'engine':engine}
        except Exception as exc:
            messagebox.showerror('모닝칠랩 생성 설정',str(exc));return
        self.working=True;self.stop_event.clear();self.last_final_paths=[]
        self.btn_morning.config(state='disabled')
        self.morning_status.set('모닝칠랩 A/B/C/D 생성 중...')
        threading.Thread(target=self._morning_worker,args=(dict(ep.__dict__),[dict(s) for s in self.morning_scenes],self.morning_brand.get(),settings),daemon=True).start()

    def _morning_worker(self,ep,scenes,brand,settings):
        paths=[]
        try:
            client=ComfyClient(settings['address'])
            if settings['engine'] not in PHOTO_ENGINES:
                raise ComfyError('Mio/Haru는 실사 사진 엔진(Z-Image Turbo)만 사용합니다: '+settings['engine'])
            job=Path(settings['output_dir'])/f"{brand}_no{ep['no']}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            job.mkdir(parents=True,exist_ok=True)
            self.event_q.put(('folder',str(job)))
            for i,scene in enumerate(scenes,1):
                if self.stop_event.is_set():break
                self.event_q.put(('morning_status',f"{i}/4 · {scene['code']} 사진 생성 중"))
                self._log(f"모닝칠랩 {scene['code']} 생성 요청")
                picture=client.render(scene['prompt'],width=1024,height=576,prefix=f"{brand}_no{ep['no']}_{scene['code']}",
                    engine=settings['engine'],checkpoint=settings['checkpoint'],reference_mode='story',quality=settings['quality'],
                    negative='text, words, logo, watermark, human, woman, man, hands, silhouette, anime, cartoon, illustration, deformed cup, blur',callback=self._log,cancelled=self.stop_event.is_set)
                path=export_final(picture,job,f"no{ep['no']}_{scene['code']}",size_label=settings['size'],fmt=settings['fmt'],
                     upscaler=settings['upscaler'],upscaler_path=settings['exe'],upscale_model=settings['upscale_model'],
                     brand_name=BRANDS[brand],display_text=ep['display_text'],font_path=settings['font'])
                paths.append(path)
                self._log('최종 모닝 이미지: '+path.name)
                self.event_q.put(('morning_status',f'{len(paths)}/4 완료: '+path.name))
                self.event_q.put(('preview',str(path)))
            if len(paths)==4:
                archive=archive_exact(paths,job,f'{brand}_no{ep["no"]}_ABCD.zip')
                self.event_q.put(('final_paths',paths))
                self.event_q.put(('morning_status','4/4 완료 · 최종 JPG/PNG 4장 + '+archive.name))
                self._log('모닝칠랩 ZIP 내 파일 4개 확인: '+str(archive))
            else:
                self.event_q.put(('morning_status',f'{len(paths)}/4 종료 · ZIP 미생성 (정확히 4장 필요)'))
        except Exception as exc:
            self.event_q.put(('morning_status','오류: '+str(exc)[:250]))
            self._log('모닝칠랩 생성 오류: '+str(exc))
        finally:self.event_q.put(('finished',None))

def main():
    app=Studio()
    app.mainloop()

if __name__=='__main__':main()
