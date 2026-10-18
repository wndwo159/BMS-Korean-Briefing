"""Local Ollama discovery and explicit, observable model downloads."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.parse import urlsplit
import httpx

CATALOG = [
    {'name':'translategemma:4b','title':'TranslateGemma 4B · 먼저 사용해보기','size':'약 3.3 GB','description':'번역 전용. 큰 모델보다 메모리 부담이 적습니다.'},
    {'name':'translategemma:12b','title':'TranslateGemma 12B · 품질 비교용','size':'약 8.1 GB','description':'번역 전용. 더 많은 메모리가 필요하며 게임과 GPU를 공유합니다.'},
]


def local_url(value):
    url=urlsplit(value)
    if url.scheme not in ('http','https') or url.hostname not in ('localhost','127.0.0.1','::1') or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('모델 관리는 이 PC의 Ollama 주소만 지원합니다. 예: http://127.0.0.1:11434')
    return value.rstrip('/')


def executable():
    found=shutil.which('ollama')
    if found:return found
    path=Path(os.environ.get('LOCALAPPDATA',''))/'Programs'/'Ollama'/'ollama.exe'
    return str(path) if path.is_file() else None


class Manager:
    def __init__(self):
        self.lock=threading.RLock();self.cancel=threading.Event();self.response=None;self.worker=None
        self.job={'state':'idle','model':'','status':'','completed':0,'total':0,'percent':0,'error':''}

    def snapshot(self):
        with self.lock:return dict(self.job)

    def status(self,url):
        base=local_url(url)
        result={'reachable':False,'installed':bool(executable()),'models':[],'catalog':CATALOG,'download':self.snapshot(),'install_url':'https://ollama.com/download/windows'}
        try:
            r=httpx.get(base+'/api/tags',timeout=3);r.raise_for_status()
            result.update(reachable=True,installed=True,models=r.json().get('models',[]))
        except (httpx.HTTPError,ValueError) as exc:result['error']='Ollama에 연결할 수 없습니다. 설치 후 실행하거나 아래 실행 버튼을 누르세요.'
        return result

    def start_runtime(self):
        path=executable()
        if not path:raise ValueError('Ollama를 먼저 설치하세요. 설치 후 이 화면에서 다시 확인할 수 있습니다.')
        subprocess.Popen([path,'serve'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def pull(self,url,name):
        base=local_url(url)
        if name not in {m['name'] for m in CATALOG}:raise ValueError('다운로드 목록에서 모델을 선택하세요.')
        with self.lock:
            if self.job['state'] in ('downloading','cancelling'):raise ValueError('이미 다운로드 중입니다. 완료하거나 취소한 뒤 다시 시도하세요.')
            self.cancel.clear();self.job=dict(state='downloading',model=name,status='다운로드 연결 중',completed=0,total=0,percent=0,error='')
            self.worker=threading.Thread(target=self._pull,args=(base,name),daemon=True);self.worker.start()
        return self.snapshot()

    def _pull(self,base,name):
        try:
            with httpx.stream('POST',base+'/api/pull',json={'model':name,'stream':True},timeout=httpx.Timeout(60,connect=5)) as response:
                with self.lock:self.response=response
                response.raise_for_status();success=False
                for line in response.iter_lines():
                    if self.cancel.is_set():break
                    if not line:continue
                    event=json.loads(line)
                    if event.get('error'):raise ValueError(event['error'])
                    total=event.get('total',0);completed=event.get('completed',0)
                    with self.lock:
                        self.job['status']=event.get('status','다운로드 중')
                        if total:self.job.update(total=total,completed=completed,percent=min(100,round(completed/total*100)))
                    if event.get('status')=='success':success=True;break
                with self.lock:
                    if self.cancel.is_set():self.job.update(state='cancelled',status='다운로드 취소됨')
                    elif success:self.job.update(state='complete',status='설치 완료 · 모델 목록에서 선택하세요',percent=100)
                    else:raise ValueError('완료 응답 없이 다운로드가 종료됐습니다. 다시 시도하세요.')
        except Exception as exc:
            with self.lock:
                if self.cancel.is_set():self.job.update(state='cancelled',status='다운로드 취소됨')
                else:
                    error='Ollama 연결이 끊겼습니다. Ollama를 실행하고 다시 시도하세요.' if isinstance(exc,httpx.ConnectError) else str(exc)[:300]
                    self.job.update(state='error',status='다운로드 실패',error=error)
        finally:
            with self.lock:self.response=None

    def cancel_pull(self):
        with self.lock:
            if self.job['state'] not in ('downloading','cancelling'):return self.snapshot()
            self.cancel.set();self.job.update(state='cancelling',status='다운로드 취소 중')
            if self.response:
                try:self.response.close()
                except Exception:pass
        return self.snapshot()

    def close(self):
        self.cancel_pull()
        if self.worker:self.worker.join(2)
