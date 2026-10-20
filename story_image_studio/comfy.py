"""Local-only ComfyUI API renderer.

Z-Image Turbo INT8 (original working configuration) and optional SDXL checkpoint.
SDXL IP-Adapter Plus can condition on independent character references if the
user installs compatible custom nodes and model assets. It is *not* FaceID lock.
"""
from __future__ import annotations
import random
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlencode
import requests
from .workflow_schema import combo_options, validate_graph, GraphSchemaError

MODEL_NAME = 'z_image_turbo_int8_convrot.safetensors'
TEXT_ENCODER = 'qwen_3_4b_fp8_mixed.safetensors'
VAE_NAME = 'ae.safetensors'
REQUIRED_CLASSES = {'UNETLoader','CLIPLoader','VAELoader','CLIPTextEncode',
                    'ModelSamplingAuraFlow','KSampler','EmptySD3LatentImage',
                    'ConditioningZeroOut','VAEDecode','SaveImage'}
SDXL_CLASSES = {'CheckpointLoaderSimple','CLIPTextEncode','EmptyLatentImage',
                'KSampler','VAEDecode','SaveImage'}
IPADAPTER_CLASSES = {'IPAdapterUnifiedLoader','IPAdapterAdvanced','LoadImage'}
# FLUX.2 [klein] 4B distilled, wiring copied from ComfyUI's official template
# image_flux2_klein_image_edit_4b_distilled.json (core nodes, no custom extension).
FLUX2_MODEL = 'flux-2-klein-4b-fp8.safetensors'
FLUX2_TEXT_ENCODER = TEXT_ENCODER  # same Qwen3-4B family as the template's qwen_3_4b
FLUX2_VAE = 'flux2-vae.safetensors'
FLUX2_CLASSES = {'UNETLoader','CLIPLoader','VAELoader','CLIPTextEncode','ConditioningZeroOut',
                 'EmptyFlux2LatentImage','Flux2Scheduler','KSamplerSelect','RandomNoise',
                 'CFGGuider','SamplerCustomAdvanced','VAEDecode','SaveImage'}
FLUX2_REF_CLASSES = {'LoadImage','ImageScaleToTotalPixels','VAEEncode','ReferenceLatent'}
ENGINES = ('zimage','sdxl','flux2')
REFERENCE_MODES = ('story','img2img','ipadapter','flux2_multiref')
PHOTO_ENGINES = ('zimage',)


def _validate_size(width:int, height:int):
    if width % 8 or height % 8 or min(width,height)<256 or max(width,height)>2048:
        raise ValueError('이미지 해상도는 각 변 256~2048px, 8의 배수여야 합니다.')


def graph(prompt: str, width: int = 1024, height: int = 576,
          seed: int | None = None, prefix='CHILI_LAB',
          reference_filename: str | None = None, denoise: float = .45,
          quality='standard') -> dict:
    """Z-Image Turbo INT8 API graph; optional img2img is *composition editing*."""
    _validate_size(width,height)
    if not .1<=denoise<=1: raise ValueError('denoise 0.1~1.0 필요')
    if seed is None: seed=random.SystemRandom().randint(0,2**53-1)
    steps=9 if quality=='high' else 8  # Turbo is distilled; >9 is not a magic quality boost
    nodes={
       '1':{'class_type':'UNETLoader','inputs':{'unet_name':MODEL_NAME,'weight_dtype':'default'}},
       '2':{'class_type':'CLIPLoader','inputs':{'clip_name':TEXT_ENCODER,'type':'lumina2','device':'default'}},
       '3':{'class_type':'VAELoader','inputs':{'vae_name':VAE_NAME}},
       '4':{'class_type':'CLIPTextEncode','inputs':{'clip':['2',0],'text':prompt}},
       '5':{'class_type':'ConditioningZeroOut','inputs':{'conditioning':['4',0]}},
       '6':{'class_type':'EmptySD3LatentImage','inputs':{'width':width,'height':height,'batch_size':1}},
       '7':{'class_type':'ModelSamplingAuraFlow','inputs':{'model':['1',0],'shift':3}},
       '8':{'class_type':'KSampler','inputs':{'model':['7',0],'positive':['4',0],
                 'negative':['5',0],'latent_image':['6',0],'seed':seed,'steps':steps,
                 'cfg':1.0,'sampler_name':'res_multistep','scheduler':'simple','denoise':1.0}},
       '9':{'class_type':'VAEDecode','inputs':{'samples':['8',0],'vae':['3',0]}},
       '10':{'class_type':'SaveImage','inputs':{'images':['9',0],'filename_prefix':prefix}},
    }
    if reference_filename:
        nodes['11']={'class_type':'LoadImage','inputs':{'image':reference_filename}}
        nodes['12']={'class_type':'ImageScale','inputs':{'image':['11',0],
                 'upscale_method':'lanczos','width':width,'height':height,'crop':'center'}}
        nodes['13']={'class_type':'VAEEncode','inputs':{'pixels':['12',0],'vae':['3',0]}}
        nodes['8']['inputs']['latent_image']=['13',0]
        nodes['8']['inputs']['denoise']=denoise
        del nodes['6']
    return nodes


def sdxl_graph(prompt:str, negative:str, checkpoint:str,
               width=1024,height=576,seed=None,prefix='CHILI_LAB',
               quality='high', uploaded_refs:dict|None=None,
               ref_weight=.55) -> dict:
    """Ordinary SDXL text-to-image graph, optionally *soft* IPAdapter Plus references.

    Independent male/female/style files get separate IPAdapterAdvanced stages, so
    a single source photo is not repeatedly edited to the identical scene.
    """
    _validate_size(width,height)
    if not checkpoint or checkpoint.startswith(('/', '\\')) or '..' in checkpoint.replace('\\','/').split('/') or not checkpoint.lower().endswith(('.safetensors','.ckpt','.pt')):
        raise ValueError('④ 설정에서 SDXL 체크포인트 파일명(.safetensors)을 입력하세요.')
    if not .1 <= ref_weight <= 1.2: raise ValueError('IPAdapter 영향도 0.1~1.2 필요')
    if seed is None: seed=random.SystemRandom().randint(0,2**53-1)
    steps={'fast':20,'standard':26,'high':32}.get(quality,26)
    nodes={
       '1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':checkpoint}},
       '2':{'class_type':'CLIPTextEncode','inputs':{'clip':['1',1],'text':prompt}},
       '3':{'class_type':'CLIPTextEncode','inputs':{'clip':['1',1],'text':negative}},
       '4':{'class_type':'EmptyLatentImage','inputs':{'width':width,'height':height,'batch_size':1}},
       '5':{'class_type':'KSampler','inputs':{'model':['1',0],'positive':['2',0],'negative':['3',0],
                'latent_image':['4',0],'seed':seed,'steps':steps,'cfg':6.0,
                'sampler_name':'dpmpp_2m','scheduler':'karras','denoise':1.0}},
       '6':{'class_type':'VAEDecode','inputs':{'samples':['5',0],'vae':['1',2]}},
       '7':{'class_type':'SaveImage','inputs':{'images':['6',0],'filename_prefix':prefix}},
    }
    if uploaded_refs:
        nodes['8']={'class_type':'IPAdapterUnifiedLoader',
                    'inputs':{'model':['1',0],'preset':'PLUS (high strength)'}}
        last_model=['8',0]
        for j, (role, filename) in enumerate(uploaded_refs.items()):
            if not filename: continue
            ix=str(9+2*j); iy=str(10+2*j)
            nodes[ix]={'class_type':'LoadImage','inputs':{'image':filename}}
            nodes[iy]={'class_type':'IPAdapterAdvanced',
                       'inputs':{'model':last_model,'ipadapter':['8',1],'image':[ix,0],
                                 'weight':float(ref_weight) if role!='mood' else min(.30,float(ref_weight)),
                                 'weight_type':'linear','combine_embeds':'concat',
                                 'start_at':0.0,'end_at':.85,'embeds_scaling':'V only'}}
            last_model=[iy,0]
        nodes['5']['inputs']['model']=last_model
    return nodes


def flux2_graph(prompt:str, width=1024, height=576, seed=None, prefix='CHILI_LAB',
                uploaded_refs:dict|None=None, steps=4, ref_megapixels=1.0,
                model=FLUX2_MODEL, text_encoder=FLUX2_TEXT_ENCODER, vae=FLUX2_VAE) -> dict:
    """FLUX.2 Klein text-to-image, or multi-reference edit when refs are given.

    Each reference (e.g. male, female) is encoded separately and appended as its
    own ReferenceLatent on BOTH the positive and the zeroed negative conditioning,
    exactly like the official template. Order of refs = image1, image2 in prompt.
    """
    _validate_size(width,height)
    if width % 16 or height % 16:
        raise ValueError('FLUX.2 latent는 가로·세로 16의 배수가 필요합니다.')
    if not 1 <= int(steps) <= 50: raise ValueError('FLUX.2 steps 1~50')
    if seed is None: seed=random.SystemRandom().randint(0,2**53-1)
    nodes={
       '1':{'class_type':'UNETLoader','inputs':{'unet_name':model,'weight_dtype':'default'}},
       '2':{'class_type':'CLIPLoader','inputs':{'clip_name':text_encoder,'type':'flux2','device':'default'}},
       '3':{'class_type':'VAELoader','inputs':{'vae_name':vae}},
       '4':{'class_type':'CLIPTextEncode','inputs':{'clip':['2',0],'text':prompt}},
       '5':{'class_type':'ConditioningZeroOut','inputs':{'conditioning':['4',0]}},
       '6':{'class_type':'EmptyFlux2LatentImage','inputs':{'width':width,'height':height,'batch_size':1}},
       '7':{'class_type':'Flux2Scheduler','inputs':{'steps':int(steps),'width':width,'height':height}},
       '8':{'class_type':'KSamplerSelect','inputs':{'sampler_name':'euler'}},
       '9':{'class_type':'RandomNoise','inputs':{'noise_seed':seed}},
       '10':{'class_type':'CFGGuider','inputs':{'model':['1',0],'positive':['4',0],'negative':['5',0],'cfg':1.0}},
       '11':{'class_type':'SamplerCustomAdvanced','inputs':{'noise':['9',0],'guider':['10',0],
                 'sampler':['8',0],'sigmas':['7',0],'latent_image':['6',0]}},
       '12':{'class_type':'VAEDecode','inputs':{'samples':['11',0],'vae':['3',0]}},
       '13':{'class_type':'SaveImage','inputs':{'images':['12',0],'filename_prefix':prefix}},
    }
    pos,neg=['4',0],['5',0]
    for j,(role,filename) in enumerate((uploaded_refs or {}).items()):
        if not filename: continue
        base=20+10*j
        load,scale,enc,rp,rn=(str(base+k) for k in range(5))
        nodes[load]={'class_type':'LoadImage','inputs':{'image':filename}}
        nodes[scale]={'class_type':'ImageScaleToTotalPixels','inputs':{'image':[load,0],
                      'upscale_method':'lanczos','megapixels':float(ref_megapixels),'resolution_steps':1}}
        nodes[enc]={'class_type':'VAEEncode','inputs':{'pixels':[scale,0],'vae':['3',0]}}
        nodes[rp]={'class_type':'ReferenceLatent','inputs':{'conditioning':pos,'latent':[enc,0]}}
        nodes[rn]={'class_type':'ReferenceLatent','inputs':{'conditioning':neg,'latent':[enc,0]}}
        pos,neg=[rp,0],[rn,0]
    nodes['10']['inputs']['positive']=pos
    nodes['10']['inputs']['negative']=neg
    return nodes


def reference_count(nodes:dict) -> int:
    """How many distinct images actually condition the diffusion graph.

    Follows links back from ReferenceLatent/IPAdapterAdvanced to LoadImage, so
    the report is evidence from the queued graph, not the UI's intent.
    """
    def sources(node_id,seen):
        if node_id in seen or node_id not in nodes: return set()
        seen.add(node_id)
        node=nodes[node_id]
        if node.get('class_type')=='LoadImage': return {node_id}
        found=set()
        for value in node.get('inputs',{}).values():
            if isinstance(value,list) and len(value)==2: found|=sources(str(value[0]),seen)
        return found
    images=set()
    for node in nodes.values():
        if node.get('class_type')=='ReferenceLatent':
            images|=sources(str(node['inputs'].get('latent',[None])[0]),set())
        elif node.get('class_type')=='IPAdapterAdvanced':
            images|=sources(str(node['inputs'].get('image',[None])[0]),set())
    return len(images)


class ComfyError(RuntimeError): pass


class ComfyClient:
    def __init__(self,url='http://127.0.0.1:8188',session=None):
        self.url=url.rstrip('/')
        parsed=urlparse(self.url)
        if parsed.scheme!='http' or (parsed.hostname or '').lower() not in ('localhost','127.0.0.1','::1'):
            raise ComfyError('참조 이미지를 보호하기 위해 127.0.0.1 로컬 ComfyUI만 허용합니다.')
        self.session=session or requests.Session()
        self.client_id=str(uuid.uuid4())

    def _request(self,method,path,*,timeout=30,**kwargs):
        try:
            response=self.session.request(method,self.url+path,timeout=timeout,**kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            detail=str(exc)
            if getattr(exc,'response',None) is not None:
                detail+=' '+exc.response.text[:900]
            raise ComfyError('ComfyUI 요청 실패: '+detail) from exc

    def ping(self,timeout=8):
        data=self._request('GET','/system_stats',timeout=timeout).json()
        return '연결 성공 · '+str((data.get('system') or {}).get('comfyui_version') or 'ComfyUI')

    def _object_info(self):
        return self._request('GET','/object_info',timeout=30).json()

    @staticmethod
    def _extract_checkpoints(data) -> list[str]:
        """ComfyUI /object_info/{node} and /object_info variants.

        Do not filter by SDXL/Animagine naming: users may rename checkpoints.
        """
        if not isinstance(data, dict):
            raise ComfyError('ComfyUI 모델 정보가 JSON 객체가 아닙니다.')
        node=data.get('CheckpointLoaderSimple',data)
        if not isinstance(node,dict) or not node.get('input'):
            raise ComfyError('현재 인스턴스에 CheckpointLoaderSimple 노드가 없습니다.')
        required=(node.get('input') or {}).get('required') or {}
        values=required.get('ckpt_name')
        if not isinstance(values,list) or not values or not isinstance(values[0],list):
            raise ComfyError('ComfyUI의 ckpt_name 목록 형식을 읽지 못했습니다.')
        return sorted({x for x in values[0] if isinstance(x,str) and x}, key=str.casefold)

    def list_checkpoints(self) -> list[str]:
        # Fetch a single node: avoids a very large /object_info response.
        try:
            info=self._request('GET','/object_info/CheckpointLoaderSimple',timeout=15).json()
            return self._extract_checkpoints(info)
        except (ComfyError, ValueError, TypeError, KeyError):
            info=self._object_info()
            return self._extract_checkpoints(info)

    def validate_nodes(self,reference=False,engine='zimage',checkpoint='',reference_mode='story',info=None):
        info=info if info is not None else self._object_info()
        classes={'zimage':REQUIRED_CLASSES,'sdxl':SDXL_CLASSES,'flux2':FLUX2_CLASSES}[engine].copy()
        if engine=='sdxl' and reference_mode=='ipadapter': classes |= IPADAPTER_CLASSES
        if engine=='zimage' and reference: classes |= {'LoadImage','ImageScale','VAEEncode'}
        if engine=='flux2' and reference_mode=='flux2_multiref': classes |= FLUX2_REF_CLASSES
        missing=sorted(classes-set(info))
        if missing:
            detail='ComfyUI에 필요한 노드가 없습니다: '+', '.join(missing)
            if engine=='flux2':
                detail += ('\n원인: 현재 ComfyUI 버전이 FLUX.2 core 노드를 등록하지 않았습니다.'
                           '\n해결: FLUX.2 Klein을 지원하는 ComfyUI 인스턴스(별도/격리 권장)를 선택하세요.')
            if engine=='sdxl' and reference_mode=='ipadapter' and set(missing) & IPADAPTER_CLASSES:
                detail += ('\n원인: SDXL 레퍼런스용 IPAdapter Plus가 현재 ComfyUI 인스턴스에 설치/로드되지 않았습니다.'
                           '\n해결: Comfy Desktop 현재 인스턴스 → 확장 프로그램 관리 → ComfyUI_IPAdapter_plus 설치 → 인스턴스 재시작.'
                           '\n추가 필요: models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors 및 '
                           'models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors.'
                           '\n⑤ 연결·모델 진단에서 IPAdapter 사전 점검을 실행하세요.')
            raise ComfyError(detail)
        if engine=='zimage':
            choices=[('UNETLoader','unet_name',MODEL_NAME),('CLIPLoader','clip_name',TEXT_ENCODER),('VAELoader','vae_name',VAE_NAME)]
        elif engine=='flux2':
            choices=[('UNETLoader','unet_name',FLUX2_MODEL),('CLIPLoader','clip_name',FLUX2_TEXT_ENCODER),('VAELoader','vae_name',FLUX2_VAE)]
        else:
            choices=[('CheckpointLoaderSimple','ckpt_name',checkpoint)]
        for cl,field,filename in choices:
            if not filename:raise ComfyError('체크포인트 파일명을 선택하세요.')
            options=combo_options((info.get(cl) or {}).get('input',{}).get('required',{}).get(field))
            if options is not None and filename not in options:
                raise ComfyError('모델이 ComfyUI에 없습니다: '+filename+'\n모델 폴더를 확인하고 인스턴스를 재시작하세요.')
        if engine=='sdxl' and reference_mode=='ipadapter':
            options=combo_options((info.get('IPAdapterUnifiedLoader') or {}).get('input',{}).get('required',{}).get('preset'))
            if options is not None and 'PLUS (high strength)' not in options:
                raise ComfyError('IPAdapter Plus의 PLUS 모델 프리셋을 사용할 수 없습니다. 확장 프로그램을 확인하세요.')

    def upload_reference(self,filepath) -> str:
        filepath=Path(filepath)
        if not filepath.exists() or filepath.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):
            raise ComfyError('레퍼런스는 PNG/JPG/WEBP여야 합니다.')
        if filepath.stat().st_size>30*1024*1024:raise ComfyError('레퍼런스는 30MB 이하여야 합니다.')
        with filepath.open('rb') as f:
            res=self._request('POST','/upload/image',timeout=90,
                     files={'image':(filepath.name,f)},data={'overwrite':'false'})
        return str(res.json()['name'])

    def queue(self,nodes) -> str:
        resp=self._request('POST','/prompt',timeout=60,json={'prompt':nodes,'client_id':self.client_id}).json()
        if 'error' in resp:raise ComfyError('ComfyUI 워크플로 오류: '+str(resp['error']))
        if not resp.get('prompt_id'):raise ComfyError('작업 ID가 없습니다: '+str(resp)[:600])
        return resp['prompt_id']

    def wait_for_images(self,prompt_id,timeout_sec=1200,callback=None,cancelled=None):
        start=time.monotonic(); last=-1
        while time.monotonic()-start<timeout_sec:
            if cancelled and cancelled():
                raise ComfyError('대기 중단. 이미 등록된 ComfyUI 작업은 계속 실행될 수 있습니다.')
            history=self._request('GET','/history/'+prompt_id,timeout=20).json()
            item=history.get(prompt_id)
            if item:
                status=item.get('status') or {}
                if status.get('status_str')=='error':
                    errors=[x for x in status.get('messages',[]) if isinstance(x,list) and x[0]=='execution_error']
                    raise ComfyError('ComfyUI 생성 실패: '+str(errors[-1][1] if errors else status)[:1300])
                if item.get('outputs'):
                    images=[]
                    for node in item['outputs'].values():
                        for m in node.get('images',[]):
                            params=urlencode({'filename':m['filename'],'subfolder':m.get('subfolder',''),'type':m.get('type','output')})
                            images.append(self._request('GET','/view?'+params,timeout=90).content)
                    if images:return images
                    if status.get('completed'):raise ComfyError('저장된 이미지가 없습니다.')
            elapsed=int(time.monotonic()-start)
            if callback and elapsed//10 != last:
                last=elapsed//10;callback(f'ComfyUI 작업 진행 중 · {elapsed}초')
            time.sleep(2)
        raise ComfyError(f'{timeout_sec}초 안에 생성 완료되지 않았습니다. ComfyUI 큐를 확인하세요.')

    def render(self,prompt,reference=None,denoise=.45,width=1024,height=576,
               prefix='CHILI_LAB',callback=None,cancelled=None,*,engine='zimage',
               checkpoint='',references=None,reference_mode=None,negative='',quality='standard',
               ref_weight=.55,seed=None,flux2_steps=4):
        # Compatibility with V1 render(reference=...). New calls always supply mode explicitly.
        if reference_mode is None:reference_mode='img2img' if reference else 'story'
        if engine not in ENGINES:raise ComfyError('알 수 없는 모델 엔진')
        if reference_mode not in REFERENCE_MODES:raise ComfyError('알 수 없는 참조 방식')
        if reference_mode=='ipadapter' and engine!='sdxl':
            raise ComfyError('IPAdapter는 SDXL 체크포인트를 선택해야 합니다. Z-Image Turbo에는 연결할 수 없습니다.')
        if reference_mode=='img2img' and engine!='zimage':
            raise ComfyError('현재 img2img 편집은 Z-Image Turbo에만 지원합니다.')
        if reference_mode=='flux2_multiref' and engine!='flux2':
            raise ComfyError('FLUX.2 다중 레퍼런스는 FLUX.2 Klein 엔진에서만 사용합니다.')
        refs={k:v for k,v in (references or {}).items() if v}
        single_reference=reference or refs.get('scene') or refs.get('mood')
        # Identity references only, in a fixed order the prompt can name (image 1 = man).
        identity_refs={k:refs[k] for k in ('male','female') if refs.get(k)}
        if reference_mode=='img2img' and not single_reference:
            raise ComfyError('img2img를 위해 장면 참조 이미지를 선택하세요.')
        if reference_mode=='ipadapter' and not refs:
            raise ComfyError('IPAdapter에 사용할 남성·여성·무드 레퍼런스를 선택하세요.')
        if reference_mode=='flux2_multiref' and not identity_refs:
            raise ComfyError('FLUX.2 다중 레퍼런스에는 남자 또는 여자 인물 레퍼런스가 필요합니다. 텍스트 전용으로 대체하지 않습니다.')
        info=self._object_info()
        self.validate_nodes(reference=reference_mode=='img2img',engine=engine,checkpoint=checkpoint,
                            reference_mode=reference_mode,info=info)
        if engine=='zimage':
            uploaded=self.upload_reference(single_reference) if reference_mode=='img2img' else None
            nodes=graph(prompt,width,height,prefix=prefix,reference_filename=uploaded,
                        denoise=denoise,quality=quality,seed=seed)
        elif engine=='flux2':
            uploaded_refs={k:self.upload_reference(p) for k,p in identity_refs.items()} if reference_mode=='flux2_multiref' else {}
            nodes=flux2_graph(prompt,width,height,seed=seed,prefix=prefix,uploaded_refs=uploaded_refs,
                              steps=flux2_steps)
        else:
            uploaded_refs={key:self.upload_reference(path) for key,path in refs.items()} if reference_mode=='ipadapter' else {}
            nodes=sdxl_graph(prompt,negative,checkpoint,width,height,prefix=prefix,quality=quality,
                             uploaded_refs=uploaded_refs,ref_weight=ref_weight,seed=seed)
        try:
            validate_graph(nodes,info)
        except GraphSchemaError as exc:
            raise ComfyError(str(exc)) from exc
        conditioned=reference_count(nodes)
        if reference_mode in ('ipadapter','flux2_multiref') and conditioned==0:
            raise ComfyError('레퍼런스가 그래프에 연결되지 않았습니다. 생성을 중단합니다.')
        job=self.queue(nodes)
        self.last_render={'prompt_id':job,'engine':engine,'reference_mode':reference_mode,
                          'conditioned_reference_images':conditioned,'graph':nodes}
        if callback:callback('ComfyUI 대기열 등록 '+job[:8])
        return self.wait_for_images(job,callback=callback,cancelled=cancelled)[0]
