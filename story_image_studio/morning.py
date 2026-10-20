"""Mio/Haru six-line thumbnail pipeline — prompt logic, no external model.

Brand specifications are derived from the user-provided MIO v11.2 and HARU v2.0 masters.
A different NO needs a stored episode entry; never invent six fields from an ID.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import re
from pathlib import Path

FIELDS = ('NO','PLAYLIST_CODE','状況','MAIN_TEXT','DISPLAY_TEXT','EMOTIONAL_LINE')
BRANDS = {'MIO': "mio's morning", 'HARU': 'haru little cafe'}
FAMILIES = {
    'P01': ('bright serene morning','cream, powder blue, sage','soft window daylight and fresh sky'),
    'P02': ('rainy morning','pearl gray, sage, warm ivory','distinct raindrops on cafe pane'),
    'P03': ('spring blooms','restrained blush, soft pistachio, light ivory','one natural blossom accent'),
    'P04': ('summer breeze','sky blue, gentle green, clean white','fresh leaves and clear sunlight'),
    'P05': ('autumn cozy','soft amber, oatmeal and warm ivory','a single realistic autumn foliage accent'),
    'P06': ('winter soft morning','milk white, ice blue, pale gray','bright frost or snow beyond the window'),
    'P07': ('book and coffee','paper ivory, graphite blue, sage','one open book or notebook'),
    'P08': ('weekend brunch','soft butter, blush and light wood','one realistic modest pastry on a plate'),
}
SCENES_MIO = [
 ('A','AIR & LIGHT','wide airy room, luminous open sky, sunlit cafe windowsill, minimal natural cloud reflections'),
 ('B','CURTAIN & SPACE','delicate sheer curtain casting graceful shadows, calm cafe geometry, airy editorial negative space'),
 ('C','EDITORIAL STILL LIFE','low intimate still life, refined ceramic drink, one relevant meaningful seasonal object, sharp focal textures'),
 ('D','SEASONAL PLACE','quiet believable Japanese neighborhood or intimate terrace view, carefully framed through a window'),
]
SCENES_HARU = [
 ('A','WINDOW LIGHT','gentle Japanese neighborhood cafe window with a small believable drink on a sill'),
 ('B','LINEN & CURTAIN','light linen and sheer curtain, pale wood, modest ceramic cup in a small cafe'),
 ('C','LITTLE TABLE STORY','focused cafe beverage and exactly one subtle seasonal supporting object on a compact table'),
 ('D','LOCAL SEASONAL VIEW','intimate local Japanese street or terrace seen through a cafe window; seasonal atmosphere'),
]

@dataclass(frozen=True)
class Episode:
    no:str
    playlist_code:str
    situation:str
    main_text:str
    display_text:str
    emotional_line:str

    def as_input(self):
        values=(self.no,self.playlist_code,self.situation,self.main_text,self.display_text,self.emotional_line)
        return '\n'.join(f'{k}: {v}' for k,v in zip(FIELDS,values))


def parse_six_lines(text:str) -> Episode:
    """Pick LAST occurrence of every key, allowing entire masters and 6-line snippets."""
    found={}
    for line in text.splitlines():
        match=re.match(r'^\s*(NO|PLAYLIST_CODE|状況|MAIN_TEXT|DISPLAY_TEXT|EMOTIONAL_LINE)\s*[:：]\s*(.*?)\s*$',line)
        if match:
            found[match.group(1)]=match.group(2).strip()
    missing=[x for x in FIELDS if not found.get(x)]
    if missing: raise ValueError('6줄 입력 누락: '+', '.join(missing))
    for k in FIELDS:
        if re.search(r'\[[^\]]*\]|\{\{[^{}]*\}\}',found[k]):
            raise ValueError(f'{k}에 교체하지 않은 자리표시자가 있습니다.')
    no=found['NO'].strip()
    if not re.fullmatch(r'\d{1,5}',no):raise ValueError('NO는 숫자 1~5자리여야 합니다.')
    code=found['PLAYLIST_CODE'].upper().strip()
    if code not in FAMILIES:raise ValueError('PLAYLIST_CODE는 P01~P08이어야 합니다. 자동 추측하지 않습니다.')
    title=found['DISPLAY_TEXT']
    if '\n' in title or len(title)>100:raise ValueError('DISPLAY_TEXT는 한 줄 100자 이하로 입력하세요.')
    return Episode(no.zfill(3),code,found['状況'],found['MAIN_TEXT'],title,found['EMOTIONAL_LINE'])


def master_profile(text:str) -> str:
    s=text[:1600].lower()
    if 'haru little cafe' in s:return 'HARU'
    if "mio's morning" in s:return 'MIO'
    raise ValueError('Mio v11.2 또는 Haru v2.0 마스터인지 확인할 수 없습니다.')



# Small deterministic bilingual keyword glossary only; never substitute a guessed episode.
JP_SCENE_HINTS = (
    ('ミモザ','one realistic fresh mimosa stem with tiny yellow fluffy flowers'),
    ('藤','wisteria blossoms in delicate hanging lavender clusters'),
    ('桜','a small natural cherry blossom branch'),
    ('紅葉','one natural autumn foliage detail'),
    ('銀杏','golden ginkgo leaves'),
    ('雨','real visible raindrops on glass with luminous clouded daylight'),
    ('雪','bright soft snow outside the cafe window'),
    ('朝','early morning'),
    ('春','spring fresh air'),
    ('夏','summer fresh green foliage'),
    ('秋','autumn crispness'),
    ('冬','winter soft pale light'),
    ('曇','soft bright cloudy light'),
    ('窓','cafe window view'),
    ('読書','one book or journal'),
    ('花瓶','small believable clear glass vase'),
    ('クリスマス','single understated Christmas seasonal detail'),
)

def japanese_context_hints(situation:str) -> str:
    hints=[description for keyword,description in JP_SCENE_HINTS if keyword in situation]
    return '; '.join(hints) if hints else 'gentle neutral morning light without a strong seasonal motif'

def morning_prompts(brand:str,ep:Episode) -> list[dict]:
    if brand not in BRANDS:raise ValueError('지원되지 않는 채널')
    mood,palette,anchor=FAMILIES[ep.playlist_code]
    directions=SCENES_MIO if brand=='MIO' else SCENES_HARU
    results=[]
    for code,title,scene in directions:
        brand_dna=(
            'serene sophisticated airy morning editorial still-life, graceful space, sheer white curtain, clean fresh natural tones'
            if brand=='MIO' else
            'authentic intimate small Japanese neighborhood cafe, youthful tender warmth, handmade ceramics, soft linen, delicate everyday details'
        )
        prompt=(
            'Premium photoreal Japanese morning cafe photograph, NOT anime or illustration. '
            +brand_dna+'. Distinct independent composition '+code+': '+scene+'. '
            # Episode strings are NEVER pasted literally: Z-Image typesets quoted text
            # (2026-10-21 GPU test drew the Japanese mood line). Only English cues derived from them.
            +'Season and weather cues: '+japanese_context_hints(ep.situation)+'. '
            +'Visual family: '+mood+', restrained palette '+palette+', seasonal motif '+anchor+'. '
            +'Mandatory: one realistic cafe beverage on a believable table, counter or windowsill, genuine clear soft morning daylight. '
            +'Elegant subtle editorial still-life photography, 35mm film-inspired tonal rolloff, natural neutral white balance, true ceramic and linen texture, realistic sharp focal detail, 50mm f/2.2 look, calm atmosphere, gentle microcontrast, accurate geometry. '
            +'Subject mainly right/lower part, 45-60 percent serene unobstructed center-left title-safe area. Wide 16:9 landscape photograph. '
            +'NO visible person, hands, faces, crowd or silhouettes. NO text, glyphs, menus, signs, logos, watermarks, letters or numbers. '
            +'Avoid global blur, orange wash, artificial haze, heavy HDR, oversaturation, giant mugs, fake bokeh, floating objects, collage.'
        )
        results.append({'code':code,'title':title,'prompt':prompt})
    return results


def load_catalog(path:Path,brand:str) -> dict[str,Episode]:
    path=Path(path)
    if not path.exists():return {}
    obj=json.loads(path.read_text(encoding='utf-8-sig'))
    records=obj.get(brand,{}) if isinstance(obj,dict) else {}
    ans={}
    for no,value in records.items():
        if isinstance(value,dict):
            input_str='\n'.join(f'{field}: {value.get(field,"")}' for field in FIELDS)
        else:input_str=str(value)
        ans[str(int(no)).zfill(3)]=parse_six_lines(input_str)
    return ans


def save_catalog_episode(path:Path,brand:str,ep:Episode):
    path=Path(path)
    obj=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    obj.setdefault(brand,{})[ep.no]=dict(zip(FIELDS, (ep.no,ep.playlist_code,ep.situation,ep.main_text,ep.display_text,ep.emotional_line)))
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)


def import_catalog_json(path:Path,brand:str,dest:Path) -> int:
    """Import explicit 6-line entries; rejects missing stories; no invented lookups."""
    obj=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if isinstance(obj,dict) and 'episodes' in obj:obj=obj['episodes']
    if isinstance(obj,dict) and brand in obj:obj=obj[brand]
    if isinstance(obj,dict):obj=list(obj.values())
    if not isinstance(obj,list):raise ValueError('목록(JSON 배열) 형식이 아닙니다.')
    episodes=[]
    for item in obj:
        txt=item if isinstance(item,str) else '\n'.join(f'{key}: {item.get(key,"")}' for key in FIELDS)
        episodes.append(parse_six_lines(txt))
    for ep in episodes:save_catalog_episode(dest,brand,ep)
    return len(episodes)
