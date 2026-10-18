"""Per-user installation and reversible shortcut integration."""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from app_version import VERSION
APP_NAME = 'BMS-Korean-Briefing'
EXE_NAME = APP_NAME + '.exe'

DISCOVER = r'''
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$p = $env:BMS_KR_PLAN | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$folders = @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('StartMenu')) | Select-Object -Unique
$managed = New-Object 'System.Collections.Generic.List[string]'
$found = @(foreach ($folder in $folders) {
 Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
  $link = $shell.CreateShortcut($_.FullName)
  if ($p.allowed -contains $link.TargetPath) {
   [pscustomobject]@{path=$_.FullName;target=$link.TargetPath;arguments=$link.Arguments;working_directory=$link.WorkingDirectory;icon=$link.IconLocation}
  }
  elseif ($link.TargetPath -eq $p.ours) { $managed.Add($_.FullName) }
 }
})
[pscustomobject]@{desktop=[Environment]::GetFolderPath('Desktop');links=$found;managed=@($managed.ToArray())} | ConvertTo-Json -Depth 8 -Compress
'''

APPLY = r'''
$ErrorActionPreference = 'Stop'
$p = $env:BMS_KR_PLAN | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
foreach ($item in $p.links) {
 $link = $shell.CreateShortcut($item.path)
 $link.TargetPath = $p.exe
 $link.Arguments = '--with-bms --profile ' + $item.profile
 $link.WorkingDirectory = $p.folder
 $link.IconLocation = $item.icon
 $link.Description = 'Falcon BMS with automatic Korean briefing'
 $link.WindowStyle = 7
 $link.Save()
}
'''

RESTORE = r'''
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$p = $env:BMS_KR_PLAN | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$result = @(foreach ($item in $p.links) {
 if (Test-Path -LiteralPath $item.path) {
  $link = $shell.CreateShortcut($item.path)
  if ($link.TargetPath -eq $p.exe) {
   if ($item.created) {
    # Preserve the link as an ordinary original-launcher shortcut on deactivation.
    $link.TargetPath = $p.original
    $link.Arguments = ''
    $link.WorkingDirectory = Split-Path -Parent $p.original
    $link.Description = 'Falcon BMS'
    $link.Save()
   }
   elseif (Test-Path -LiteralPath $item.backup) { Copy-Item -LiteralPath $item.backup -Destination $item.path -Force }
   [pscustomobject]@{path=$item.path;restored=$true}
  }
 }
})
ConvertTo-Json -InputObject $result -Compress
'''


def powershell(script, plan):
    if 'New-Object -ComObject WScript.Shell' in script:
        from shell_link import UNICODE_SHELL
        script=UNICODE_SHELL+script.replace('New-Object -ComObject WScript.Shell','New-Object BmsShell')
    env = dict(os.environ, BMS_KR_PLAN=json.dumps(plan, ensure_ascii=True))
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
        env=env, capture_output=True, text=True, encoding='utf-8-sig', errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or '바로가기 처리 실패')
    return json.loads(result.stdout) if result.stdout.strip() else None


def validate_root(root):
    root = Path(root).expanduser().resolve()
    # Accept a selected launcher, game executable, or nested Bin/User folder.
    if root.is_file():root=root.parent
    for candidate in (root,*list(root.parents)[:4]):
        if (candidate/'Bin/x64/Falcon BMS.exe').is_file():
            root=candidate;break
    if not (root / 'Bin' / 'x64' / 'Falcon BMS.exe').is_file():
        raise ValueError('Falcon BMS.exe가 있는 BMS 설치 폴더를 선택하세요.')
    if not (root / 'User').is_dir():
        raise ValueError('BMS User 폴더가 없습니다.')
    destination = root / 'User' / 'Plugins' / APP_NAME
    if destination.resolve() != destination or root not in destination.resolve().parents:
        raise ValueError('플러그인 설치 경로의 연결/위치를 확인하세요.')
    return root, destination


def detect_roots():
    found = []
    if os.name == 'nt':
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r'SOFTWARE\Benchmark Sims', 0, winreg.KEY_READ | view) as parent:
                        for i in range(winreg.QueryInfoKey(parent)[0]):
                            try:
                                with winreg.OpenKey(parent, winreg.EnumKey(parent, i)) as child:
                                    value = winreg.QueryValueEx(child, 'baseDir')[0]
                                    if (Path(value) / 'Bin' / 'x64' / 'Falcon BMS.exe').exists():
                                        found.append(str(Path(value)))
                            except OSError:
                                pass
                except OSError:
                    pass
    try:
        import psutil
        for process in psutil.process_iter(['exe']):
            executable=process.info.get('exe')
            if not executable:continue
            executable=Path(executable)
            if executable.name.lower() in ('falcon bms.exe','falconbms_alternative_launcher.exe','launcher.exe'):
                for candidate in list(executable.parents)[:4]:
                    if (candidate/'Bin/x64/Falcon BMS.exe').is_file():found.append(str(candidate));break
    except (OSError,ImportError):pass
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        path = Path(letter + ':/') / 'Falcon BMS 4.38'
        if (path / 'Bin' / 'x64' / 'Falcon BMS.exe').exists():
            found.append(str(path))
    for env in ('ProgramFiles','ProgramFiles(x86)'):
        parent=Path(os.environ.get(env,'C:/Program Files'))
        if parent.is_dir():
            for candidate in parent.glob('Falcon BMS*'):
                if (candidate/'Bin/x64/Falcon BMS.exe').is_file():found.append(str(candidate))
    unique={}
    for value in found:
        candidate=Path(value).resolve()
        unique.setdefault(str(candidate).casefold(),str(candidate))
    return list(unique.values())


def remove_login_startup():
    if os.name != 'nt':
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        try:
            winreg.DeleteValue(key, 'BMS Korean Briefing')
        except FileNotFoundError:
            pass


def discover_briefings(root):
    selected = root / 'User' / 'Briefings'
    import re
    for filename in ('falcon bms.cfg', 'Falcon BMS User.cfg'):
        path = root / 'User' / 'Config' / filename
        if not path.is_file():
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('cp949', errors='replace')
        for match in re.finditer(r'^\s*set\s+g_sBriefingsDirectory\s+"([^"]*)"', text, re.I | re.M):
            if match[1]:
                selected = Path(os.path.expandvars(match[1]))
                if not selected.is_absolute():
                    selected = root / selected
            else:
                selected = root / 'User' / 'Briefings'
    return selected.resolve()


def migrate_data(destination, root, old_home=None):
    data = destination / 'data'
    data.mkdir(parents=True, exist_ok=True)
    old = Path(old_home or Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / APP_NAME)
    if not (data / 'settings.json').exists():
        config = json.loads((old / 'settings.json').read_text('utf-8')) if (old / 'settings.json').exists() else {}
        config.update(watch_dir=str(discover_briefings(root)), output_dir=str(root / 'User' / 'BriefingKR'), startup=False)
    else:
        config = json.loads((data / 'settings.json').read_text('utf-8'))
        config['startup'] = False
    (data / 'settings.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), 'utf-8')
    if not (data / 'briefings.sqlite').exists() and (old / 'briefings.sqlite').exists():
        with sqlite3.connect(old / 'briefings.sqlite') as source, sqlite3.connect(data / 'briefings.sqlite') as target:
            source.backup(target)
    return data


def release_payload(base=None):
    base = Path(base or (Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent))
    return base / 'payload'


def configure_launcher_watch(destination, enabled=True):
    """Per-user login sentinel detects direct launcher/game starts too."""
    return powershell(r'''
$ErrorActionPreference = 'Stop'
$p = $env:BMS_KR_PLAN | ConvertFrom-Json
$startup = [Environment]::GetFolderPath('Startup')
$path = Join-Path $startup 'BMS Korean Briefing Launcher Watch.lnk'
if ($p.enabled) {
 $s = New-Object -ComObject WScript.Shell
 $l = $s.CreateShortcut($path)
 $l.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
 $l.Arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $p.script + '"'
 $l.WorkingDirectory = $p.folder
 $l.WindowStyle = 7
 $l.Description = 'Detect BMS launchers and start Korean briefing automatically'
 $l.Save()
 Start-Process -FilePath $l.TargetPath -ArgumentList $l.Arguments -WorkingDirectory $p.folder -WindowStyle Hidden
} elseif (Test-Path -LiteralPath $path) {
 $s = New-Object -ComObject WScript.Shell
 $l = $s.CreateShortcut($path)
 if ($l.Arguments.Contains($p.script)) { Remove-Item -LiteralPath $path }
}
''', {'enabled': enabled, 'script': str(Path(destination) / 'launcher_watch.ps1'), 'folder': str(destination)})


def configure_manual_viewer(destination,enabled=True):
    powershell(r'''
$ErrorActionPreference='Stop'
$p=$env:BMS_KR_PLAN | ConvertFrom-Json
$shell=New-Object -ComObject WScript.Shell
$path=Join-Path ([Environment]::GetFolderPath('Desktop')) 'BMS Korean Briefing Viewer.lnk'
$link=$shell.CreateShortcut($path)
if ($p.enabled) {
 if ((Test-Path -LiteralPath $path) -and $link.TargetPath -ne $p.exe) { exit }
 $link.TargetPath=$p.exe
 $link.WorkingDirectory=$p.folder
 $link.Description='Open briefing and settings without starting BMS'
 $link.WindowStyle=7
 $link.Save()
} elseif ((Test-Path -LiteralPath $path) -and $link.TargetPath -eq $p.exe) {
 Remove-Item -LiteralPath $path
}
''',{'enabled':enabled,'exe':str(Path(destination)/'BMS-Korean-Briefing-Viewer.exe'),'folder':str(destination)})


def install(root, payload=None, integrate=True, old_home=None, progress=lambda value: None):
    root, destination = validate_root(root)
    payload = Path(payload or release_payload())
    source = payload / EXE_NAME
    if not source.is_file():
        raise ValueError('배포 프로그램 파일이 없습니다. 배포 ZIP 전체를 다시 압축 해제하세요.')
    checks = payload / 'release.json'
    if checks.exists():
        expected = json.loads(checks.read_text('utf-8'))['sha256']
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('배포 파일 무결성 검사 실패')
    prior = json.loads((destination / 'install.json').read_text('utf-8')) if (destination / 'install.json').exists() else {}
    allowed = [str(root / 'Launcher.exe'), str(root / 'Launcher' / 'FalconBMS_Alternative_Launcher.exe'), str(root / 'Bin' / 'x64' / 'Falcon BMS.exe')]
    discovery = powershell(DISCOVER, {'allowed': allowed, 'ours': str(destination / EXE_NAME)})
    default = next((p for p in allowed if Path(p).is_file()), None)
    if not default:
        raise ValueError('BMS 런처가 없습니다.')
    profiles = prior.get('profiles', {'default': {'target': default, 'arguments': '', 'working_directory': str(Path(default).parent)}})
    links = prior.get('shortcuts', [])
    updates = []
    progress('프로그램과 모델 복사 중…')
    destination.mkdir(parents=True, exist_ok=True)
    data = migrate_data(destination, root, old_home)
    backups = data / 'shortcut-backups'
    backups.mkdir(exist_ok=True)
    if integrate:
        for link in discovery['links']:
            identity = hashlib.sha256(link['path'].encode()).hexdigest()[:12]
            backup = backups / (identity + '.lnk')
            if not backup.exists():
                shutil.copy2(link['path'], backup)
            profiles[identity] = {k: link[k] for k in ('target', 'arguments', 'working_directory')}
            icon = link['icon'] if link['icon'] not in ('', ',0') else link['target'] + ',0'
            profiles[identity]['icon'] = icon
            updates.append({'path': link['path'], 'profile': identity, 'icon': icon})
            if not any(x['path'] == link['path'] for x in links):
                links.append({'path': link['path'], 'backup': str(backup), 'created': False})
    fresh = Path(discovery['desktop']) / 'Falcon BMS + Korean Briefing.lnk'
    if not any(x['path'] == str(fresh) for x in links):
        if fresh.exists():
            backup = backups / 'default-shortcut.lnk'
            shutil.copy2(fresh, backup)
            links.append({'path': str(fresh), 'backup': str(backup), 'created': False})
        else:
            links.append({'path': str(fresh), 'backup': '', 'created': True})
    # Also refresh shortcuts already integrated by an earlier installation.
    for link in links:
        if link['path'] not in discovery.get('managed', []) or link['path'] == str(fresh) or any(item['path'] == link['path'] for item in updates):
            continue
        identity = hashlib.sha256(link['path'].encode()).hexdigest()[:12]
        if identity in profiles:
            profile = profiles[identity]
            updates.append({'path': link['path'], 'profile': identity, 'icon': profile.get('icon') or profile['target'] + ',0'})
    updates.append({'path': str(fresh), 'profile': 'default', 'icon': default + ',0'})
    staged = destination / (EXE_NAME + '.new')
    shutil.copy2(source, staged)
    try:
        os.replace(staged, destination / EXE_NAME)
    except PermissionError:
        raise RuntimeError('실행 중인 브리핑 앱을 종료한 뒤 설치를 다시 실행하세요.')
    for name in ('초기설치안내.html', '초기설치안내.txt', 'THIRD-PARTY-NOTICES.txt', 'LICENSE.txt', 'release.json'):
        if (payload / name).exists():
            shutil.copy2(payload / name, destination / name)
    viewer=payload/'BMS-Korean-Briefing-Viewer.exe'
    if viewer.is_file():
        shutil.copy2(viewer,destination/viewer.name)
        configure_manual_viewer(destination)
    if (payload / 'licenses').exists():
        shutil.copytree(payload / 'licenses', destination / 'licenses', dirs_exist_ok=True)
    manifest = {'version': VERSION, 'bms_root': str(root), 'profiles': profiles, 'shortcuts': links, 'installed_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'launch_mode': 'with-bms'}
    (destination / 'install.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    watch_source = payload / 'launcher_watch.ps1'
    if watch_source.exists():
        shutil.copy2(watch_source, destination / 'launcher_watch.ps1')
        configure_launcher_watch(destination)
    (destination / 'Uninstall.cmd').write_text('@echo off\r\n"%~dp0' + EXE_NAME + '" --uninstall\r\n', 'ascii')
    (root / 'User' / 'BriefingKR').mkdir(exist_ok=True)
    progress('BMS 바로가기에 자동 번역 연결 중…')
    plan = {'exe': str(destination / EXE_NAME), 'folder': str(destination), 'links': updates}
    try:
        powershell(APPLY, plan)
    except Exception:
        powershell(RESTORE, {'exe': str(destination / EXE_NAME), 'original': default, 'links': links})
        raise
    remove_login_startup()
    progress('설치 완료')
    return destination


def deactivate(destination):
    destination = Path(destination).resolve()
    manifest = json.loads((destination / 'install.json').read_text('utf-8'))
    root, expected = validate_root(manifest['bms_root'])
    if expected != destination:
        raise ValueError('설치 위치 불일치')
    restored = powershell(RESTORE, {'exe': str(destination / EXE_NAME), 'original': manifest['profiles']['default']['target'], 'links': manifest['shortcuts']})
    remove_login_startup()
    manifest['launch_mode'] = 'disabled'
    (destination / 'install.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    configure_launcher_watch(destination, enabled=False)
    configure_manual_viewer(destination,enabled=False)
    return restored
