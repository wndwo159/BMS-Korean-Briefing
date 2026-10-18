from pathlib import Path
import time
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
import main

SAMPLE=b'<html><body><h1>Mission</h1><table><tr><td>Departure 20:23:55Z 305.000 MHz 42X FL250 25 NM STPT 15 GBU-12</td><td>Attack target</td></tr></table><script>alert(1)</script><a href="javascript:alert(1)" onclick="x()">Link</a></body></html>'

def make(tmp_path):
    e=main.Engine(tmp_path/'app',opener=lambda url:None)
    source=tmp_path/'in'; source.mkdir();out=tmp_path/'out'
    e.config.update(watch_dir=str(source),output_dir=str(out))
    return e,source,out

def test_parse_integrity():
    soup,nodes=main.parse(SAMPLE)
    assert len(soup.select('tr'))==1 and len(soup.select('td'))==2
    assert not soup.select('script,[href],[onclick]')
    for token in ['20:23:55Z','305.000 MHz','42X','FL250','25 NM','STPT 15','GBU-12']:
        assert token in soup.get_text()

def test_save_failure_duplicate_update_restart(tmp_path):
    e,source,out=make(tmp_path);opened=[];e.opener=opened.append
    p=source/'mission.html';p.write_bytes(SAMPLE)
    e.translate=lambda text: (_ for _ in ()).throw(ValueError('offline'))
    e.process(p);files=list(out.glob('*_KR.html'));assert len(files)==1
    assert p.read_bytes()==SAMPLE
    data=files[0].read_text('utf-8');assert 'error' in data and 'GBU-12' in data and '.en' in data
    e.process(p);assert len(opened)==1
    e.clients['test']=time.monotonic();p.write_bytes(SAMPLE.replace(b'Mission',b'Mission Two'));e.process(p)
    assert len(opened)==1 and len(list(out.glob('*_KR.html')))==1
    assert 'Mission Two' in files[0].read_text('utf-8')
    e.close();assert files[0].read_text('utf-8').startswith('<!doctype html>')
    e2=main.Engine(tmp_path/'app',opener=opened.append);e2.config.update(watch_dir=str(source),output_dir=str(out));e2.process(p);assert len(opened)==1
    assert 'Mission Two' in e2.snapshot()['html']
    assert e2.snapshot()['sections']
    e2.close()

def test_watchdog_end_to_end(tmp_path):
    e,source,out=make(tmp_path);e.config['provider']='test';e.translate=lambda t:'번역 '+t;e.start()
    p=source/'print.html';p.write_bytes(SAMPLE)
    deadline=time.monotonic()+12
    while time.monotonic()<deadline and not list(out.glob('*_KR.html')):time.sleep(.1)
    assert len(list(out.glob('*_KR.html')))==1
    assert '번역' in next(out.glob('*_KR.html')).read_text('utf-8')
    assert e.snapshot()['done']==e.snapshot()['total']
    e.close();assert not e.worker.is_alive();assert not e.observer.is_alive()

def test_translation_validation_and_cache(tmp_path,monkeypatch):
    e,_,_=make(tmp_path);e.config.update(provider='ollama',model='test')
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'response':'{"id":"text","translation":"출발 __BMS_0__"}'}
    monkeypatch.setattr(main.httpx,'post',lambda *a,**k:Response())
    assert e.translate('Departure 42X')=='출발 42X'
    monkeypatch.setattr(main.httpx,'post',lambda *a,**k: (_ for _ in ()).throw(RuntimeError()))
    assert e.translate('Departure 42X')=='출발 42X'
    import pytest
    with pytest.raises(RuntimeError):e.translate('Other 42X')
    e.close()

def test_api():
    with TestClient(main.app) as c:
        assert c.get('/').status_code==200
        assert c.get('/api/state').status_code==200
        assert c.post('/api/settings',json={}).status_code==403

def test_real_bms_text_read_only():
    p=Path(r'B:\Falcon BMS 4.38\User\Briefings\briefing.txt')
    if not p.exists():return
    raw=p.read_bytes();soup,nodes=main.parse(raw)
    text=main.UnicodeDammit(raw).unicode_markup
    assert soup.body.get_text()==text
    assert len(nodes)>10
    assert p.read_bytes()==raw

def test_offline_real_translation_and_protection(tmp_path):
    import re
    from collections import Counter
    e,_,_=make(tmp_path);e.config['provider']='offline'
    source='Departure 20:23:55Z 305.000 MHz 42X FL250 25 NM STPT 15 GBU-12'
    translated=e.translate(source)
    assert '출발' in translated
    assert Counter(main.TOKEN.findall(source))==Counter(main.TOKEN.findall(translated))
    narrative='Be advised: Starting at 10:00:00, our ground forces will be making a major push towards Kaesong.'
    assert '대규모 진격' in e.translate(narrative)
    assert e.translate('Maj. Ha')=='Maj. Ha'
    # This sentence is not in the BMS dictionary or reviewed templates: exercise neural inference.
    assert re.search('[가-힣]',e.translate('The flight must avoid dangerous clouds.'))
    e.close()

def test_render_sections_tables_and_offline_document():
    from briefing_render import render
    source=b'Mission Overview:\n\tCallsign:\tTask:\n\tBanshee2\tSEAD\nWeather:\n\tWind:\t348deg@ 5kts.\nUnknown New Section:\n\tMore content\n'
    soup,nodes=main.parse(source);body,sections=render(soup)
    assert len(sections)==3
    assert sections[-1]['source']=='Unknown New Section'
    output=BeautifulSoup(main.document(body,'완료'),'lxml')
    assert len(output.select('table'))==2
    assert output.find('style') and not output.select('link,script[src]')
    content=BeautifulSoup(output.select_one('#briefing-source').decode_contents(),'lxml')
    for token in ['Banshee2','SEAD','348deg','5kts.','More content']:
        assert token in content.get_text()

def test_korean_adjacent_numeric_boundaries():
    assert main.TOKEN.findall('10:00:00부터 30 km이내 FLOT로부터')==['10:00:00','30 km','FLOT']

def test_real_bms_all_lines_offline(tmp_path):
    from collections import Counter
    p=Path(r'B:\Falcon BMS 4.38\User\Briefings\briefing.txt')
    if not p.exists():return
    raw=p.read_bytes();_,nodes=main.parse(raw);e,_,_=make(tmp_path);e.config['provider']='offline'
    for _,source in nodes:
        translated=e.translate(source)
        assert Counter(main.TOKEN.findall(source))==Counter(main.TOKEN.findall(translated)),source
    assert p.read_bytes()==raw
    e.close()


def test_bms_session_ignores_previous_print_until_new_write(tmp_path,monkeypatch):
    monkeypatch.setenv('BMS_KR_PRINT_ONLY','1')
    e,source,out=make(tmp_path);e.config['provider']='test';e.translate=lambda t:'번역 '+t
    p=source/'briefing.txt';p.write_bytes(b'Mission Overview:\n\tPrevious mission\n')
    e.start()
    deadline=time.monotonic()+3
    while time.monotonic()<deadline and not e.seen:time.sleep(.05)
    assert not out.exists()
    p.write_bytes(b'Mission Overview:\n\tNew PRINT mission\n')
    deadline=time.monotonic()+8
    while time.monotonic()<deadline and not list(out.glob('*_KR.html')):time.sleep(.1)
    assert len(list(out.glob('*_KR.html')))==1
    e.close()
