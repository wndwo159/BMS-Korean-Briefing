import os, re, json, time, hashlib, sqlite3, threading, webbrowser, tempfile, sys
from pathlib import Path
from app_version import VERSION
from collections import Counter
from contextlib import asynccontextmanager
from bs4 import BeautifulSoup, UnicodeDammit
import httpx
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

HOME = Path(os.environ.get('BMS_KR_DATA',str(Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'BMS-Korean-Briefing')))
BMS_ROOT = Path(os.environ.get('BMS_KR_ROOT',r'B:\Falcon BMS 4.38'))
HOME.mkdir(parents=True, exist_ok=True)
DEFAULTS = dict(kneeboard_first_page=True, kneeboard_aspect='a4', watch_dir=str(BMS_ROOT/'User'/'Briefings'), output_dir=str(BMS_ROOT/'User'/'BriefingKR'), auto_open=True, auto_translate=True, auto_save=True, reuse_window=True, notify=False, force_focus=False, startup=False, provider='offline', model='', ollama_url='http://127.0.0.1:11434', openai_model='gpt-4.1-mini')
CSS = (Path(__file__).parent/'briefing.css').read_text('utf-8-sig')
from briefing_render import render, metadata
from theater_context import current as current_theater, marker as theater_marker, saved as saved_theater
from military_terms import REVISION, spans as protected_spans
from ollama_manager import Manager as OllamaManager, local_url
ollama_manager=OllamaManager()
# BMS can join identifiers to prose (P-12or, M-1992anti-aircraft).
# The lookahead branch has its own boundary so the actual identifier stays protected.
TOKEN = re.compile(r'\b[A-Z]+-\d+(?=anti-aircraft\b|or\b)|\b(?:(?:Maj\.|Lt\.|Cpt\.|Capt\.|2Lt\.|1Lt\.)[ ]+[A-Za-z]+(?:[ ]+[A-Z][A-Za-z]+)*|[A-Za-z][A-Za-z0-9/-]*\d[A-Za-z0-9/.-]*|[A-Z]{2,}|\d+(?:[.:,/-]\d+)*(?:[A-Za-z]+)?)(?:\s+(?:MHz|FT|NM|KT|ft|nm|km|kts|deg|mm))?\b', re.ASCII)
BRIEFING_STYLE = ('Write complete, natural Korean military briefing sentences. Preserve the meaning, negation, and uncertainty of the original; do not add facts or tactical instructions. '
                 'In this military context Intelligence means 정보당국 or 첩보, not 지능; offensive means 공세; take a location means 점령; put a facility out of commission means 가동 불능 상태로 만들다. '
                 'Distinguish electrical power from military strength. Preserve qualifiers such as probably, suspected, and no known; no known defenses does not mean no threat. '
                 'Keep unknown proper names identifiable and never invent Korean place names. Preserve every __BMS_n__ placeholder exactly, once, and do not translate its contents. ')

def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def parse(raw):
    if not re.search(br'<(?:html|body|table|div|p|h[1-6])(?:\s|>)',raw,re.I):
        import html
        text=UnicodeDammit(raw).unicode_markup or raw.decode('utf-8',errors='replace')
        raw=('<html><body><pre>'+html.escape(text)+'</pre></body></html>').encode('utf-8')
    soup = BeautifulSoup(raw, 'lxml')
    for tag in list(soup.find_all(True)):
        if tag.name in ('script','style','iframe','object','embed','link','meta','base','form','input','button','svg','math','img','audio','video'):
            tag.decompose(); continue
        for attr in list(tag.attrs):
            if attr not in ('colspan','rowspan'): del tag[attr]
    nodes=[]
    for node in list(soup.body.find_all(string=True)) if soup.body else []:
        text=str(node)
        if text.strip():
            if node.parent.name=='pre':
                parts=text.splitlines(keepends=True)
                for part in parts:
                    element=soup.new_tag('span');element.string=part;node.insert_before(element)
                    if part.strip():nodes.append((element.string,part))
                node.extract()
            else:nodes.append((node,text))
    return soup,nodes

def document(body, status):
    import html
    template=(Path(__file__).parent/'standalone.html').read_text('utf-8')
    return template.replace('__PAPER_CSS__',CSS,1).replace('__STATUS__',html.escape(status),1).replace('__BRIEFING_CONTENT__',body,1)

class Engine:
    def __init__(self, home=HOME, opener=None):
        self.home=Path(home); self.home.mkdir(parents=True,exist_ok=True)
        self.config=DEFAULTS | (json.loads((self.home/'settings.json').read_text('utf-8')) if (self.home/'settings.json').exists() else {})
        if self.config['provider']=='argos':
            self.config['provider']='offline'
            atomic(self.home/'settings.json',json.dumps(self.config,ensure_ascii=False,indent=2))
        self.lock=threading.RLock(); self.stop=threading.Event(); self.observer=None; self.worker=None
        self.state={'id':'','status':'PRINT 대기 중','done':0,'total':0,'html':'','file':''}
        self.offline=None; self.forced=set(); self.seen={}; self.pending={}; self.clients={}; self.last_open=0; self.opener=opener or webbrowser.open
        self.db=sqlite3.connect(self.home/'briefings.sqlite',check_same_thread=False)
        self.db.executescript('CREATE TABLE IF NOT EXISTS cache(k TEXT PRIMARY KEY,v TEXT); CREATE TABLE IF NOT EXISTS history(id TEXT PRIMARY KEY, source TEXT, hash TEXT, output TEXT, stamp REAL);')
        self.db.execute('CREATE TABLE IF NOT EXISTS translation_versions(id TEXT PRIMARY KEY, version TEXT)')
    def start(self):
        self.worker=threading.Thread(target=self.loop,daemon=True); self.worker.start()
    def close(self):
        self.stop.set()
        if self.worker:self.worker.join(40)
        if self.observer:self.observer.stop(); self.observer.join(5)
        if not self.worker or not self.worker.is_alive():self.db.close()
    def enqueue(self,path):
        p=Path(path)
        if p.suffix.lower() in ('.html','.htm') or p.name.lower()=='briefing.txt':
            with self.lock:self.pending[str(p)]=time.monotonic()
    def snapshot(self):
        with self.lock:return dict(self.state)
    def loop(self):
        watched=None
        initial_scan=True
        while not self.stop.is_set():
            folder=Path(self.config['watch_dir'])
            if str(folder)!=watched or (self.observer is None and folder.is_dir()):
                if self.observer:self.observer.stop(); self.observer.join(); self.observer=None
                watched=str(folder)
                if folder.is_dir():
                    engine=self
                    class Handler(FileSystemEventHandler):
                        def on_created(self,e):engine.enqueue(e.src_path)
                        def on_modified(self,e):engine.enqueue(e.src_path)
                        def on_moved(self,e):engine.enqueue(e.dest_path)
                    try:
                        self.observer=Observer(); self.observer.schedule(Handler(),str(folder)); self.observer.start()
                    except OSError:self.observer=None
            try:
                files=sorted((p for p in folder.glob('*') if p.suffix.lower() in ('.html','.htm') or p.name.lower()=='briefing.txt'),key=lambda p:p.stat().st_mtime)
                if initial_scan and os.environ.get('BMS_KR_PRINT_ONLY')=='1':
                    for p in files:
                        stat=p.stat();self.seen[str(p)]=(stat.st_size,stat.st_mtime_ns)
                initial_scan=False
                for p in files:
                    key=str(p); stat=p.stat(); signature=(stat.st_size,stat.st_mtime_ns)
                    if self.seen.get(key)!=signature:
                        self.seen[key]=signature; self.enqueue(p)
                with self.lock:ready=[p for p,t in self.pending.items() if time.monotonic()-t>0.8]
                if ready:
                    path=max(ready,key=lambda p:Path(p).stat().st_mtime if Path(p).exists() else 0)
                    with self.lock:
                        for p in ready:self.pending.pop(p,None)
                    try:self.process(Path(path))
                    except Exception:
                        self.seen.pop(path,None)
                        raise
            except Exception as e:
                with self.lock:self.state['status']='파일 대기: '+str(e)
            self.stop.wait(.4)
    def stable_read(self,path):
        previous=None; count=0
        for _ in range(60):
            if self.stop.wait(.25):raise OSError('종료 중')
            st=path.stat(); current=(st.st_size,st.st_mtime_ns)
            count=count+1 if current==previous else 0; previous=current
            if count>=4:
                raw=path.read_bytes()
                if path.stat().st_mtime_ns==current[1] and len(raw)==current[0]:return raw
        raise OSError('파일 쓰기가 계속되고 있습니다')
    def translate(self,text):
        protected=TOKEN.findall(text)
        c=self.config
        glossary=json.loads((Path(__file__).parent/'glossary.json').read_text('utf-8'))
        key=hashlib.sha256(json.dumps([text,c['provider'],c['model'],c['ollama_url'],c['openai_model'],glossary,REVISION,'ollama-setup-v1'],ensure_ascii=False).encode()).hexdigest()
        with self.lock:row=self.db.execute('SELECT v FROM cache WHERE k=?',(key,)).fetchone()
        if row:return row[0]
        from offline_translation import reviewed_translation
        output=reviewed_translation(text,TOKEN,glossary)
        if output is not None:
            if Counter(TOKEN.findall(output))!=Counter(protected):raise ValueError('숫자/약어 변경 감지')
            with self.lock:self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?)',(key,output));self.db.commit()
            return output
        if c['provider']=='offline':
            if self.offline is None:
                from offline_translation import OfflineTranslator
                self.offline=OfflineTranslator()
            output=self.offline.translate(text,TOKEN,glossary)
            if Counter(TOKEN.findall(output))!=Counter(protected):raise ValueError('숫자/약어 변경 감지')
            with self.lock:self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?)',(key,output));self.db.commit()
            return output
        protected_values=[];masked_parts=[]
        parts=list(protected_spans(text,TOKEN,glossary))
        if not any(not keep and re.search('[A-Za-z]',value) for keep,value in parts):
            output=''.join(value for keep,value in parts)
            if Counter(TOKEN.findall(output))!=Counter(protected):raise ValueError('숫자/약어 변경 감지')
            with self.lock:self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?)',(key,output));self.db.commit()
            return output
        for keep,value in parts:
            if keep:
                masked_parts.append(f'__BMS_{len(protected_values)}__');protected_values.append(value)
            else:masked_parts.append(value)
        masked=''.join(masked_parts)
        prompt='Translate ALL English text to Korean for Falcon BMS. Do not summarize. '+BRIEFING_STYLE+'Return JSON {"id":"text","translation":"..."}. Glossary (keep abbreviations): '+json.dumps(glossary,ensure_ascii=False)+'\n'+json.dumps({'id':'text','text':masked})
        if c['provider']=='ollama':
            if not c['model']:raise ValueError('설정에서 설치된 Ollama 모델을 선택하세요')
            if c['model'].split(':')[0]=='translategemma':
                instruction='You are a professional English (en) to Korean (ko) translator. '+BRIEFING_STYLE+'Produce only the Korean translation, without additional explanations. Please translate the following English text into Korean:\n\n\n'+masked
                r=httpx.post(c['ollama_url']+'/api/chat',json={'model':c['model'],'messages':[{'role':'user','content':instruction}],'stream':False,'options':{'temperature':0}},timeout=180);r.raise_for_status()
                result={'id':'text','translation':r.json()['message']['content']}
            else:
                r=httpx.post(c['ollama_url']+'/api/generate',json={'model':c['model'],'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0}},timeout=180);r.raise_for_status();result=json.loads(r.json()['response'])
        elif c['provider']=='openai':
            r=httpx.post('https://api.openai.com/v1/chat/completions',headers={'Authorization':'Bearer '+os.environ.get('OPENAI_API_KEY','')},json={'model':c['openai_model'],'messages':[{'role':'user','content':prompt}],'response_format':{'type':'json_object'}},timeout=30);r.raise_for_status();result=json.loads(r.json()['choices'][0]['message']['content'])
        else:raise ValueError('지원하지 않는 번역 엔진')
        if result.get('id')!='text' or not isinstance(result.get('translation'),str):raise ValueError('번역 응답 ID 오류')
        output=result['translation']
        for i,t in enumerate(protected_values):
            placeholder=f'__BMS_{i}__'
            if output.count(placeholder)!=1:raise ValueError('군사 데이터 보호 검증 실패')
            output=output.replace(placeholder,t)
        if Counter(TOKEN.findall(output))!=Counter(protected):raise ValueError('숫자/약어 변경 감지')
        with self.lock:self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?)',(key,output));self.db.commit()
        return output
    def process(self,path):
        raw=self.stable_read(path); digest=hashlib.sha256(raw).hexdigest(); identity=hashlib.sha256(str(path.resolve()).lower().encode()).hexdigest()[:16]
        with self.lock:old=self.db.execute('SELECT hash,output FROM history WHERE id=?',(identity,)).fetchone()
        with self.lock:
            force=str(path.resolve()) in self.forced
            self.forced.discard(str(path.resolve()))
        with self.lock:version=self.db.execute('SELECT version FROM translation_versions WHERE id=?',(identity,)).fetchone()
        if old and old[0]==digest and version and version[0]==REVISION and not force:
            if not self.state['html'] and Path(old[1]).exists():
                saved=BeautifulSoup(Path(old[1]).read_text('utf-8'),'lxml')
                article=saved.find('article')
                restored=article or saved.body
                saved_sections=[]
                for section in restored.select('.briefing-section'):
                    heading=section.find('h2')
                    saved_sections.append({'id':section.get('id',''),'title':next(heading.stripped_strings,'브리핑') if heading else '브리핑'})
                error_count=len(restored.select('.error'))
                self.state.update(id=identity,file=path.name,html=str(restored),status='저장된 한국어 브리핑' if not error_count else '저장된 브리핑 · 일부 영어 원문 유지',phase='partial' if error_count else 'complete',errors=error_count,revision=time.time(),sections=saved_sections,meta=metadata(parse(raw)[0].get_text())|{'theater':saved_theater(str(restored))},provider=self.config['provider'],done=1,total=1)
            return
        soup,nodes=parse(raw)
        if not nodes:raise ValueError('빈 브리핑입니다')
        theater=current_theater(BMS_ROOT)
        if old and old[0]==digest and Path(old[1]).is_file():
            recorded=saved_theater(Path(old[1]).read_text('utf-8'))
            if recorded.get('source')=='bms-registry':theater=recorded
        context=theater_marker(theater)
        initial,sections=render(soup)
        with self.lock:self.state=dict(id=identity,status='한국어 번역 준비 중',phase='translating',done=0,total=len(nodes),html=context+initial,file=path.name,sections=sections,meta=metadata(soup.get_text())|{'theater':theater},provider=self.config['provider'],errors=0,revision=time.time())
        now=time.monotonic()
        with self.lock:alive=any(now-t<15 for t in self.clients.values())
        if self.config['auto_open'] and (not alive or not self.config['reuse_window']) and now-self.last_open>15:
            self.last_open=now
            # Windows background browser launch avoids requesting foreground activation.
            if os.name=='nt' and self.opener==webbrowser.open:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(None,'open','http://127.0.0.1:8765',None,None,1 if self.config['force_focus'] else 4)
            else:self.opener('http://127.0.0.1:8765')
        errors=0
        provider_error=None
        if self.config['auto_translate'] and self.config['provider']=='ollama':
            try:
                response=httpx.get(self.config['ollama_url']+'/api/tags',timeout=2)
                response.raise_for_status()
                models=response.json().get('models',[])
                if not models:raise ValueError('Ollama 모델이 없습니다. 모델을 설치하세요')
                if not self.config['model']:raise ValueError('설정에서 설치된 Ollama 모델을 선택하세요')
            except Exception:provider_error='Ollama 서비스/모델을 사용할 수 없습니다. 설정에서 연결을 확인하세요'
        for index,(node,text) in enumerate(nodes):
            if self.stop.is_set():return
            with self.lock:
                if self.pending:return
            translated=text;error=''
            if self.config['auto_translate'] and re.search('[a-zA-Z]',text):
                try:
                    if provider_error:raise ValueError(provider_error)
                    translated=self.translate(text)
                except Exception as exc:error=type(exc).__name__+': '+str(exc)[:160]; errors+=1
            span=soup.new_tag('span');kr=soup.new_tag('span',attrs={'class':'kr'});kr.string=translated
            if error:kr['class']='kr error';kr['title']=error
            en=soup.new_tag('span',attrs={'class':'en'});en.string=text
            span.append(kr);span.append(en);node.replace_with(span)
            body,sections=render(soup)
            with self.lock:self.state.update(done=index+1,status=f'한국어 번역 중 {index+1}/{len(nodes)}',html=context+body,sections=sections,errors=errors)
        status=f'일부 번역 실패 · 영어 원문 유지 {errors}건' if errors else '한국어 브리핑 준비 완료'
        output=Path(self.config['output_dir'])/(path.stem+'_'+identity+'_KR.html')
        if self.config['auto_save']:
            source=Path(self.config['watch_dir']).resolve();dest=output.resolve()
            if dest==path.resolve() or source==dest.parent or source in dest.parents:raise ValueError('출력 폴더는 원본 감시 폴더 밖이어야 합니다')
            atomic(output,document(context+render(soup)[0],status))
            with self.lock:
                self.db.execute('INSERT OR REPLACE INTO history VALUES (?,?,?,?,?)',(identity,str(path),digest,str(output),time.time()))
                self.db.execute('INSERT OR REPLACE INTO translation_versions VALUES (?,?)',(identity,REVISION));self.db.commit()
        with self.lock:self.state.update(status=status,phase='partial' if errors else 'complete',errors=errors)
        if self.config['notify'] and os.name=='nt':
            import winsound
            winsound.MessageBeep(winsound.MB_OK)

from updater import Manager as UpdateManager
update_manager=UpdateManager(HOME,BMS_ROOT)
engine=Engine()
@asynccontextmanager
async def lifespan(app):
    engine.start();update_manager.check();yield;update_manager.close();ollama_manager.close();engine.close()
app=FastAPI(lifespan=lifespan)
@app.middleware('http')
async def local_only(request:Request,call_next):
    if request.headers.get('host','').split(':')[0] not in ('127.0.0.1','localhost','testserver'):return JSONResponse({'detail':'Forbidden'},status_code=403)
    if request.method=='POST' and request.headers.get('origin') not in ('http://127.0.0.1:8765','http://localhost:8765'):return JSONResponse({'detail':'Forbidden'},status_code=403)
    response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff';return response
@app.get('/',response_class=HTMLResponse)
def index():return (Path(__file__).parent/'viewer.html').read_text('utf-8')
@app.get('/briefing.css')
def stylesheet():
    from fastapi.responses import Response
    return Response(CSS,media_type='text/css')
@app.post('/api/retry')
def retry():
    with engine.lock:
        rows=engine.db.execute('SELECT source FROM history ORDER BY stamp DESC LIMIT 1').fetchall()
        if not rows:raise HTTPException(404,'브리핑 기록이 없습니다')
        source=rows[0][0]
        engine.forced.add(str(Path(source).resolve()))
        engine.enqueue(source)
    return {'queued':True}
@app.get('/api/health')
def health():
    return {'application':'BMS-Korean-Briefing','version':VERSION,'data_dir':str(HOME),'bms_root':str(BMS_ROOT)}
@app.post('/api/shutdown')
def shutdown():
    callback=getattr(app.state,'request_exit',None)
    if callback is None:raise HTTPException(409,'이 실행 방식은 원격 종료를 지원하지 않습니다')
    callback()
    return {'stopping':True}
@app.post('/api/viewer-session')
def viewer_session():
    callback=getattr(app.state,'manual_viewer',None)
    if callback is None:raise HTTPException(409,'수동 뷰어는 설치된 EXE에서 사용할 수 있습니다.')
    callback();return {'manual_viewer':True}
@app.get('/api/state')
def state(client:str='viewer'):
    with engine.lock:engine.clients[client[:80]]=time.monotonic()
    return engine.snapshot()
@app.get('/api/settings')
def settings():return engine.config
@app.post('/api/kneeboard')
def generate_kneeboard(value:dict):
    from kneeboard import apply
    markup=value.get('html','')
    if not isinstance(markup,str) or not markup.strip() or len(markup)>2_000_000:
        raise HTTPException(400,'유효한 브리핑을 먼저 여세요. 최대 2MB까지 지원합니다.')
    first=value.get('first_page',engine.config.get('kneeboard_first_page',True))
    aspect=value.get('aspect',engine.config.get('kneeboard_aspect','a4'))
    if not isinstance(first,bool) or aspect not in ('a4','texture'):raise HTTPException(400,'니보드 설정 오류')
    try:
        result=apply(BMS_ROOT,HOME,markup,first_page=first,aspect=aspect)
        with engine.lock:
            engine.config.update(kneeboard_first_page=first,kneeboard_aspect=aspect)
            atomic(engine.home/'settings.json',json.dumps(engine.config,ensure_ascii=False,indent=2))
        return result
    except (ValueError,OSError) as exc:raise HTTPException(400,str(exc))

@app.post('/api/kneeboard/restore')
def restore_kneeboard():
    from kneeboard import restore
    try:return restore(BMS_ROOT,HOME)
    except (ValueError,OSError) as exc:raise HTTPException(400,str(exc))

@app.post('/api/settings')
def save_settings(value:dict):
    config=engine.config | {k:v for k,v in value.items() if k in DEFAULTS}
    for k,default in DEFAULTS.items():
        if not isinstance(config[k],type(default)):raise HTTPException(400,'설정 자료형 오류')
    source=Path(config['watch_dir']).resolve();dest=Path(config['output_dir']).resolve()
    if source==dest or source in dest.parents:raise HTTPException(400,'출력은 감시 폴더 밖에 지정하세요')
    if config['provider']=='argos':config['provider']='offline'
    if config['provider'] not in ('offline','ollama','openai'):raise HTTPException(400,'지원하지 않는 번역 엔진')
    if config['provider']=='ollama':
        try:available=ollama_manager.status(config['ollama_url'])
        except ValueError as exc:raise HTTPException(400,str(exc))
        if not available['reachable']:raise HTTPException(400,'Ollama를 설치·실행한 뒤 모델 목록을 새로고침하세요.')
        if not config['model'] or config['model'] not in {m.get('name') for m in available['models']}:raise HTTPException(400,'설치된 모델 목록에서 사용할 모델을 선택하세요.')
    if config['startup']!=engine.config['startup']:startup(config['startup'])
    changed=any(config[k]!=engine.config[k] for k in ('provider','model','openai_model','ollama_url'))
    atomic(engine.home/'settings.json',json.dumps(config,ensure_ascii=False,indent=2));engine.config=config
    if changed:
        try:retry()
        except HTTPException:pass
    return config
@app.get('/api/history')
def history():
    with engine.lock:return [dict(id=r[0],source=r[1],output=r[2]) for r in engine.db.execute('SELECT id,source,output FROM history ORDER BY stamp DESC LIMIT 100')]
@app.get('/history/{identity}',response_class=HTMLResponse)
def saved(identity:str):
    with engine.lock:row=engine.db.execute('SELECT output FROM history WHERE id=?',(identity,)).fetchone()
    if not row or not Path(row[0]).exists():raise HTTPException(404)
    return Path(row[0]).read_text('utf-8')
@app.get('/api/models')
def models(url:str=''):
    try:return ollama_manager.status(url or engine.config['ollama_url'])
    except ValueError as exc:raise HTTPException(400,str(exc))
@app.post('/api/ollama/start')
def ollama_start():
    try:ollama_manager.start_runtime();return {'started':True}
    except ValueError as exc:raise HTTPException(400,str(exc))
@app.post('/api/ollama/pull')
def ollama_pull(value:dict):
    try:return ollama_manager.pull(value.get('url') or engine.config['ollama_url'],value.get('model',''))
    except ValueError as exc:raise HTTPException(400,str(exc))
@app.get('/api/ollama/download')
def ollama_download():return ollama_manager.snapshot()
@app.post('/api/ollama/cancel')
def ollama_cancel():return ollama_manager.cancel_pull()

def startup(enabled):
    if os.name!='nt':return
    import winreg,subprocess
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled:
            command=[sys.executable] if getattr(sys,'frozen',False) else [str(Path(sys.executable).with_name('pythonw.exe')),str(Path(__file__).resolve())]
            winreg.SetValueEx(key,'BMS Korean Briefing',0,winreg.REG_SZ,subprocess.list2cmdline(command))
        else:
            try:winreg.DeleteValue(key,'BMS Korean Briefing')
            except FileNotFoundError:pass
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8765,log_config=None)


@app.get('/api/updates')
def updates_state():return update_manager.snapshot()

@app.post('/api/updates/check')
def updates_check():
    try:update_manager.check()
    except ValueError as exc:raise HTTPException(409,str(exc))
    return update_manager.snapshot()

@app.post('/api/updates/install')
def updates_install():
    try:update_manager.install()
    except ValueError as exc:raise HTTPException(400,str(exc))
    return update_manager.snapshot()

@app.post('/api/updates/cancel')
def updates_cancel():
    update_manager.cancel();return update_manager.snapshot()
