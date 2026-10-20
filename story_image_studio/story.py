"""Offline story extraction from Suno lyric JSON. No paid LLM needed."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import re
from pathlib import Path

PHASES = [
    ('01', '도입', 'Opening — recognition'),
    ('02', '전개', 'Development — choosing to stay'),
    ('03', '절정', 'Climax — emotions deepen'),
    ('04', '결말', 'Ending — a gentle goodbye'),
]
VISUAL_STYLE = {
    'anime': 'masterpiece, best quality, very aesthetic, high-quality anime film still, premium Japanese theatrical romance anime key visual, refined character design, sharp clean purposeful linework, expressive detailed eyes, individually rendered hair locks, detailed costumes and fabric folds, layered hand-painted scenery, polished cel shading, luminous but controlled cinematic lighting, natural human proportions, crisp facial silhouettes, professional anime feature-film finish',
    'realistic': 'cinematic professional 35mm film photography, realistic human anatomy, natural skin texture, Kodak Portra 400, elegant shallow depth of field, subtle grain, optical bokeh, sophisticated color grading',
}
# These are scene-first vocabulary cues. They supplement JSON's explicit story fields.
SCENES = [
    ('street fair', 'a busy autumn street fair, colorful stalls and a path of golden ginkgo leaves'),
    ('market', 'a cozy outdoor market surrounded by autumn ginkgo trees'),
    ('ginkgo', 'golden ginkgo trees lining a Japanese pedestrian street'),
    ('bus', 'a quiet Japanese bus stop next to the evening market'),
    ('lantern', 'lanterns and wooden stalls on a street at dusk'),
    ('crossing', 'a golden crosswalk beneath autumn trees'),
    ('bench', 'a quiet hilltop bench above the city at twilight'),
    ('chestnut', 'a last roasted chestnut stall beside the closing market'),
    ('train', 'a Japanese train platform under a bright open sky'),
    ('cafe', 'a cozy Japanese cafe beside a sunlit window'),
    ('bridge', 'a small bridge along a golden tree-lined street'),
    ('book', 'a vintage book stall at an outdoor market'),
    ('maple', 'a winding path under red maple trees'),
]

@dataclass
class Scene:
    number: str
    phase: str
    title: str
    track_numbers: list[int]
    track_titles: list[str]
    narrative: str
    lyric_signals: list[str]
    prompt: str
    negative: str

    def to_dict(self) -> dict:
        return asdict(self)


def load_json(path: str | Path) -> dict:
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            obj = json.load(f)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'JSON 파일을 읽을 수 없습니다: {exc}') from exc
    if not isinstance(obj, dict) or not isinstance(obj.get('songs'), list) or not obj['songs']:
        raise ValueError('이 파일에서 songs 배열을 찾을 수 없습니다.')
    for idx, song in enumerate(obj['songs'], 1):
        if not isinstance(song, dict) or not (song.get('lyrics') or song.get('centralImage') or song.get('lyricThemeText')):
            raise ValueError(f'{idx}번 곡에 가사 또는 장면 정보가 없습니다.')
    return obj


def get_tracks(data: dict) -> list[dict]:
    songs = data['songs']
    # Keep track order where available; unlike vocal roles, tracks are a timeline.
    return sorted(songs, key=lambda s: int(s.get('trackNo') or songs.index(s) + 1))


def track_splits(tracks: list[dict]) -> list[list[dict]]:
    # 15-song sets use the series' 3/4/5/3 story arc split.
    n = len(tracks)
    if n == 15:
        cuts = [3, 7, 12, 15]
    else:
        cuts = [max(1, round(n*.20)), max(2, round(n*.47)), max(3, round(n*.80)), n]
        cuts = sorted(set([min(n, max(1, v)) for v in cuts]))
        # Ensure exactly four scenes even for n<4 by leaving some ranges empty.
        while len(cuts) < 4:
            cuts.insert(-1, cuts[-2] if len(cuts)>1 else 0)
        cuts = cuts[:3] + [n]
    output = []
    start = 0
    for cut in cuts:
        output.append(tracks[start:cut])
        start = cut
    return output


def _lyric_signal(song: dict) -> str:
    """Extract sung story words, not studio instructions and technical [tags]."""
    raw = song.get('lyrics') or ''
    raw = re.sub(r'\[[^]]*\]', '', raw)
    lines = [line.strip(' /\t') for line in raw.splitlines() if line.strip()]
    # Keep verse lines that describe concrete actions, bypass formal chorus hook repetition.
    triggers = ('leaf', 'stalls', 'crowd', 'bus', 'lantern', 'market', 'walk', 'hill', 'bench',
                'street', 'map', 'chestnut', 'name', 'laugh', 'look', 'book', 'cross', 'light',
                'goodbye', 'song', 'train', 'smile', 'window', 'hands')
    for line in lines:
        if any(word in line.lower() for word in triggers) and len(line) < 85:
            return line
    return next((x[:80] for x in lines if len(x) < 90), '')


def _extract_location(chunks: list[dict], fallback: str) -> str:
    text = ' '.join(str(x.get(k, '')) for x in chunks for k in
                    ('centralImage', 'listenerSituation', 'lyricThemeText', 'lyrics')).lower()
    for keyword, location in SCENES:
        if keyword in text:
            return location
    return fallback


def _role_text(channel: str, phase: int) -> str:
    base = 'two fictional Japanese young adults in their early twenties, the same recurring man and woman, natural proportions'
    if channel == '남자':
        return base + '; man is the clear foreground protagonist, his perspective and subtle emotion lead the scene, woman is supporting co-star'
    if channel == '여자':
        return base + '; woman is the clear foreground protagonist, her perspective and subtle emotion lead the scene, man is supporting co-star'
    return base + '; both protagonists have equal presence, visually intimate but respectful and naturally posed'


def build_scenes(data: dict, channel: str = '남녀', style: str = 'anime',
                 reference_hint: str = '', scene_anchors: list[str] | None = None) -> list[Scene]:
    """Four scenes. Episode-specific direction comes from data, never from code:
    explicit ``scene_anchors`` (e.g. a private local file) > ``meta.sceneAnchors`` > generic."""
    if channel not in ('남자','여자','남녀'):
        raise ValueError('채널은 남자, 여자, 남녀 중 선택하세요.')
    if style not in VISUAL_STYLE:
        raise ValueError('지원하지 않는 스타일입니다.')
    tracks = get_tracks(data)
    grouped = track_splits(tracks)
    meta = data.get('meta') or {}
    arc = meta.get('seasonArc') or []
    boundary = meta.get('continuityBoundary') or {}
    episode_title = meta.get('episodeTitleJapanese') or meta.get('episodeTitle') or meta.get('conceptLabel') or 'Romantic story'
    story = meta.get('episodeStoryJapanese') or meta.get('episodeStory') or ''
    story = re.sub(r'\s+', ' ', story).strip()
    boundary_exclude = boundary.get('mustNotHappen') or ''
    default_locations = [
        'a lively street in early autumn, first unexpected encounter among passersby',
        'a picturesque Japanese pedestrian market with golden ginkgo leaves',
        'a quiet autumn walkway at evening, warm shop lights and blue hour sky',
        'the same street after the market closes, calm night lights and gentle farewell',
    ]
    general_anchors = [
        'Opening scene: the first story event, introduce the protagonists and relationship tension.',
        'Development: the protagonists take a small action that extends their shared journey.',
        'Emotional peak: a quieter moment that reveals a subtle shift in their feelings.',
        'Ending: the final concrete event, preserve the story’s actual ending without inventing new milestones.',
    ]
    anchors = scene_anchors if scene_anchors is not None else meta.get('sceneAnchors')
    if anchors is None:
        anchors = general_anchors
    if not isinstance(anchors, list) or len(anchors) != 4 or not all(isinstance(a, str) and a.strip() for a in anchors):
        raise ValueError('sceneAnchors는 비어 있지 않은 문장 4개여야 합니다.')
    result = []
    for i, (phase, group) in enumerate(zip(PHASES, grouped)):
        number, ko, en = phase
        group_numbers = [int(x.get('trackNo',0) or 0) for x in group]
        group_titles = [str(x.get('title','')) for x in group]
        seeds = [str(x.get('centralImage') or x.get('lyricThemeText') or x.get('listenerSituation') or '').strip() for x in group]
        seeds = [x for x in seeds if x]
        signals = [_lyric_signal(x) for x in group]
        signals = [x for x in signals if x]
        scene_summary = (arc[i] if len(arc) > i else '')
        anchor = anchors[i]
        keyword_location = _extract_location(group, default_locations[i])
        # Scene-first structure; avoid multi-thousand-character instructions that can
        # drown out the story and weaken anime-model prompt adherence.
        evidence='; '.join(seeds[:2])[:165]
        role=_role_text(channel,i)
        mood=str(group[-1].get('emotionArc') or 'quiet growing warmth') if group else 'quiet growing warmth'
        style_intro=(
            'masterpiece, best quality, very aesthetic, cinematic anime feature-film still, '
            'crisp linework, polished faces, refined eyes and hair, cel shading, detailed painted background'
            if style=='anime' else
            'cinematic realistic film photograph, natural human faces, Kodak Portra 400, detailed sunlight'
        )
        design=('Fixed protagonist design: '+reference_hint.strip()[:190]+'. ') if reference_hint.strip() else ''
        continuity='No confession, kissing, holding hands, or relationship labels.' if boundary_exclude else ''
        prompt=(
            f'{style_intro}. 16:9 cinematic frame. {anchor} '
            f'People: {role}. {design}'
            f'Emotion: {mood}. Story evidence: {evidence}. '
            'Sharp facial features, complete uncropped heads, accurate hands, believable anatomy, '
            'well-drawn architecture, clean coherent shadows, distinct camera angles across the four scenes. '
            'Leave modest calm negative space toward left for YouTube title; no written text, no watermark. '
            +continuity
        ).strip()
        negative=('worst quality, low quality, normal quality, lowres, blurry, jpeg artifacts, '
                  'bad anatomy, malformed hands, extra fingers, duplicate people, cropped face, '
                  'unreadable clutter, logos, watermarks, printed captions, garbled signs. ')
        if boundary_exclude:
            negative+='Exclude forbidden story events: '+boundary_exclude[:340]
        result.append(Scene(number, ko, en, group_numbers, group_titles,
                            f'{scene_summary}. {anchor}' if scene_summary else anchor,
                            signals[:4], prompt, negative))
    return result


def reference_edit_prompt(scene: Scene, roles: list[str]) -> str:
    """Instruction prompt for multi-reference edit models (FLUX.2 Klein).

    ``roles`` is the order the identity images enter the graph, e.g. ['male','female'],
    so the prompt can bind "image 1"/"image 2" to the right person. Each reference
    is used for identity only; the scene, pose and background come from the story.
    """
    who = {'male': 'the young man', 'female': 'the young woman'}
    binds = [f'{who[r]} is exactly the person in image {i}: same face, eyes, hairstyle, hair colour, '
             f'outfit and art style' for i, r in enumerate(roles, 1) if r in who]
    if not binds:
        raise ValueError('레퍼런스 역할(male/female)이 필요합니다.')
    people = 'exactly two people, one man and one woman' if len(binds) == 2 else 'the referenced person as protagonist'
    return (
        'Create a NEW single 16:9 anime film still in the same painted anime style as the reference images. '
        + '; '.join(binds) + '. '
        f'Do not copy the reference poses, framing or backgrounds. Scene: {scene.narrative} '
        f'Show {people}, no other main characters; background passers-by small and soft if needed. '
        'One continuous frame, not a collage, triptych or split screen. Natural anatomy and hands, '
        'complete heads, no text, no captions, no watermark. '
        # Measured 2026-10-21: adding "blank signs, no lettering" here produced MORE garbled
        # signage (cfg=1, no negative prompt: negations prime the concept). Do not re-add.
        + ('No confession, kissing, holding hands, or relationship labels.' if 'No confession' in scene.prompt else '')
    ).strip()


def summary(data: dict) -> dict:
    s = get_tracks(data)
    counts = {'남자':0,'여자':0,'듀엣':0}
    for song in s:
        role = str(song.get('vocalType') or song.get('storyPOV') or '').lower()
        if 'duet' in role or '듀엣' in role: counts['듀엣']+=1
        elif 'female' in role or '여자' in role: counts['여자']+=1
        elif 'male' in role or '남자' in role: counts['남자']+=1
    meta = data.get('meta') or {}
    return {'episode': meta.get('episodeNo','?'), 'title': meta.get('episodeTitle',''),
            'song_count':len(s), 'vocal_roles':counts}
