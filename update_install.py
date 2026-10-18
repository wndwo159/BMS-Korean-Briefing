"""Installer-side handoff: wait for the old app, preserve data, recover on failure."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
import httpx
import psutil
from app_version import VERSION
from installer_core import install, validate_root, configure_launcher_watch


def perform(root, expected_version):
    if expected_version!=VERSION:raise ValueError('다운로드 버전과 설치 파일 버전이 다릅니다.')
    root,base=validate_root(root)
    manifest_path=base/'install.json'
    if not manifest_path.is_file():raise ValueError('기존 설치 정보를 찾을 수 없습니다.')
    previous=json.loads(manifest_path.read_text('utf-8'))
    if Path(previous['bms_root']).resolve()!=root:raise ValueError('기존 BMS 경로와 업데이트 경로가 다릅니다.')
    report=base/'data/updates/last-result.json';report.parent.mkdir(parents=True,exist_ok=True)
    rollback=base/'data/updates'/('rollback-'+str(time.time_ns()));rollback.mkdir()
    # Program assets only. Settings, history, models installed outside the program,
    # saved HTML, and original kneeboard backups never enter the replacement set.
    originals=[p for p in base.iterdir() if p.is_file() and p.suffix.lower() in ('.exe','.json','.ps1','.cmd','.txt','.html')]
    for p in originals:shutil.copy2(p,rollback/p.name)
    disabled=previous|{'launch_mode':'disabled'}
    manifest_path.write_text(json.dumps(disabled,ensure_ascii=False,indent=2),'utf-8')
    try:
        time.sleep(3)  # Allow the launcher detector to observe disabled mode.
        try:
            with httpx.Client(timeout=5) as c:
                health=c.get('http://127.0.0.1:8765/api/health').json()
                if Path(health.get('bms_root','')).resolve()==root:
                    c.post('http://127.0.0.1:8765/api/shutdown',headers={'Origin':'http://127.0.0.1:8765'})
        except (httpx.HTTPError,ValueError):pass
        expected=str((base/'BMS-Korean-Briefing.exe').resolve()).casefold()
        def ours():
            matches=[]
            for p in psutil.process_iter(['exe']):
                if (p.info.get('exe') or '').casefold()==expected:matches.append(p)
            return matches
        deadline=time.monotonic()+60
        while ours() and time.monotonic()<deadline:time.sleep(.3)
        remaining=ours()
        for p in remaining:p.terminate()
        psutil.wait_procs(remaining,timeout=10)
        if ours():raise RuntimeError('기존 브리핑 앱을 닫지 못했습니다. BMS 게임은 종료하지 않았습니다.')
        for attempt in range(5):
            try:install(root,integrate=False);break
            except RuntimeError:
                if attempt==4:raise
                time.sleep(2)
        current=json.loads(manifest_path.read_text('utf-8'))
        current['launch_mode']=previous.get('launch_mode','with-bms')
        manifest_path.write_text(json.dumps(current,ensure_ascii=False,indent=2),'utf-8')
        configure_launcher_watch(base,enabled=current['launch_mode']!='disabled')
        result={'ok':True,'version':VERSION,'message':'업데이트 설치 완료. 기존 설정과 브리핑 기록을 유지했습니다.'}
    except Exception as exc:
        for p in rollback.iterdir():shutil.copy2(p,base/p.name)
        configure_launcher_watch(base,enabled=previous.get('launch_mode')!='disabled')
        result={'ok':False,'version':VERSION,'message':'업데이트 실패로 이전 프로그램을 복원했습니다: '+str(exc)}
    staged=report.with_suffix('.tmp');staged.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');os.replace(staged,report)
    app=base/'BMS-Korean-Briefing-Viewer.exe'
    if app.is_file():subprocess.Popen([str(app)],cwd=base,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return result
