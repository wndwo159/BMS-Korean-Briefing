import json
from contextlib import contextmanager
import threading
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
import main
import ollama_manager as om


def test_legacy_argos_selection_migrates_to_bundled_model(tmp_path):
    (tmp_path/'settings.json').write_text(json.dumps({'provider':'argos','notify':True}),'utf-8')
    engine=main.Engine(tmp_path,opener=lambda url:None)
    try:
        assert engine.config['provider']=='offline' and engine.config['notify']
        assert json.loads((tmp_path/'settings.json').read_text('utf-8'))['provider']=='offline'
    finally:engine.close()


def test_status_distinguishes_unavailable_runtime_and_installed_models(monkeypatch):
    manager=om.Manager();monkeypatch.setattr(om,'executable',lambda:None)
    monkeypatch.setattr(om.httpx,'get',lambda *a,**k:(_ for _ in ()).throw(httpx.ConnectError('offline')))
    assert manager.status('http://127.0.0.1:11434')['reachable'] is False
    monkeypatch.setattr(om.httpx,'get',lambda *a,**k:httpx.Response(200,json={'models':[{'name':'translategemma:4b','size':3300000000}]},request=httpx.Request('GET',a[0])))
    status=manager.status('http://127.0.0.1:11434')
    assert status['reachable'] and status['models'][0]['name']=='translategemma:4b'
    with pytest.raises(ValueError):manager.status('http://example.com:11434')


def test_pull_stream_reports_completion_and_errors(monkeypatch):
    events=[{'status':'pulling layer','total':100,'completed':40},{'status':'success'}]
    @contextmanager
    def stream(*a,**k):
        yield httpx.Response(200,content='\n'.join(json.dumps(e) for e in events),request=httpx.Request('POST',a[1]))
    monkeypatch.setattr(om.httpx,'stream',stream)
    manager=om.Manager();manager.pull('http://127.0.0.1:11434','translategemma:4b');manager.worker.join(2)
    assert manager.snapshot()['state']=='complete' and manager.snapshot()['percent']==100
    events[:]=[{'error':'not enough disk space'}]
    manager.pull('http://127.0.0.1:11434','translategemma:4b');manager.worker.join(2)
    assert manager.snapshot()['state']=='error' and 'disk space' in manager.snapshot()['error']
    with pytest.raises(ValueError):manager.pull('http://127.0.0.1:11434','unknown:latest')


def test_cancel_and_duplicate_download(monkeypatch):
    entered=threading.Event();released=threading.Event()
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def raise_for_status(self):pass
        def iter_lines(self):entered.set();released.wait(2);yield '{"status":"success"}'
        def close(self):released.set()
    monkeypatch.setattr(om.httpx,'stream',lambda *a,**k:Response())
    manager=om.Manager();manager.pull('http://127.0.0.1:11434','translategemma:4b');assert entered.wait(2)
    with pytest.raises(ValueError):manager.pull('http://127.0.0.1:11434','translategemma:12b')
    manager.cancel_pull();manager.worker.join(2);assert manager.snapshot()['state']=='cancelled'


def test_model_selection_requires_installed_model_and_post_origin(tmp_path,monkeypatch):
    engine=main.Engine(tmp_path,opener=lambda url:None);monkeypatch.setattr(main,'engine',engine)
    monkeypatch.setattr(main.ollama_manager,'status',lambda url:{'reachable':True,'models':[{'name':'translategemma:4b'}]})
    client=TestClient(main.app);headers={'Origin':'http://127.0.0.1:8765'}
    try:
        assert client.post('/api/ollama/pull',json={'model':'translategemma:4b'}).status_code==403
        assert client.post('/api/settings',json={'provider':'ollama','model':''},headers=headers).status_code==400
        assert client.post('/api/settings',json={'provider':'ollama','model':'missing'},headers=headers).status_code==400
        assert client.post('/api/settings',json={'provider':'ollama','model':'translategemma:4b'},headers=headers).status_code==200
    finally:engine.close()


def test_translategemma_uses_translation_prompt_and_protects_data(tmp_path,monkeypatch):
    engine=main.Engine(tmp_path,opener=lambda url:None);engine.config.update(provider='ollama',model='translategemma:4b')
    def post(url,**kwargs):
        assert url.endswith('/api/chat')
        body=kwargs['json'];prompt=body['messages'][0]['content'];assert '\n\n\n' in prompt and 'Korean (ko)' in prompt
        assert 'Pyeongtaek AAF' not in prompt
        return httpx.Response(200,json={'message':{'content':'__BMS_0__ 방어'}},request=httpx.Request('POST',url))
    monkeypatch.setattr(main.httpx,'post',post)
    try:assert engine.translate('Defend Pyeongtaek AAF')=='평택 육군비행장(AAF) 방어'
    finally:engine.close()
