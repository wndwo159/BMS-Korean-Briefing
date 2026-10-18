from collections import Counter
import main
from offline_translation import OfflineTranslator
from military_terms import spans


def test_israel_print_reviewed_cells_preserve_identifiers():
    from offline_translation import reviewed_translation
    from briefing_render import metadata
    cases={
        'Hatzor ATIS':'Hatzor ATIS',
        'Hatzor Ground':'Hatzor 지상관제',
        'Tel Approach':'Tel 접근관제',
        'Tel Nof Tower':'Tel Nof 관제탑',
        'Unknown Base Departure':'Unknown Base 출항관제',
        'Clear sweep area of hostile aircraft':'소탕 구역 내 적기를 제거',
        '-- M-1992anti-aircraft guns over Al Bar Cape':'-- M-1992 대공포 · Al Bar Cape 일대',
        'Destroy Radar P-12or other facilities at target site':'Radar P-12 또는 표적 지역의 기타 시설을 파괴',
        'Tel Nof Airbase, 14 nm south of Tel Aviv':'Tel Nof Airbase, Tel Aviv 남쪽 14 nm',
        '2x Python-4':'2x Python-4',
        '4x Spice 2000':'4x Spice 2000',
        'Box':'상자 대형','Fair':'대체로 맑음',
        'Strike':'타격','OCA STRIKE':'공세 제공 타격(OCA STRIKE)',
        'Panther5 (OCA STRIKE)':'Panther5 (공세 제공 타격(OCA STRIKE))',
        '-- Radar EW Dome':'-- EW 레이더 돔',
        '100%operational':'100% 가동 중',
        'Intelligence reports the highest impact targets are:':'정보 보고에 따른 주요 타격 표적:',
    }
    for en,kr in cases.items():
        result=reviewed_translation(en,main.TOKEN,{})
        assert result==kr
        assert Counter(main.TOKEN.findall(en))==Counter(main.TOKEN.findall(result))
    meta=metadata('Mission Overview:\n\tPanther5 (OCA STRIKE)\n')
    assert meta['callsign']=='Panther5'
    assert meta['mission']=='OCA STRIKE'


def test_equipment_and_airfield_never_enter_neural_model():
    translator = OfflineTranslator.__new__(OfflineTranslator)
    translator.fragment = lambda text: (_ for _ in ()).throw(AssertionError(text))
    cases = {
        'Pyeongtaek AAF': '평택 육군비행장(AAF)',
        '6x AGM-65D Maverick': '6x AGM-65D 매버릭',
        '2x AIM-9M Sidewinder': '2x AIM-9M 사이드와인더',
        '2x AGM-65D UnknownWeapon': '2x AGM-65D UnknownWeapon',
        'Unknownfield AAF': 'Unknownfield AAF',
    }
    for text, expected in cases.items():
        output = translator.translate(text, main.TOKEN, {})
        assert output == expected
        assert Counter(main.TOKEN.findall(text)) == Counter(main.TOKEN.findall(output))


def test_shared_protection_keeps_duplicates_units_and_unknown_names():
    text = 'Sidewinder / Sidewinder 305.000 MHz Pyeongtaek AAF Unknownfield AAF'
    parts = list(spans(text, main.TOKEN, {}))
    values = [value for keep, value in parts if keep]
    assert values == ['사이드와인더', '사이드와인더', '305.000 MHz', '평택 육군비행장(AAF)', 'Unknownfield AAF']


def test_pilot_name_does_not_consume_next_table_cell():
    assert main.TOKEN.findall('2Lt. JoongJae Pilot\tUnassigned') == ['2Lt. JoongJae Pilot']


def test_remote_provider_also_protects_entire_unknown_loadout():
    assert list(spans('6x AGM-65D UnknownWeapon\t2x AIM-9M Sidewinder', main.TOKEN, {})) == [
        (True, '6x AGM-65D UnknownWeapon'), (False, '\t'), (True, '2x AIM-9M 사이드와인더')]


def test_dictionary_upgrade_reprocesses_same_source(tmp_path):
    engine=main.Engine(tmp_path/'data',opener=lambda url:None)
    engine.config.update(provider='test',output_dir=str(tmp_path/'out'),watch_dir=str(tmp_path/'in'),auto_open=False)
    source=tmp_path/'in'/'mission.html';source.parent.mkdir();source.write_text('<p>Maverick</p>','utf-8')
    engine.stable_read=lambda p:p.read_bytes()
    translated=[]
    engine.translate=lambda text:translated.append(text) or '매버릭'
    try:
        engine.process(source);count=len(translated)
        engine.process(source);assert len(translated)==count
        engine.db.execute("UPDATE translation_versions SET version='previous-dictionary'");engine.db.commit()
        engine.process(source);assert len(translated)>count
    finally:engine.close()


def test_inline_bms_label_uses_reviewed_dictionary():
    translator=OfflineTranslator.__new__(OfflineTranslator);translator.cache={}
    assert translator.fragment('Ext. Time Ref.: No')=='외부 시간 기준: 아니요'
    assert translator.fragment('Flt Lead: Yes')=='편대장: 예'


def test_reviewed_military_mistranslations_and_operational_data():
    from offline_translation import reviewed_translation
    cases={
        'No enemy air response is anticipated.':'적기의 대응은 예상되지 않습니다.',
        'Enemy Air':'적기',
        'Protect package elements from enemy aircraft':'적기로부터 패키지 소속 편대를 보호',
        'Osan Ground':'오산 지상관제',
        'Osan Tower':'오산 관제탑',
        'Pyeongtaek Approach':'평택 접근관제',
        'Pre IP':'IP 이전 지점','Turn Pt':'선회 지점',
        'Ladder':'계단 대형','ArrowHead':'화살촉 대형',
        '10deg C.':'10deg C. (섭씨)',
        'Key A: Day2 00:00z':'암호키 A: Day2 00:00z',
        'Rot/day:':'일일 코드 변경 횟수:',
    }
    for en,expected in cases.items():
        result=reviewed_translation(en,main.TOKEN,{})
        assert result==expected,(en,result)
        assert Counter(main.TOKEN.findall(result))==Counter(main.TOKEN.findall(en))


def test_reviewed_cells_apply_before_remote_model(tmp_path,monkeypatch):
    engine=main.Engine(tmp_path/'data',opener=lambda _:None)
    engine.config.update(provider='ollama',model='test')
    monkeypatch.setattr(main.httpx,'post',lambda *a,**k:(_ for _ in ()).throw(AssertionError('reviewed text must not reach the model')))
    try:
        output=engine.translate('Osan Ground\t253.700 MHz [2]\tNo enemy air response is anticipated.')
        assert output=='오산 지상관제\t253.700 MHz [2]\t적기의 대응은 예상되지 않습니다.'
    finally:engine.close()


def test_unreviewed_prose_still_requires_model():
    from offline_translation import reviewed_translation
    assert reviewed_translation('An unfamiliar briefing sentence.',main.TOKEN,{}) is None


def test_weather_situation_label_keeps_original():
    from briefing_render import render
    from bs4 import BeautifulSoup
    soup,_=main.parse(b'Weather:\n\tSituation:\tSunny\tSunny\tSunny\n')
    body,_=render(soup);doc=BeautifulSoup(body,'lxml')
    assert doc.select_one('td .kr').get_text()=='기상 상태:'
    assert doc.select_one('td .en').get_text()=='Situation:'
