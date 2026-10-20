import io
import json
import re
import zipfile
from pathlib import Path
import pytest
from PIL import Image
from story_image_studio.morning import (parse_six_lines,master_profile,morning_prompts,
                                        save_catalog_episode,load_catalog,import_catalog_json)
from story_image_studio.final_exports import export_final,archive_exact,SIZE_MAP,find_serif_font

FIXTURES=Path(__file__).resolve().parent/'fixtures'

@pytest.mark.parametrize('name,brand,no,title',[
    ('MIO_SYNTHETIC_MASTER.txt','MIO','905','Lilac Window'),
    ('HARU_SYNTHETIC_MASTER.txt','HARU','904','Rain on Glass'),
])
def test_uploaded_masters_parse(name,brand,no,title):
    content=(FIXTURES/name).read_text(encoding='utf-8')
    assert master_profile(content)==brand
    episode=parse_six_lines(content)
    assert episode.no==no and episode.display_text==title
    prompts=morning_prompts(brand,episode)
    assert [p['code'] for p in prompts]==list('ABCD')
    assert len(set(p['prompt'] for p in prompts))==4
    for p in prompts:
        text=p['prompt']
        # Z-Image typesets literal strings it is given (observed 2026-10-21: the Japanese
        # mood line appeared as garbled on-image text). No raw episode strings in prompts.
        assert not re.search(r'[぀-ヿ㐀-鿿]',text)
        for literal in (episode.situation,episode.emotional_line,episode.main_text,episode.display_text):
            assert literal not in text
        assert 'NO visible person' in text


def test_missing_number_catalog_error(tmp_path):
    ep=parse_six_lines((FIXTURES/'MIO_SYNTHETIC_MASTER.txt').read_text(encoding='utf-8'))
    where=tmp_path/'store.json'
    save_catalog_episode(where,'MIO',ep)
    assert load_catalog(where,'MIO')['905']==ep
    assert '906' not in load_catalog(where,'MIO')
    assert not load_catalog(where,'HARU')


def test_batch_catalog_import(tmp_path):
    data=[{'NO':str(n),'PLAYLIST_CODE':'P01','状況':'晴れの朝','MAIN_TEXT':'Quiet Spring','DISPLAY_TEXT':f'Morning {n}','EMOTIONAL_LINE':'静かな朝'} for n in (1,2,3)]
    path=tmp_path/'catalog_input.json';path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    stored=tmp_path/'library.json'
    assert import_catalog_json(path,'HARU',stored)==3
    assert len(load_catalog(stored,'HARU'))==3


def test_undefined_placeholders_fail():
    txt='NO: 001\nPLAYLIST_CODE: P01\n状況: [状況]\nMAIN_TEXT: A\nDISPLAY_TEXT: B\nEMOTIONAL_LINE: C'
    with pytest.raises(ValueError,match='자리표시자'):parse_six_lines(txt)


def test_no_bad_playlist_guess():
    txt='NO: 001\nPLAYLIST_CODE: P44\n状況: 春\nMAIN_TEXT: A\nDISPLAY_TEXT: B\nEMOTIONAL_LINE: C'
    with pytest.raises(ValueError,match='P01~P08'):parse_six_lines(txt)


def picture_bytes(seed):
    im=Image.new('RGB',(1024,576),seed)
    stream=io.BytesIO();im.save(stream,'PNG');return stream.getvalue()


def test_exact_four_standalone_jpg_and_zip(tmp_path):
    font=find_serif_font()
    paths=[]
    for index,code in enumerate('ABCD'):
        path=export_final(picture_bytes((224,230,235+index)),tmp_path,f'no004_{code}',
               size_label='YouTube 1280x720',fmt='JPG',brand_name='haru little cafe',
               display_text='Rain on Glass',font_path=str(font))
        paths.append(path)
        with Image.open(path) as im:
            assert im.size==SIZE_MAP['YouTube 1280x720']
            assert im.format=='JPEG'
            assert im.getpixel((145,360)) != (224,230,235+index) # overlay across text area
    zipname=archive_exact(paths,tmp_path,'HARU_LITTLE_CAFE_no004_ABCD.zip')
    with zipfile.ZipFile(zipname) as z:
        assert z.namelist()==[f'no004_{code}.jpg' for code in 'ABCD']
    assert len(list(tmp_path.glob('*.jpg')))==4
    assert len(list(tmp_path.glob('*.png')))==0


def test_final_story_jpg_and_4k_size(tmp_path):
    path=export_final(picture_bytes((80,70,60)),tmp_path,'no001',size_label='4K 3840x2160',fmt='JPG')
    with Image.open(path) as im:
        assert im.size==(3840,2160)
    assert sorted(x.name for x in tmp_path.iterdir())==['no001.jpg']


def test_four_or_nothing_zip(tmp_path):
    paths=[]
    for number in range(3):
        paths.append(export_final(picture_bytes((number*30,99,100)),tmp_path,f'no{number+1:03}',size_label='YouTube 1280x720'))
    with pytest.raises(ValueError,match='정확히 4장'):archive_exact(paths,tmp_path)
    assert not list(tmp_path.glob('*.zip'))


def test_font_required_unknown(tmp_path):
    with pytest.raises(ValueError,match='세리프'):find_serif_font(str(tmp_path/'missing.ttf'))
