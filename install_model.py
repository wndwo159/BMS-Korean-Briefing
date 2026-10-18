"""Install only the fixed EN-KO model from the official Argos package index."""
import hashlib,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).parent/'models'
URL='https://argos-net.com/v1/translate-en_ko-1_1.argosmodel'
SHA256='e03d8e65e6d44525ec5808c3409fcf8728c76c2c76925372b6d3dc3278de17fc'

def install():
    if (ROOT/'en_ko'/'model'/'model.bin').exists():
        print('EN-KO offline model already installed.');return
    ROOT.mkdir(exist_ok=True);archive=ROOT/'en-ko.argosmodel'
    req=urllib.request.Request(URL,headers={'User-Agent':'BMS-Korean-Briefing/1.0'})
    print('Downloading one EN-KO model (121 MB). No briefing data is uploaded.')
    if not archive.exists():
        with urllib.request.urlopen(req,timeout=60) as response,archive.open('wb') as f:
            while chunk:=response.read(1024*1024):f.write(chunk)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise RuntimeError('Model checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            if not (ROOT/member.filename).resolve().is_relative_to(ROOT.resolve()):raise RuntimeError('Invalid archive path')
        z.extractall(ROOT)
    print('Offline Korean translation ready.')
if __name__=='__main__':install()
