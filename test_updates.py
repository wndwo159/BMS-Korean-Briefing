import hashlib
import json
from pathlib import Path
import httpx
import pytest
import updater
import update_install

REPO='wndwo159/BMS-Korean-Briefing'
PAYLOAD=b'MZ'+b'checked-installer'*30

def release(data=PAYLOAD, **changes):
    value={'tag_name':'v0.4.0','draft':False,'prerelease':False,'body':'새 기능', 'assets':[{'name':updater.ASSET,'browser_download_url':f'https://github.com/{REPO}/releases/download/v0.4.0/{updater.ASSET}','size':len(data),'digest':'sha256:'+hashlib.sha256(data).hexdigest()}]}
    value.update(changes);return value

def manager(tmp_path, body=PAYLOAD, metadata=None, status=200):
    def handler(request):
        if request.url.host=='api.github.com':return httpx.Response(status,json=metadata or release())
        return httpx.Response(200,content=body)
    factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(handler),**kw)
    launched=[]
    m=updater.Manager(tmp_path/'data',tmp_path/'BMS',launch=lambda p,v:launched.append((p,v)),client_factory=factory)
    manifest=m.root/'User/Plugins/BMS-Korean-Briefing/install.json';manifest.parent.mkdir(parents=True);manifest.write_text('{}')
    return m,launched

def test_verified_download_only_executes_complete_installer(tmp_path):
    m,launched=manager(tmp_path);m._check();assert m.snapshot()['available']
    m._download(m.latest)
    assert m.snapshot()['phase']=='installing' and len(launched)==1
    assert launched[0][0].read_bytes()==PAYLOAD
    assert not list(m.home.rglob('*.part'))

@pytest.mark.parametrize('body',[b'MZtampered',b'not-executable'])
def test_bad_download_never_executes(tmp_path,body):
    metadata=release(body) if body==b'not-executable' else release()
    m,launched=manager(tmp_path,body,metadata);m._check();m._download(m.latest)
    assert m.snapshot()['phase']=='error' and not launched
    assert not list(m.home.rglob('*.part'))

def test_cancel_leaves_program_alone(tmp_path):
    m,launched=manager(tmp_path);m._check();m.stop.set();m._download(m.latest)
    assert m.snapshot()['phase']=='cancelled' and not launched

@pytest.mark.parametrize('change',[{'prerelease':True},{'tag_name':'latest'}, {'assets':[]}])
def test_unsupported_release_rejected(change):
    with pytest.raises(ValueError):updater.release_info(REPO,release(**change))

def test_foreign_download_url_and_missing_checksum_rejected():
    value=release();value['assets'][0]['browser_download_url']='https://example.com/Setup.exe'
    with pytest.raises(ValueError):updater.release_info(REPO,value)
    value=release();value['assets'][0].pop('digest')
    with pytest.raises(ValueError):updater.release_info(REPO,value)

def test_same_version_and_missing_release(tmp_path):
    value=release();value['tag_name']='v'+updater.VERSION
    value['assets'][0]['browser_download_url']=f'https://github.com/{REPO}/releases/download/v{updater.VERSION}/{updater.ASSET}'
    m,_=manager(tmp_path,metadata=value);m._check();assert not m.snapshot()['available']
    m,_=manager(tmp_path/'missing',status=404);m._check();assert not m.snapshot()['available']
    assert '정식 배포' in m.snapshot()['message']

def test_update_failure_restores_program_preserves_settings(tmp_path,monkeypatch):
    root=tmp_path/'BMS';game=root/'Bin/x64/Falcon BMS.exe';game.parent.mkdir(parents=True);game.write_bytes(b'game')
    base=root/'User/Plugins/BMS-Korean-Briefing';base.mkdir(parents=True)
    (base/'install.json').write_text(json.dumps({'bms_root':str(root),'launch_mode':'with-bms'}))
    exe=base/'BMS-Korean-Briefing.exe';exe.write_bytes(b'old-program')
    settings=base/'data/settings.json';settings.parent.mkdir();settings.write_text('user-settings')
    def failed(*args,**kwargs):exe.write_bytes(b'partial-new-program');raise RuntimeError('locked')
    monkeypatch.setattr(update_install,'install',failed)
    monkeypatch.setattr(update_install,'configure_launcher_watch',lambda *a,**k:None)
    monkeypatch.setattr(update_install.time,'sleep',lambda *_:None)
    monkeypatch.setattr(update_install.psutil,'process_iter',lambda *_:[])
    class NoServer:
        def __init__(self,**kw):pass
        def __enter__(self):raise httpx.ConnectError('offline')
        def __exit__(self,*args):pass
    monkeypatch.setattr(update_install.httpx,'Client',NoServer)
    result=update_install.perform(root,updater.VERSION)
    assert not result['ok'] and exe.read_bytes()==b'old-program'
    assert settings.read_text()=='user-settings'
    assert json.loads((base/'install.json').read_text())['launch_mode']=='with-bms'

def test_version_order_is_numeric():
    assert updater.version_tuple('v0.10.0')>updater.version_tuple('0.9.9')
