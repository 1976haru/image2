"""Resolution/format conversion, optional offline AI enhancer, manifest and ZIP."""
from pathlib import Path
from datetime import datetime
import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from PIL import Image, ImageOps, ImageFile
Image.MAX_IMAGE_PIXELS = 100_000_000

SIZES = {'2K':(2560,1440),'4K':(3840,2160)}
# Manifests/drafts live here, never beside the four delivered images.
REVIEW_DIRNAME = '_review'


def _fit(image, dims):
    if image.size == dims:
        return image.copy()
    return ImageOps.fit(image, dims, method=Image.Resampling.LANCZOS, centering=(.5,.5))


def ai_upscale_external(image: Image.Image, exe_path: str, model='realesrgan-x4plus-anime') -> Image.Image:
    """Optional Real-ESRGAN ncnn-vulkan executable; user installs separately.
    Run without shell and with per-task temporary paths. External model may not exist.
    """
    exe = Path(exe_path)
    if not exe.is_file() or exe.name.lower() != 'realesrgan-ncnn-vulkan.exe':
        raise ValueError('Real-ESRGAN 경로에서 realesrgan-ncnn-vulkan.exe를 선택하세요.')
    # Explicit model selection; executable's distributed models directory required.
    models_dir = exe.parent/'models'
    if not models_dir.is_dir():
        raise ValueError('실행파일 옆 models 폴더가 없습니다. Real-ESRGAN 전체 배포판이 필요합니다.')
    if not (models_dir / (model+'.param')).exists() or not (models_dir / (model+'.bin')).exists():
        raise ValueError(f'선택한 Real-ESRGAN 모델 {model}의 .param/.bin 파일을 models 폴더에서 찾지 못했습니다.')
    with tempfile.TemporaryDirectory(prefix='chili_up_') as d:
        src = Path(d)/'input.png'
        dst = Path(d)/'enhanced.png'
        image.convert('RGB').save(src)
        command = [str(exe),'-i',str(src),'-o',str(dst),'-n',model,'-s','4','-m',str(models_dir)]
        run = subprocess.run(command,capture_output=True,text=True,timeout=300,check=False)
        if run.returncode != 0 or not dst.exists():
            raise RuntimeError('Real-ESRGAN 업스케일 실패: '+(run.stderr or run.stdout)[-900:])
        with Image.open(dst) as output:
            return output.convert('RGB').copy()


def create_output(image_bytes: bytes, dest: str | Path, basename: str,
                  resolutions=('2K','4K'), formats=('JPG','PNG'),
                  enhancer='Lanczos', enhancer_path='', reference_info='',
                  upscale_model='realesrgan-x4plus-anime', save_source=True) -> list[Path]:
    dest = Path(dest)
    dest.mkdir(parents=True,exist_ok=True)
    with Image.open(io.BytesIO(image_bytes)) as raw:
        image = ImageOps.exif_transpose(raw).convert('RGB')
    if save_source:
        source=dest/(basename+'_SOURCE.png')
        image.save(source,'PNG',optimize=True)
    else:
        source=None
    if enhancer == 'Real-ESRGAN':
        image = ai_upscale_external(image,enhancer_path,upscale_model)
    elif enhancer != 'Lanczos':
        raise ValueError('알 수 없는 업스케일 방식')
    files = [source] if source else []
    for res in resolutions:
        frame = _fit(image,SIZES[res])
        for fmt in formats:
            suffix = '.jpg' if fmt == 'JPG' else '.png'
            target = dest/(basename+'_'+res+suffix)
            if fmt == 'JPG':
                frame.save(target,'JPEG',quality=95,subsampling=0,optimize=True)
            else:
                frame.save(target,'PNG',optimize=True)
            files.append(target)
    return files


def save_manifest(dest, meta, scenes, settings):
    dest = Path(dest)
    dest.mkdir(parents=True,exist_ok=True)
    obj = {'created_at':datetime.now().isoformat(timespec='seconds'),
           'source':meta, 'settings':settings,
           'scenes':[x.to_dict() if hasattr(x,'to_dict') else x for x in scenes]}
    name=dest/'storyboard_manifest.json'
    name.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
    return name


def zip_outputs(dest, zip_name='CHILI_LAB_4SCENES.zip'):
    dest = Path(dest)
    items = [x for x in sorted(dest.iterdir()) if x.suffix.lower() in ('.png','.jpg','.json') and x.name != zip_name]
    name = dest/zip_name
    with zipfile.ZipFile(name,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for item in items:
            archive.write(item,item.name)
    return name
