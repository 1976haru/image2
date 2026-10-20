"""User-initiated optional Real-ESRGAN portable installer (official GitHub release).

Never runs automatically. No subprocess execution during installation; extracts
only after safe archive checks. The app remains usable without this dependency.
"""
from __future__ import annotations
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZipFile

RELEASE_URL = ('https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/'
               'realesrgan-ncnn-vulkan-20220424-windows.zip')
MAX_COMPRESSED_SIZE=350 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE=650 * 1024 * 1024


def install_upscaler(root: str|Path, url: str=RELEASE_URL, notify=None) -> Path:
    """Download and safely unpack a known official portable release.

    URL is fixed by default; only tests supply another URL. Requires online access.
    Does not modify the user's ComfyUI installation or existing generated images.
    """
    root=Path(root).resolve(); root.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix='chili_esrgan_') as temporary:
        zpath=Path(temporary)/'package.zip'
        with urlopen(url,timeout=40) as resp, zpath.open('wb') as f:
            if resp.headers.get('Content-Length') and int(resp.headers['Content-Length'])>MAX_COMPRESSED_SIZE:
                raise ValueError('Real-ESRGAN ZIP이 예상보다 큽니다. 설치를 중단했습니다.')
            read=0; bucket=-1
            while True:
                block=resp.read(1024*1024)
                if not block:break
                read+=len(block)
                if read>MAX_COMPRESSED_SIZE:raise ValueError('압축 파일 크기 한도를 초과했습니다.')
                f.write(block)
                if notify and read//(20*1024*1024)!=bucket:
                    bucket=read//(20*1024*1024)
                    notify('Real-ESRGAN 다운로드 중: '+str(read//(1024*1024))+'MB')
        if notify:notify('파일 검증 및 압축 해제 중...')
        with ZipFile(zpath) as z:
            files=z.infolist()
            if len(files)>1000:raise ValueError('배포 ZIP 파일 수가 예상보다 많습니다.')
            if sum(x.file_size for x in files)>MAX_UNCOMPRESSED_SIZE:
                raise ValueError('압축 해제 예상 용량이 너무 큽니다.')
            for info in files:
                destination=(root/info.filename).resolve()
                if not destination.is_relative_to(root):
                    raise ValueError('ZIP 경로가 안전하지 않습니다.')
                # Reject Unix symlinks. Portable archive from GitHub should contain normal files.
                if info.external_attr>>16 & 0o170000 == 0o120000:
                    raise ValueError('심볼릭 링크가 있는 ZIP은 설치하지 않습니다.')
            z.extractall(root)
    candidates=list(root.rglob('realesrgan-ncnn-vulkan.exe'))
    valid=[exe for exe in candidates if (exe.parent/'models').is_dir()]
    if not valid:
        raise RuntimeError('압축 해제는 완료했지만 exe와 models 폴더가 함께 있지 않습니다.')
    if notify:notify('Real-ESRGAN 설치 완료')
    return valid[0]
