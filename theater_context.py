"""Read BMS's selected theater; persist the selection with each PRINT document."""
import json
from pathlib import Path
from html import escape
from bs4 import BeautifulSoup


def registry_selection(root):
    try:import winreg
    except ImportError:return ''
    for hive in (winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive,r'SOFTWARE\Benchmark Sims',0,winreg.KEY_READ|view) as parent:
                    for i in range(winreg.QueryInfoKey(parent)[0]):
                        try:
                            with winreg.OpenKey(parent,winreg.EnumKey(parent,i)) as child:
                                base=Path(winreg.QueryValueEx(child,'baseDir')[0]).resolve()
                                if base==Path(root).resolve():return str(winreg.QueryValueEx(child,'curTheater')[0]).strip()
                        except (OSError,ValueError):continue
            except OSError:continue
    return ''


def describe(name):
    lower=name.lower()
    if 'israel' in lower:code,label,tone='ISRAEL','이스라엘 전장','desert'
    elif 'korea' in lower or 'kto' in lower:code,label,tone='KTO','한반도 전장','olive'
    elif 'balkan' in lower:code,label,tone='BALKANS','발칸 전장','slate'
    elif name:code,label,tone=name.upper(),name,'slate'
    else:code,label,tone='UNCONFIRMED','전장 미확인','slate'
    return dict(code=code,label=label,name=name,tone=tone,source='bms-registry' if name else 'unknown')


def current(root):
    return describe(registry_selection(root))


def marker(context):
    return '<div hidden data-bms-theater="'+escape(json.dumps(context,ensure_ascii=False),quote=True)+'"></div>'


def saved(markup):
    node=BeautifulSoup(markup,'html.parser').select_one('[data-bms-theater]')
    if node:
        try:
            value=json.loads(node['data-bms-theater'])
            if isinstance(value,dict):return value
        except (TypeError,ValueError):pass
    return describe('')
