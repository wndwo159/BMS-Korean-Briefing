"""Small user-facing launcher: the adjacent installed service owns data and settings."""
import ctypes
from pathlib import Path
import subprocess
import sys


def run():
    base=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    app=base/'BMS-Korean-Briefing.exe'
    if not app.is_file() or not (base/'install.json').is_file():
        ctypes.windll.user32.MessageBoxW(None,'설치된 BMS User\\Plugins\\BMS-Korean-Briefing 폴더의 뷰어 EXE를 실행하세요. 먼저 배포본의 Setup으로 설치할 수 있습니다.','BMS Korean Briefing',48)
        return 1
    subprocess.Popen([str(app),'--open-viewer'],cwd=base,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return 0


if __name__=='__main__':sys.exit(run())
