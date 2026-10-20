"""Exactly one final artifact per generated scene. No duplicated source or upscale in release ZIP."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import zipfile
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat
from .output import ai_upscale_external

SIZE_MAP={'YouTube 1280x720':(1280,720),'2K 2560x1440':(2560,1440),'4K 3840x2160':(3840,2160)}


def find_serif_font(custom='') -> Path:
    if custom:
        p=Path(custom)
        if not p.is_file() or p.suffix.lower() not in ('.ttf','.otf'):
            raise ValueError('세리프 폰트 파일(.ttf/.otf)을 올바르게 선택하세요.')
        return p
    import os
    guesses=[]
    if os.name=='nt':
        guesses=[Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft/Windows/Fonts/CormorantGaramond-Regular.ttf',
                 Path('C:/Windows/Fonts/CormorantGaramond-Regular.ttf'),
                 Path('C:/Windows/Fonts/georgia.ttf'),Path('C:/Windows/Fonts/times.ttf')]
    else:
        guesses=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'),Path('/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf')]
    for p in guesses:
        if p.is_file():return p
    raise ValueError('세리프 폰트를 찾을 수 없습니다. ⑥ 모닝칠랩에서 .ttf 파일을 직접 선택하세요.')


def _draw_tracked(draw:ImageDraw.ImageDraw,xy:tuple[int,int],text:str,font:ImageFont.FreeTypeFont,spacing:float,fill):
    x,y=xy
    for char in text:
        draw.text((round(x),y),char,font=font,fill=fill,stroke_width=0)
        x += draw.textlength(char,font=font)+spacing
    return x


def _text_width(draw,text,font,spacing):
    return sum(draw.textlength(c,font=font) for c in text)+max(0,len(text)-1)*spacing


def _render_typography(im:Image.Image,brand_name:str,title:str,font_path:str):
    font_file=find_serif_font(font_path)
    draw=ImageDraw.Draw(im)
    W,H=im.size
    # Reserved left space. Same positions, relative sizes, and typography across A/B/C/D.
    max_width=W*.59
    title_size=int(H*.104)
    font=ImageFont.truetype(str(font_file),title_size)
    spacing=max(1,title_size*.018)
    while _text_width(draw,title,font,spacing)>max_width and title_size>int(H*.045):
        title_size-=2
        font=ImageFont.truetype(str(font_file),title_size)
        spacing=max(1,title_size*.018)
    if _text_width(draw,title,font,spacing)>max_width:
        raise ValueError('DISPLAY_TEXT가 너무 깁니다. 두 줄 자동 분할은 아직 지원하지 않습니다. 짧은 제목을 지정하세요.')
    small=ImageFont.truetype(str(font_file),int(H*.038))
    block_x=int(W*.095)
    big_y=int(H*.475)
    small_y=int(H*.398)
    # Contrast sampled under typographic zone; no gradient/backplate.
    rect=(block_x,int(H*.34),min(W,block_x+int(max_width)),int(H*.60))
    probe=im.crop(rect).convert('L')
    brightness=ImageStat.Stat(probe).mean[0]
    ink=(51,48,47) if brightness>127 else (249,246,237)
    _draw_tracked(draw,(block_x,small_y),brand_name,small,1.2,ink)
    _draw_tracked(draw,(block_x,big_y),title,font,spacing,ink)
    return im


def export_final(image_bytes:bytes,dest:Path,basename:str,*,size_label='4K 3840x2160',
                 fmt='JPG',upscaler='Lanczos',upscaler_path='',upscale_model='realesrgan-x4plus-anime',
                 brand_name='',display_text='',font_path='') -> Path:
    if size_label not in SIZE_MAP:raise ValueError('알 수 없는 출력 해상도')
    if fmt not in ('JPG','PNG'):raise ValueError('출력은 JPG 또는 PNG만 가능합니다.')
    with Image.open(BytesIO(image_bytes)) as raw:
        im=ImageOps.exif_transpose(raw).convert('RGB')
    if upscaler=='Real-ESRGAN':
        im=ai_upscale_external(im,upscaler_path,upscale_model)
    elif upscaler!='Lanczos':raise ValueError('지원되지 않는 확대 방식')
    im=ImageOps.fit(im,SIZE_MAP[size_label],method=Image.Resampling.LANCZOS)
    if brand_name:
        if not display_text:raise ValueError('모닝 채널은 DISPLAY_TEXT가 필요합니다.')
        im=_render_typography(im,brand_name,display_text,font_path)
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    path=dest/(basename+('.jpg' if fmt=='JPG' else '.png'))
    if fmt=='JPG':
        quality=91 if size_label=='YouTube 1280x720' else 94
        # YouTube user master: aim <=2MB for 1280x720 without significant degradation.
        while True:
            im.save(path,'JPEG',quality=quality,subsampling=0,optimize=True)
            if size_label!='YouTube 1280x720' or path.stat().st_size<=2_000_000 or quality<=72:break
            quality-=3
    else:im.save(path,'PNG',optimize=True)
    return path


def archive_exact(paths:list[Path],dest:Path,zip_name='FINAL_4_IMAGES.zip') -> Path:
    if len(paths)!=4:raise ValueError(f'정확히 4장 생성 완료 후 ZIP을 만듭니다. 현재 {len(paths)}장')
    validated=[]
    for p in paths:
        p=Path(p)
        if not p.is_file() or p.suffix.lower() not in ('.jpg','.png'):
            raise ValueError('이미지 파일이 없거나 이미지 형식이 아닙니다: '+str(p))
        with Image.open(p) as im:
            im.verify()
        validated.append(p)
    if len({p.name for p in validated})!=4:raise ValueError('출력 파일명이 중복됩니다.')
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    result=dest/zip_name
    with zipfile.ZipFile(result,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in validated:z.write(p,p.name)
    with zipfile.ZipFile(result) as z:
        if len(z.namelist())!=4:raise RuntimeError('ZIP에 4장이 들어있지 않습니다.')
    return result
