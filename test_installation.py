import json
import sqlite3
from pathlib import Path
import pytest
import entrypoint
import installer_core as installer


def fake_root(tmp_path):
    root = tmp_path / 'Falcon BMS 한글 경로'
    (root / 'Bin' / 'x64').mkdir(parents=True)
    (root / 'Bin' / 'x64' / 'Falcon BMS.exe').write_bytes(b'fixture-not-executable')
    (root / 'User').mkdir()
    (root / 'Launcher.exe').write_bytes(b'fixture-not-executable')
    return root


def test_selected_game_executable_and_nested_folder_find_root(tmp_path):
    root=fake_root(tmp_path)
    assert installer.validate_root(root/'Bin/x64/Falcon BMS.exe')[0]==root.resolve()
    assert installer.validate_root(root/'User')[0]==root.resolve()


def test_session_waits_for_exact_game_and_exits_with_launcher():
    ticks = [0]
    def wait(seconds): ticks[0] += seconds
    assert entrypoint.wait_for_game(lambda: ticks[0] >= 3, lambda: True, wait, clock=lambda: ticks[0])
    ticks[0] = 0
    assert not entrypoint.wait_for_game(lambda: False, lambda: False, wait, clock=lambda: ticks[0], launcher_grace=2)
    assert ticks[0] == 2


def test_monitor_exit_has_grace_and_resets():
    ticks = [0]
    requested = []
    class Stop:
        def wait(self, seconds):
            ticks[0] += seconds
            return ticks[0] > 20
    entrypoint.monitor_exit(lambda: ticks[0] in (1, 2, 5), lambda: requested.append(ticks[0]), Stop(), clock=lambda: ticks[0], grace=3)
    assert requested == [9]


def test_process_detection_rejects_other_installations(tmp_path):
    root = fake_root(tmp_path)
    assert entrypoint.game_running(root, [{'exe': str(root / 'Bin' / 'x64' / 'Falcon BMS.exe')}])
    assert not entrypoint.game_running(root, [{'exe': str(tmp_path / 'unrelated' / 'Falcon BMS.exe')}, {'exe': None}])


def test_launcher_handoff_keeps_waiting_for_user_launch(tmp_path):
    root=fake_root(tmp_path)
    delegated=root/'Launcher'/'FalconBMS_Alternative_Launcher.exe'
    assert entrypoint.launcher_running(root/'Launcher.exe',[{'exe':str(delegated)}])
    assert entrypoint.launcher_running(delegated,[{'exe':str(root/'Launcher.exe')}])
    assert not entrypoint.launcher_running(root/'Launcher.exe',[{'exe':str(tmp_path/'other'/'Launcher.exe')}])
    ticks=[0]
    def wait(seconds):ticks[0]+=seconds
    assert entrypoint.wait_for_game(lambda:ticks[0]>=240,lambda:True,wait,clock=lambda:ticks[0])
    ticks[0]=0
    assert entrypoint.wait_for_game(lambda:ticks[0]>=65,lambda:False,wait,clock=lambda:ticks[0])


def test_windows_arguments_round_trip():
    assert entrypoint.split_arguments('-window -profile "a b"') == ['-window', '-profile', 'a b']


def test_single_session_lock(tmp_path):
    path = tmp_path / 'session.lock'
    first = entrypoint.acquire_lock(path)
    assert first is not None
    assert entrypoint.acquire_lock(path) is None
    first.close()
    again = entrypoint.acquire_lock(path)
    assert again is not None
    again.close()


def test_install_migrate_backup_upgrade_and_deactivate(tmp_path, monkeypatch):
    root = fake_root(tmp_path)
    desktop = tmp_path / 'Desktop'; desktop.mkdir()
    link = desktop / 'Falcon BMS.lnk'; link.write_bytes(b'original-shortcut')
    payload = tmp_path / 'payload'; payload.mkdir()
    (payload / installer.EXE_NAME).write_bytes(b'new-program')
    (payload / 'launcher_watch.ps1').write_text('# test sentinel', 'utf-8')
    old = tmp_path / 'old'; old.mkdir()
    (old / 'settings.json').write_text(json.dumps({'startup': True, 'provider': 'offline'}))
    with sqlite3.connect(old / 'briefings.sqlite') as db:
        db.execute('CREATE TABLE fixture(value TEXT)')
        db.execute("INSERT INTO fixture VALUES ('cache-kept')")
    calls = []
    discovery = {'desktop': str(desktop), 'links': [{'path': str(link), 'target': str(root / 'Launcher.exe'), 'arguments': '-profile "a b"', 'working_directory': str(root), 'icon': 'original-icon,0'}]}
    def shell(script, plan):
        calls.append((script, plan))
        return discovery if script == installer.DISCOVER else []
    monkeypatch.setattr(installer, 'powershell', shell)
    monkeypatch.setattr(installer, 'remove_login_startup', lambda: None)
    dest = installer.install(root, payload, old_home=old)
    manifest = json.loads((dest / 'install.json').read_text('utf-8'))
    assert (dest / 'launcher_watch.ps1').read_text('utf-8') == '# test sentinel'
    assert any(plan.get('enabled') is True for script, plan in calls)
    assert dest == root / 'User' / 'Plugins' / installer.APP_NAME
    profile = next(v for k, v in manifest['profiles'].items() if k != 'default')
    assert profile['arguments'] == '-profile "a b"'
    assert Path(manifest['shortcuts'][0]['backup']).read_bytes() == b'original-shortcut'
    assert json.loads((dest / 'data' / 'settings.json').read_text('utf-8'))['startup'] is False
    with sqlite3.connect(dest / 'data' / 'briefings.sqlite') as db:
        assert db.execute('SELECT value FROM fixture').fetchone()[0] == 'cache-kept'
    discovery['links'] = []
    installer.install(root, payload, old_home=old)
    assert json.loads((dest / 'install.json').read_text('utf-8'))['profiles'] == manifest['profiles']
    installer.deactivate(dest)
    assert any(script == installer.RESTORE for script, plan in calls)
    assert calls[-1][1]['enabled'] is False
    assert (dest / 'data' / 'briefings.sqlite').exists()
    assert json.loads((dest / 'install.json').read_text('utf-8'))['launch_mode'] == 'disabled'


def test_invalid_install_and_corrupt_payload_do_not_touch_shortcuts(tmp_path, monkeypatch):
    with pytest.raises(ValueError): installer.validate_root(tmp_path)
    root = fake_root(tmp_path); payload = tmp_path / 'payload'; payload.mkdir()
    (payload / installer.EXE_NAME).write_bytes(b'corrupt')
    (payload / 'release.json').write_text(json.dumps({'sha256': 'wrong'}))
    monkeypatch.setattr(installer, 'powershell', lambda *args: pytest.fail('must not touch shortcuts'))
    with pytest.raises(ValueError): installer.install(root, payload)
    assert not (root / 'User' / 'Plugins').exists()


def test_real_windows_shortcut_round_trip_in_temp_folder(tmp_path):
    # Exercises the real Windows shell COM integration without touching user shortcuts.
    folder = tmp_path / "한글 O'Brien"; folder.mkdir()
    original = folder / 'original.exe'; original.write_bytes(b'not-executed')
    installed = folder / 'installed.exe'; installed.write_bytes(b'not-executed')
    link = folder / 'test.lnk'; backup = folder / 'backup.lnk'
    create = r'''
    $p=$env:BMS_KR_PLAN | ConvertFrom-Json
    $s=New-Object -ComObject WScript.Shell
    $l=$s.CreateShortcut($p.link)
    $l.TargetPath=$p.original
    $l.Arguments='-profile "hello world"'
    $l.Save()
    Copy-Item -LiteralPath $p.link -Destination $p.backup
    '''
    installer.powershell(create, {'link': str(link), 'original': str(original), 'backup': str(backup)})
    installer.powershell(installer.APPLY, {'exe': str(installed), 'folder': str(folder), 'links': [{'path': str(link), 'profile': 'test', 'icon': str(original) + ',0'}]})
    read = r'''
    [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding
    $p=$env:BMS_KR_PLAN | ConvertFrom-Json
    $s=New-Object -ComObject WScript.Shell
    $l=$s.CreateShortcut($p.link)
    [pscustomobject]@{target=$l.TargetPath;arguments=$l.Arguments} | ConvertTo-Json -Compress
    '''
    assert installer.powershell(read, {'link': str(link)})['arguments'] == '--with-bms --profile test'
    installer.powershell(installer.RESTORE, {'exe': str(installed), 'original': str(original), 'links': [{'path': str(link), 'created': False, 'backup': str(backup)}]})
    restored = installer.powershell(read, {'link': str(link)})
    assert restored['target'] == str(original)
    assert restored['arguments'] == '-profile "hello world"'


def test_briefing_path_respects_user_cfg_override(tmp_path):
    root = fake_root(tmp_path)
    cfg = root / 'User' / 'Config'; cfg.mkdir()
    (cfg / 'falcon bms.cfg').write_text('set g_sBriefingsDirectory "User\\Export"\n', 'utf-8')
    assert installer.discover_briefings(root) == (root / 'User' / 'Export').resolve()
    (cfg / 'Falcon BMS User.cfg').write_text('set g_sBriefingsDirectory ""\n', 'utf-8')
    assert installer.discover_briefings(root) == (root / 'User' / 'Briefings').resolve()


def test_rapid_restart_launches_original_even_with_session_lock(tmp_path,monkeypatch):
    root=fake_root(tmp_path)
    app=tmp_path/'app';app.mkdir()
    manifest={'bms_root':str(root),'profiles':{'default':{'target':str(root/'Launcher.exe'),'arguments':'-window','working_directory':str(root)}}}
    (app/'install.json').write_text(json.dumps(manifest),'utf-8')
    monkeypatch.setattr(entrypoint,'executable_directory',lambda:app)
    monkeypatch.setattr(entrypoint,'acquire_lock',lambda path:None)
    monkeypatch.setattr(entrypoint,'game_running',lambda root:False)
    monkeypatch.setattr(entrypoint,'launcher_running',lambda path:False)
    monkeypatch.setenv('BMS_KR_DATA',str(app/'data'))
    calls=[]
    monkeypatch.setattr(entrypoint.subprocess,'Popen',lambda args,**kwargs:calls.append(args))
    assert entrypoint.run(['--with-bms'])==0
    assert calls==[[str(root/'Launcher.exe'),'-window']]
