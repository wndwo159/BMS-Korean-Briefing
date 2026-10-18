"""Launch the original BMS launcher; run the briefing service only for a BMS session."""
import argparse,hashlib,json,os,subprocess,sys,threading,time,logging
from pathlib import Path

from app_version import VERSION

def executable_directory():
    return Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent

def game_running(root, processes=None):
    import psutil
    expected=os.path.normcase(str((Path(root)/'Bin'/'x64'/'Falcon BMS.exe').resolve()))
    for p in processes if processes is not None else psutil.process_iter(['name','exe']):
        try:
            info=p if isinstance(p,dict) else p.info
            if info.get('exe') and os.path.normcase(str(Path(info['exe']).resolve()))==expected:return True
        except (psutil.NoSuchProcess,psutil.AccessDenied,OSError):continue
    return False

def launcher_running(path, processes=None):
    import psutil
    path=Path(path).resolve()
    # Launcher.exe hands off to Alternative Launcher, often while the user
    # spends several minutes configuring the mission before pressing LAUNCH.
    root=path.parent.parent if path.parent.name.lower()=='launcher' else path.parent
    candidates=(path,root/'Launcher.exe',root/'Launcher'/'FalconBMS_Alternative_Launcher.exe')
    expected={os.path.normcase(str(p.resolve())) for p in candidates}
    for p in processes if processes is not None else psutil.process_iter(['exe']):
        try:
            info=p if isinstance(p,dict) else p.info
            if info.get('exe') and os.path.normcase(str(Path(info['exe']).resolve())) in expected:return True
        except (psutil.NoSuchProcess,psutil.AccessDenied,OSError):continue
    return False

def split_arguments(text):
    if not text:return []
    if os.name!='nt':
        import shlex
        return shlex.split(text)
    import ctypes
    from ctypes import wintypes
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    shell.CommandLineToArgvW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype=ctypes.POINTER(wintypes.LPWSTR)
    count=ctypes.c_int();pointer=shell.CommandLineToArgvW('placeholder.exe '+text,ctypes.byref(count))
    if not pointer:raise OSError('Invalid launcher arguments')
    try:return [pointer[i] for i in range(1,count.value)]
    finally:
        kernel=ctypes.WinDLL('kernel32');kernel.LocalFree.argtypes=[wintypes.HLOCAL];kernel.LocalFree(pointer)

def wait_for_game(is_game,is_launcher,wait,clock=time.monotonic,launcher_grace=180,max_wait=14400):
    started=clock();absent_since=None
    while clock()-started<max_wait:
        if is_game():return True
        if is_launcher():absent_since=None
        elif absent_since is None:absent_since=clock()
        elif clock()-absent_since>=launcher_grace:return False
        wait(1)
    return False

def monitor_exit(is_game,request_exit,stop,clock=time.monotonic,grace=15):
    absent=None
    while not stop.wait(1):
        if is_game():absent=None
        elif absent is None:absent=clock()
        elif clock()-absent>=grace:
            request_exit();return

def acquire_lock(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    stream=path.open('a+b');stream.seek(0)
    if os.fstat(stream.fileno()).st_size==0:stream.write(b'0');stream.flush()
    stream.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:stream.close();return None
    return stream

def configure_paths(base,manifest):
    if manifest:
        root=Path(manifest['bms_root']).resolve()
        os.environ['BMS_KR_DATA']=str(base/'data')
        os.environ['BMS_KR_ROOT']=str(root)
    return Path(os.environ.get('BMS_KR_DATA',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'BMS-Korean-Briefing')))

def monitor_viewer(is_game,clients,request_exit,stop,clock=time.monotonic,idle=30,start_grace=120):
    """Manual sessions end after the last browser heartbeat; BMS keeps PRINT available."""
    started=clock();last_client=None
    while not stop.wait(1):
        now=clock();beats=list(clients())
        if beats:last_client=max(beats)
        if is_game():continue
        if last_client is not None and now-last_client>=idle:
            request_exit();return
        if last_client is None and now-started>=start_grace:
            request_exit();return


def open_when_ready():
    import httpx,webbrowser
    for _ in range(120):
        try:
            response=httpx.get('http://127.0.0.1:8765/api/health',timeout=1)
            if response.status_code==200 and response.json().get('application')=='BMS-Korean-Briefing':
                httpx.post('http://127.0.0.1:8765/api/viewer-session',headers={'Origin':'http://127.0.0.1:8765'},timeout=2)
                webbrowser.open('http://127.0.0.1:8765/');return
        except (httpx.HTTPError,ValueError):pass
        time.sleep(.25)
    logging.error('Manual viewer could not connect to briefing service')


def serve(root=None,bms_session=False,manual_viewer=False):
    import uvicorn
    import main
    server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=8765,log_config=None,access_log=False))
    main.app.state.request_exit=lambda:setattr(server,'should_exit',True)
    stop=threading.Event();monitor=None;manual=threading.Event()
    main.app.state.manual_viewer=manual.set
    def clients():
        with main.engine.lock:return list(main.engine.clients.values())
    def finish_game():
        if manual.is_set():monitor_viewer(lambda:game_running(root),clients,lambda:setattr(server,'should_exit',True),stop)
        else:server.should_exit=True
    if bms_session:
        monitor=threading.Thread(target=monitor_exit,args=(lambda:game_running(root),finish_game,stop),daemon=True)
        monitor.start()
    elif manual_viewer:
        manual.set()
        monitor=threading.Thread(target=monitor_viewer,args=(lambda:game_running(root),clients,lambda:setattr(server,'should_exit',True),stop),daemon=True)
        monitor.start()
    try:server.run()
    finally:
        stop.set()
        if monitor:monitor.join(2)

def run(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--uninstall',action='store_true')
    parser.add_argument('--with-bms',action='store_true')
    parser.add_argument('--attach-bms',action='store_true')
    parser.add_argument('--open-viewer',action='store_true')
    parser.add_argument('--profile',default='default')
    args=parser.parse_args(argv)
    base=executable_directory()
    if args.uninstall:
        from installer_core import deactivate
        deactivate(base)
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'BMS 원래 바로가기를 복원했습니다. 프로그램과 브리핑 기록은 보존했습니다.','BMS Korean Briefing',64)
        return 0
    manifest_path=base/'install.json'
    manifest=json.loads(manifest_path.read_text('utf-8')) if manifest_path.exists() else None
    home=configure_paths(base,manifest);home.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=home/'application.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    lock=acquire_lock(home/'session.lock')
    if lock is None:
        if args.open_viewer:open_when_ready()
        # A rapid restart during the previous session's exit grace must still launch BMS.
        if args.with_bms and manifest and not game_running(manifest['bms_root']):
            profile=manifest['profiles'].get(args.profile,manifest['profiles']['default'])
            launcher=Path(profile['target'])
            if launcher.is_file() and not launcher_running(launcher):
                subprocess.Popen([str(launcher),*split_arguments(profile.get('arguments',''))],cwd=profile.get('working_directory') or str(launcher.parent))
        return 0
    try:
        if args.open_viewer:
            root=Path(manifest['bms_root']) if manifest else Path(os.environ.get('BMS_KR_ROOT',r'B:\Falcon BMS 4.38'))
            os.environ['BMS_KR_PRINT_ONLY']='1'
            threading.Thread(target=open_when_ready,daemon=True).start()
            logging.info('Manual viewer starting without BMS requirement')
            serve(root,manual_viewer=True)
        elif args.with_bms or args.attach_bms:
            if not manifest:raise RuntimeError('먼저 설치 프로그램으로 BMS 경로를 지정하세요.')
            root=Path(manifest['bms_root']);profile=manifest['profiles'].get(args.profile,manifest['profiles']['default'])
            launcher=Path(profile['target'])
            if not launcher.is_file():raise RuntimeError('BMS 원본 런처를 찾을 수 없습니다.')
            if not game_running(root):
                if not args.attach_bms and not launcher_running(launcher):
                    subprocess.Popen([str(launcher),*split_arguments(profile.get('arguments',''))],cwd=profile.get('working_directory') or str(launcher.parent))
                logging.info('Waiting for BMS: %s',root)
                if not wait_for_game(lambda:game_running(root),lambda:launcher_running(launcher),time.sleep):
                    logging.info('BMS launch cancelled: no game or launcher after grace period')
                    return 0
            os.environ['BMS_KR_PRINT_ONLY']='1'
            logging.info('BMS detected; briefing server starting')
            serve(root,bms_session=True)
        else:serve()
        return 0
    except Exception:
        logging.exception('BMS briefing session failed')
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'실행 중 문제가 발생했습니다. User\\Plugins\\BMS-Korean-Briefing\\data\\application.log를 확인해주세요.','BMS Korean Briefing',16)
        return 1
    finally:lock.close()

if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(run())
