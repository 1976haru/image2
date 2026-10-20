"""Simple local QC heuristics: detect suspiciously repeated visual compositions.
Not an aesthetic scorer or facial identity verifier.
"""
from __future__ import annotations
from io import BytesIO
from PIL import Image, ImageChops, ImageStat, ImageFilter


def similarity(a:bytes, b:bytes) -> float:
    """Normalized coarse-image RMS similarity in [0,1]. Detect near-duplicates.
    Deliberately ignores fine upscale noise that can conceal identical compositions.
    """
    def small(raw):
        with Image.open(BytesIO(raw)) as image:
            im=image.convert('RGB').resize((160,90),Image.Resampling.BILINEAR)
            return im.filter(ImageFilter.GaussianBlur(.8))
    im1,im2=small(a),small(b)
    diff=ImageChops.difference(im1,im2)
    rms=ImageStat.Stat(diff).rms
    return max(0.0,min(1.0,1.0-(sum(rms)/3)/255.0))


def detect_duplicate(candidate:bytes, previous:list[bytes], threshold=.945) -> tuple[int,float]|None:
    for i,p in enumerate(previous):
        value=similarity(candidate,p)
        if value>=threshold:
            return i,value
    return None
