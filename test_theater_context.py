from pathlib import Path
from bs4 import BeautifulSoup
import main
import theater_context as theater


def test_theater_variants_and_unknown():
    assert theater.describe('Israel')['code']=='ISRAEL'
    assert theater.describe('Korea KTO')['code']=='KTO'
    assert theater.describe('KTO 80s revamp 4.38')['name']=='KTO 80s revamp 4.38'
    assert theater.describe('Balkans')['code']=='BALKANS'
    assert theater.describe('')['source']=='unknown'


def test_context_survives_offline_html_without_script_injection():
    context=theater.describe('Israel " <script>alert(1)</script>')
    markup=theater.marker(context)
    assert not BeautifulSoup(markup,'html.parser').select('script')
    assert theater.saved(markup)==context
    assert theater.saved('<article>Legacy briefing</article>')['source']=='unknown'


def test_saved_theater_does_not_change_with_current_selection(tmp_path,monkeypatch):
    engine=main.Engine(tmp_path/'data',opener=lambda _:None)
    source=tmp_path/'in'/'briefing.txt';source.parent.mkdir()
    source.write_text('Mission Overview:\n\tPanther5 (OCA STRIKE)\n',encoding='utf-8')
    engine.config.update(watch_dir=str(source.parent),output_dir=str(tmp_path/'out'),auto_open=False)
    engine.stable_read=lambda p:p.read_bytes()
    engine.translate=lambda text:text
    monkeypatch.setattr(main,'current_theater',lambda _:theater.describe('Israel'))
    try:
        engine.process(source)
        path=next((tmp_path/'out').glob('*_KR.html'))
        assert theater.saved(path.read_text('utf-8'))['code']=='ISRAEL'
        monkeypatch.setattr(main,'current_theater',lambda _:theater.describe('Korea KTO'))
        engine.state['html']=''
        engine.process(source)
        assert engine.state['meta']['theater']['code']=='ISRAEL'
        engine.forced.add(str(source.resolve()))
        engine.process(source)
        assert engine.state['meta']['theater']['code']=='ISRAEL'
    finally:engine.close()
