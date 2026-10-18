"""Prepare only redistributable program assets; never package user data."""
import hashlib
import html
import importlib.metadata
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
from app_version import VERSION
UI_RELEASE = VERSION
PAYLOAD = ROOT / 'payload'
RELEASE = ROOT / 'release'


def prepare():
    PAYLOAD.mkdir(exist_ok=True)
    RELEASE.mkdir(exist_ok=True)
    binary = ROOT / 'dist' / 'BMS-Korean-Briefing.exe'
    shutil.copy2(binary, PAYLOAD / binary.name)
    shutil.copy2(ROOT/'dist'/'BMS-Korean-Briefing-Viewer.exe',PAYLOAD/'BMS-Korean-Briefing-Viewer.exe')
    for name in ('초기설치안내.txt', 'LICENSE.txt', 'launcher_watch.ps1'):
        shutil.copy2(ROOT / name, PAYLOAD / name)
    text = (ROOT / '초기설치안내.txt').read_text('utf-8-sig')
    paragraphs = text.split('\n\n')
    markup = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>BMS Korean Briefing · 초기 설치</title><style>body{max-width:900px;margin:50px auto;padding:0 25px;font:15px/1.9 "Malgun Gothic",sans-serif;background:#0e1821;color:#dce8ee}h1{font-size:32px;color:#c2dcaf}h2{font-size:21px;border-bottom:1px solid #3b4f5c;padding-bottom:10px;margin-top:35px}p{white-space:pre-wrap;color:#b8cbd5}.tag{color:#96b47d;letter-spacing:3px;font-size:11px}button{padding:9px 18px;cursor:pointer}@media print{body{background:white;color:black}p{color:black}button{display:none}}</style><div class="tag">BMS KOREAN BRIEFING / INSTALLATION GUIDE</div><h1>처음 설치하는 분을 위한 안내</h1><button onclick="print()">인쇄 / PDF 저장</button>'
    for paragraph in paragraphs:
        if len(paragraph.splitlines()) == 1 and paragraph[:1].isdigit():
            markup += '<h2>' + html.escape(paragraph) + '</h2>'
        else:
            lines = paragraph.splitlines()
            if lines and len(lines[0]) > 1 and lines[0][0].isdigit() and lines[0][1] == '.':
                markup += '<h2>' + html.escape(lines[0]) + '</h2><p>' + html.escape('\n'.join(lines[1:])) + '</p>'
            else:
                markup += '<p>' + html.escape(paragraph) + '</p>'
    (PAYLOAD / '초기설치안내.html').write_text(markup + '</html>', 'utf-8')
    licenses = PAYLOAD / 'licenses'
    licenses.mkdir(exist_ok=True)
    notices = ['BMS Korean Briefing — third-party notices', '', 'Argos EN-KO 1.1 model', 'Source: https://github.com/argosopentech/argospm-index', 'Model: https://argos-net.com/v1/translate-en_ko-1_1.argosmodel', 'Model licensing confirmation (MIT/CC0): https://github.com/argosopentech/argos-translate/issues/533', 'Model credits: licenses/Argos-EN-KO-README.md', 'Only CTranslate2 model and SentencePiece tokenizer are bundled; no Stanza runtime/model is bundled.', '']
    shutil.copy2(ROOT / 'models' / 'en_ko' / 'README.md', licenses / 'Argos-EN-KO-README.md')
    for font_license in (ROOT / 'ui-assets').glob('*LICENSE.txt'):
        shutil.copy2(font_license, licenses / font_license.name)
    notices.extend(['', 'Paper UI fonts: Pretendard (SIL OFL 1.1), IBM Plex Sans Condensed and IBM Plex Mono (SIL OFL 1.1).', 'Font licenses are included alongside the model notices. Fonts are embedded in the document CSS for offline use.'])
    request = urllib.request.Request('https://raw.githubusercontent.com/argosopentech/argos-translate/master/LICENSE', headers={'User-Agent': 'BMS-Korean-Briefing'})
    (licenses / 'Argos-LICENSE.txt').write_bytes(urllib.request.urlopen(request, timeout=20).read())
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata['Name']
        notices.append(name + ' ' + distribution.version)
        for item in distribution.files or []:
            if any(marker in item.name.lower() for marker in ('license', 'copying', 'notice')):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    destination = licenses / name / Path(*[part for part in item.parts if part not in ('..', '.')])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    for path in (Path(sys.base_prefix) / 'tcl').glob('*/license.terms'):
        shutil.copy2(path, licenses / (path.parent.name + '-license.terms'))
    (PAYLOAD / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices), 'utf-8')
    (PAYLOAD / 'release.json').write_text(json.dumps({'version': VERSION, 'filename': binary.name, 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}, indent=2), 'utf-8')


def package():
    files = [ROOT / 'dist' / 'BMS-Korean-Briefing-Setup.exe', PAYLOAD / '초기설치안내.html', PAYLOAD / '초기설치안내.txt', PAYLOAD / 'THIRD-PARTY-NOTICES.txt', PAYLOAD / 'LICENSE.txt']
    for path in files:
        shutil.copy2(path, RELEASE / path.name)
    for source in (PAYLOAD / 'licenses').rglob('*'):
        if source.is_file():
            target = RELEASE / 'licenses' / source.relative_to(PAYLOAD / 'licenses')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    sums = '\n'.join(hashlib.sha256((RELEASE / path.name).read_bytes()).hexdigest() + '  ' + path.name for path in files)
    (RELEASE / 'SHA256SUMS.txt').write_text(sums + '\n', 'utf-8')
    archive = ROOT / 'dist' / f'BMS-Korean-Briefing-{UI_RELEASE}-Windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as output:
        for path in RELEASE.rglob('*'):
            if path.is_file():
                output.write(path, f'BMS-Korean-Briefing-{UI_RELEASE}/' + path.relative_to(RELEASE).as_posix())
    sources = ['main.py','entrypoint.py','installer.py','installer_core.py','offline_translation.py','military_prose.py','briefing_render.py','viewer.html','briefing.css','glossary.json','requirements.txt','install_model.py','setup.ps1','build.ps1','prepare_release.py','test_app.py','test_installation.py','README.md','초기설치안내.txt','LICENSE.txt']
    sources += ['app_version.py','updater.py','update_install.py','update_settings.js','update_source.json','test_updates.py','RELEASING.md','.github/workflows/release.yml','kneeboard.py','test_kneeboard.py','BMS-Korean-Briefing.spec','BMS-Korean-Briefing-Setup.spec','BMS-Korean-Briefing-Viewer.spec','build_ui.py','paper_document.js','paper-theme.css','viewer.template.html','standalone.template.html','standalone.html','UI-DESIGN-NOTES.md','UI-CONTINUOUS-READING.md','launcher_watch.ps1','military_terms.py','test_military_terms.py','ollama_manager.py','ollama_settings.js','test_ollama_setup.py','manual_launcher.py','test_manual_viewer.py','UI-SECTION-SHEETS.md']
    with zipfile.ZipFile(ROOT / 'dist' / f'BMS-Korean-Briefing-{UI_RELEASE}-source.zip', 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for name in sources:
            output.write(ROOT / name, name)
        for asset in (ROOT / 'ui-assets').glob('*'):
            if asset.is_file():
                output.write(asset, 'ui-assets/' + asset.name)
    print(archive)


if __name__ == '__main__':
    package() if '--package' in sys.argv else prepare()
