"""GitHub stable-release updates; only verified installers are executed."""
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
import httpx
from app_version import VERSION

ASSET = 'BMS-Korean-Briefing-Setup.exe'


def version_tuple(value):
    m=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',value or '')
    if not m:raise ValueError('정식 버전 번호가 올바르지 않습니다.')
    return tuple(map(int,m.groups()))


def release_info(repo, release):
    if release.get('draft') or release.get('prerelease'):raise ValueError('시험 배포는 자동 업데이트하지 않습니다.')
    tag=release.get('tag_name','');version_tuple(tag)
    asset=next((a for a in release.get('assets',[]) if a.get('name')==ASSET),None)
    if not asset:raise ValueError('이 버전의 Windows 설치 파일이 아직 준비되지 않았습니다.')
    url=asset.get('browser_download_url','')
    prefix=f'https://github.com/{repo}/releases/download/{tag}/'
    if url != prefix+ASSET:raise ValueError('업데이트 파일 출처가 올바르지 않습니다.')
    digest=asset.get('digest','')
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}',digest):raise ValueError('GitHub 파일 검증 정보가 없어 설치를 중단했습니다.')
    size=asset.get('size',0)
    if not isinstance(size,int) or not 0<size<1_500_000_000:raise ValueError('업데이트 파일 크기 오류')
    return dict(version=tag.lstrip('v'),url=url,sha256=digest[7:].lower(),size=size,notes=str(release.get('body') or '')[:20000])


class Manager:
    def __init__(self, home, root, launch=None, client_factory=httpx.Client):
        self.home=Path(home);self.root=Path(root);self.lock=threading.RLock();self.worker=None
        self.client_factory=client_factory;self.launch=launch or self.launch_installer
        self.repo=json.loads((Path(__file__).parent/'update_source.json').read_text('utf-8'))['repository']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',self.repo):raise ValueError('업데이트 저장소 설정 오류')
        self.latest=None;self.stop=threading.Event()
        self.state=dict(phase='idle',current=VERSION,latest='',available=False,downloaded=0,total=0,message='새 버전을 확인하세요.',repository=self.repo)

    def snapshot(self):
        with self.lock:
            state=dict(self.state)
        report=self.home/'updates'/'last-result.json'
        if report.is_file():
            try:state['last_install']=json.loads(report.read_text('utf-8'))
            except (OSError,ValueError):pass
        return state

    def _start(self, task):
        with self.lock:
            if self.worker and self.worker.is_alive():raise ValueError('업데이트 작업이 진행 중입니다.')
            self.stop.clear();self.worker=threading.Thread(target=task,daemon=True);self.worker.start()

    def check(self):self._start(self._check)

    def _check(self):
        with self.lock:self.state.update(phase='checking',message='GitHub 정식 배포 확인 중…')
        try:
            with self.client_factory(timeout=30,headers={'Accept':'application/vnd.github+json','User-Agent':'BMS-Korean-Briefing/'+VERSION}) as c:
                r=c.get(f'https://api.github.com/repos/{self.repo}/releases/latest')
                if r.status_code==404:raise ValueError('아직 공개된 정식 배포가 없습니다. 현재 버전을 계속 사용할 수 있습니다.')
                if r.status_code in (403,429):raise ValueError('GitHub 요청 한도에 도달했습니다. 잠시 후 다시 확인하세요.')
                r.raise_for_status();latest=release_info(self.repo,r.json())
            available=version_tuple(latest['version'])>version_tuple(VERSION)
            with self.lock:
                self.latest=latest;self.state.update(phase='available' if available else 'current',latest=latest['version'],available=available,notes=latest['notes'],message='새 버전을 설치할 수 있습니다.' if available else '최신 버전입니다.')
        except Exception as exc:
            with self.lock:self.latest=None;self.state.update(phase='error',available=False,message=str(exc))

    def install(self):
        with self.lock:
            if not self.latest or not self.state['available']:raise ValueError('먼저 새 버전을 확인하세요.')
            latest=dict(self.latest)
        if not (self.root/'User/Plugins/BMS-Korean-Briefing/install.json').is_file():raise ValueError('설치된 프로그램에서만 자동 업데이트할 수 있습니다.')
        self._start(lambda:self._download(latest))

    def cancel(self):self.stop.set()

    def _download(self, latest):
        folder=self.home/'updates'/latest['version'];folder.mkdir(parents=True,exist_ok=True)
        partial=folder/(ASSET+'.part');destination=folder/ASSET
        try:
            with self.lock:self.state.update(phase='downloading',downloaded=0,total=latest['size'],message='업데이트 다운로드 중…')
            digest=hashlib.sha256();count=0
            # Redirects are limited to GitHub's release CDN; never execute a web response.
            with self.client_factory(timeout=60,follow_redirects=False) as client:
                url=latest['url']
                for _ in range(6):
                    with client.stream('GET',url,headers={'User-Agent':'BMS-Korean-Briefing/'+VERSION}) as r:
                        if r.is_redirect:
                            url=r.headers.get('location','');parsed=urlparse(url)
                            if parsed.scheme!='https' or parsed.hostname not in ('github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'):raise ValueError('허용되지 않은 다운로드 이동입니다.')
                            continue
                        r.raise_for_status()
                        with partial.open('wb') as f:
                            for chunk in r.iter_bytes(1024*256):
                                if self.stop.is_set():raise InterruptedError('업데이트 다운로드를 취소했습니다.')
                                count+=len(chunk)
                                if count>latest['size']:raise ValueError('업데이트 파일 크기가 다릅니다.')
                                f.write(chunk);digest.update(chunk)
                                with self.lock:self.state['downloaded']=count
                            f.flush();os.fsync(f.fileno())
                        break
                else:raise ValueError('다운로드 이동 횟수 초과')
            if count!=latest['size'] or digest.hexdigest()!=latest['sha256']:raise ValueError('업데이트 파일 검증 실패. 설치하지 않았습니다.')
            with partial.open('rb') as f:
                if f.read(2)!=b'MZ':raise ValueError('Windows 설치 파일이 아닙니다.')
            if self.stop.is_set():raise InterruptedError('업데이트 다운로드를 취소했습니다.')
            os.replace(partial,destination)
            self.launch(destination,latest['version'])
            with self.lock:self.state.update(phase='installing',message='검증 완료. 앱을 닫고 업데이트 설치 후 다시 엽니다.')
        except InterruptedError as exc:
            with self.lock:self.state.update(phase='cancelled',message=str(exc))
        except Exception as exc:
            with self.lock:self.state.update(phase='error',message='업데이트 실패: '+str(exc))
        finally:
            if partial.exists():partial.unlink()

    def launch_installer(self, path, version):
        subprocess.Popen([str(path),'--update','--bms-root',str(self.root),'--expected-version',version],cwd=path.parent,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

    def close(self):
        self.stop.set()
