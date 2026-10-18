import json
from pathlib import Path
import entrypoint
import manual_launcher


def test_manual_viewer_closes_after_last_tab_heartbeat():
    ticks=[0];ended=[]
    class Stop:
        def wait(self,seconds):ticks[0]+=seconds;return ticks[0]>15
    entrypoint.monitor_viewer(lambda:False,lambda:[min(ticks[0],3)],lambda:ended.append(ticks[0]),Stop(),clock=lambda:ticks[0],idle=3)
    assert ended==[6]


def test_manual_viewer_remains_available_while_bms_runs():
    ticks=[0];ended=[]
    class Stop:
        def wait(self,seconds):ticks[0]+=seconds;return ticks[0]>15
    entrypoint.monitor_viewer(lambda:ticks[0]<8,lambda:[1],lambda:ended.append(ticks[0]),Stop(),clock=lambda:ticks[0],idle=3)
    assert ended==[8]


def test_manual_viewer_open_failure_does_not_leave_server_running():
    ticks=[0];ended=[]
    class Stop:
        def wait(self,seconds):ticks[0]+=seconds;return ticks[0]>15
    entrypoint.monitor_viewer(lambda:False,lambda:[],lambda:ended.append(ticks[0]),Stop(),clock=lambda:ticks[0],start_grace=4)
    assert ended==[4]


def test_small_launcher_opens_installed_viewer_not_game(tmp_path,monkeypatch):
    (tmp_path/'BMS-Korean-Briefing.exe').write_bytes(b'fixture')
    (tmp_path/'install.json').write_text('{}')
    monkeypatch.setattr(manual_launcher,'__file__',str(tmp_path/'manual_launcher.py'))
    calls=[];monkeypatch.setattr(manual_launcher.subprocess,'Popen',lambda args,**kwargs:calls.append(args))
    assert manual_launcher.run()==0
    assert calls==[[str(tmp_path/'BMS-Korean-Briefing.exe'),'--open-viewer']]


def test_existing_session_opens_browser_without_launching_bms(tmp_path,monkeypatch):
    manifest={'bms_root':str(tmp_path),'profiles':{}}
    (tmp_path/'install.json').write_text(json.dumps(manifest),'utf-8')
    monkeypatch.setattr(entrypoint,'executable_directory',lambda:tmp_path)
    monkeypatch.setattr(entrypoint,'acquire_lock',lambda path:None)
    calls=[];monkeypatch.setattr(entrypoint,'open_when_ready',lambda:calls.append('browser'))
    monkeypatch.setattr(entrypoint.subprocess,'Popen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Must not launch BMS')))
    assert entrypoint.run(['--open-viewer'])==0
    assert calls==['browser']
