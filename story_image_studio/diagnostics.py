"""Read-only diagnostics + explicit, safe copy repair for Comfy Desktop models.

Do not assume a Comfy Desktop primary DOWNLOADS folder implies each instance
has shared-model discovery enabled. Only the running ComfyUI API can confirm.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import re
import shutil
from typing import Iterable

MODEL_SUFFIXES = {'.safetensors', '.ckpt', '.pt'}
PREFERRED_NAME = ('animagine', 'sdxl', 'pony', 'illustrious', 'anime', 'xl')


def settings_path() -> Path:
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData'/'Local'))) / 'CHILI_LAB' / 'StoryImageStudio' / 'settings_v12.json'
    return Path.home()/'.config'/'chili_lab'/'story_image_studio'/'settings_v12.json'


def load_settings(path:Path|None=None) -> dict:
    path = Path(path or settings_path())
    try:
        obj=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(obj,dict) and obj.get('version')==1:
            return {x:obj[x] for x in ('address','checkpoint','model_root') if isinstance(obj.get(x),str)}
    except (OSError,ValueError,TypeError): pass
    return {}


def save_settings(data:dict,path:Path|None=None):
    path=Path(path or settings_path())
    path.parent.mkdir(parents=True,exist_ok=True)
    serialized={'version':1}
    for field in ('address','checkpoint','model_root'):
        val=data.get(field)
        if isinstance(val,str):serialized[field]=val
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(serialized,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)
    return path


def recommended_root() -> Path:
    return Path('D:/ai/Comfy Desktop/ComfyUI-Models') if os.name=='nt' else Path.home()/'ComfyUI-Models'


def preferred_checkpoint(names:list[str]) -> str|None:
    for hint in PREFERRED_NAME:
        for name in names:
            if hint in name.lower() and name.lower().endswith(tuple(MODEL_SUFFIXES)):
                return name
    return None


def checkpoint_dirs(root:Path) -> list[Path]:
    root=Path(root)
    candidates=[root/'checkpoints',root/'models'/'checkpoints',root/'checkpoints'/'checkpoints']
    return [p for i,p in enumerate(candidates) if p not in candidates[:i]]


def probe_local_models(root:Path, *, extra_roots:Iterable[Path]=()) -> list[dict]:
    """Bounded to explicit model roots; no entire-drive scanning."""
    inspected=set();found=[]
    for r in [Path(root), *map(Path, extra_roots)]:
        for folder in checkpoint_dirs(r):
            if not folder.is_dir():continue
            try:
                for path in folder.glob('**/*'):
                    if not path.is_file() or path.suffix.lower() not in MODEL_SUFFIXES:continue
                    if path.resolve() in inspected:continue
                    inspected.add(path.resolve())
                    found.append({'name':path.name, 'path':str(path),
                                  'size_gb':round(path.stat().st_size/1_000_000_000,2),
                                  'root':str(r),'nested':str(path.relative_to(folder))})
            except (OSError,PermissionError):continue
    return sorted(found,key=lambda d:d['name'].lower())


def compare_models(server_models:list[str], local_models:list[dict]):
    server=set(server_models)
    # ComfyUI may show relative subfolder name. Relative Windows/POSIX paths accepted.
    server_basenames={n.replace('\\','/').split('/')[-1].lower() for n in server}
    result=[]
    for model in local_models:
        result.append({**model,'visible_in_api':model['name'].lower() in server_basenames or model['nested'] in server})
    return result


def safe_copy_checkpoint(source:Path,model_root:Path) -> Path:
    """Called only after user confirmation in UI. Never overwrite models."""
    source=Path(source);model_root=Path(model_root)
    if not source.is_file() or source.suffix.lower() not in MODEL_SUFFIXES:raise ValueError('체크포인트 파일이 아닙니다.')
    if source.stat().st_size<1024:raise ValueError('모델 파일이 너무 작습니다. 다운로드가 완료됐는지 확인하세요.')
    target_dir=model_root/'checkpoints';target_dir.mkdir(parents=True,exist_ok=True)
    target=target_dir/source.name
    if source.resolve()==target.resolve():return target
    if target.exists():raise FileExistsError('대상 폴더에 동일 파일명이 있습니다. 안전을 위해 덮어쓰지 않습니다: '+str(target))
    usage=shutil.disk_usage(target_dir)
    if usage.free < source.stat().st_size+100_000_000:raise OSError('D드라이브 여유 공간이 부족합니다.')
    tmp=target.with_suffix(target.suffix+'.part')
    if tmp.exists():raise FileExistsError('이전 복사 임시 파일이 있습니다: '+str(tmp))
    try:
        with source.open('rb') as f, tmp.open('xb') as out:
            shutil.copyfileobj(f,out,4*1024*1024)
        if tmp.stat().st_size!=source.stat().st_size:raise IOError('복사 용량이 일치하지 않습니다.')
        tmp.rename(target)
    finally:
        if tmp.exists():tmp.unlink()
    return target


def diagnostic_text(address:str,root:str,server_models:list[str],local_models:list[dict],err:str=''):
    lines=['CHILI LAB Story Image Studio v1.2 · 모델 연결 진단',
           f'ComfyUI 주소: {address}',f'지정 모델 루트: {root}',
           f'API 상태: {"오류: "+err if err else "응답"}',
           f'API 체크포인트 수: {len(server_models)}',
           f'로컬 모델 발견 수: {len(local_models)}',
           '주의: 지정 폴더에 존재하는 파일이 현재 인스턴스에 등록됐다는 뜻은 아닙니다.']
    for n in server_models:lines.append('  [서버 인식] '+n)
    for item in compare_models(server_models,local_models):
        state='서버 인식됨' if item['visible_in_api'] else '서버에서 안 보임'
        lines.append(f"  [로컬·{state}] {item['path']} ({item['size_gb']}GB)")
    if not server_models and local_models:
        lines.append('해결: Comfy Desktop → Storage에서 지정 모델 루트를 Shared Models로 추가하고, 현재 인스턴스에서 공유 모델 사용을 확인한 뒤 인스턴스를 재시작하세요.')
        lines.append('다른 ComfyUI 인스턴스에서는 모델 목록이 다를 수 있습니다.')
    if server_models and not preferred_checkpoint(server_models):
        lines.append('서버는 모델을 인식합니다. SDXL이 맞는 파일을 직접 선택해야 합니다. 이름으로 SDXL 여부를 보장할 수 없습니다.')
    return '\n'.join(lines)+'\n'


def discover_servers(addresses, *, preferred_name='', client_factory=None, workers=8):
    """Inspect several running local instances; prefer one with the requested model.

    Bounded parallel local-only requests. Return [dict] scored best first. A port
    having a Python listener alone does not identify it as ComfyUI.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if client_factory is None:
        from .comfy import ComfyClient
        client_factory=ComfyClient
    addresses=list(dict.fromkeys(addresses))[:64]
    if not addresses:return []
    preferred_name=preferred_name.strip().lower()
    def probe(item):
        idx,address=item
        try:
            client=client_factory(address)
            status=client.ping(timeout=1.2)
        except Exception:return None
        names=[];err=''
        try:names=client.list_checkpoints()
        except Exception as exc:err=str(exc)
        good=bool(names)
        matches=bool(preferred_name and preferred_name in [name.lower() for name in names])
        score=(100 if matches else 0)+(40 if preferred_checkpoint(names) else 0)+(15 if good else 0)+(3 if idx==0 else 0)
        return {'address':address,'status':status,'checkpoints':names,'model_error':err,
                'score':score,'order':idx}
    results=[]
    with ThreadPoolExecutor(max_workers=min(workers,len(addresses))) as pool:
        fs=[pool.submit(probe,item) for item in enumerate(addresses)]
        for f in as_completed(fs):
            x=f.result()
            if x is not None:results.append(x)
    return sorted(results,key=lambda x:(-x['score'],x['order']))
