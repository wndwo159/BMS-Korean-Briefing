"""Render readable Korean briefing cards into BMS F-16/KTO DDS slots."""
import io
import os
import json
import hashlib
import tempfile
import threading
import struct
from pathlib import Path
from bs4 import BeautifulSoup
from PIL import Image

SLOTS = tuple(range(7982, 7998))
LATE_SLOTS = tuple(range(7990,7998))
LOCK = threading.Lock()


def write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def render_pages(markup, max_pages=16):
    """Capture the actual paper HTML with its bundled CSS/fonts, without re-typesetting."""
    from playwright.sync_api import sync_playwright, Error as BrowserError
    soup=BeautifulSoup(markup,'lxml')
    for tag in list(soup.find_all(True)):
        if not tag.name:continue
        if tag.name in ('script','style','iframe','object','embed','link','meta','base','img','video','audio','svg','form','input','button'):
            tag.decompose();continue
        for attr in list(tag.attrs):
            if attr not in ('class','id','colspan','rowspan','data-index'):del tag[attr]
    if not soup.select('.briefing-section'):raise ValueError('PRINT 또는 기록에서 브리핑을 먼저 여세요.')
    resources=Path(__file__).parent
    css=(resources/'briefing.css').read_text('utf-8')
    script=(resources/'paper_document.js').read_text('utf-8')
    # Same page typography, tables, paper texture and pagination as the viewer.
    css+='\nhtml,body{background:#ece7dc!important}body{--paper-width:940px}.viewer-shell{padding:0}.document-stage{margin:0;width:940px}.backing-board{padding:0;border:0;background:none;box-shadow:none}.backing-board::before,.backing-board::after,.reader-toolbar,.reader-status,.divider-tabs{display:none!important}.paper-page{box-shadow:none!important;scroll-margin-top:0}#briefing{gap:0} .paper-page::before{display:none}'
    doc='<!doctype html><html lang="ko"><meta charset="utf-8"><style>'+css+'</style><body><div id="briefing-source" hidden>'+str(soup.body or soup)+'</div><main class="viewer-shell"><div class="document-stage"><div class="backing-board"><article id="briefing"></article><nav id="sections"></nav></div></div></main><script>'+script+'</script><script>const packet=new BriefingPaper.Packet();packet.mode="";packet.host.className="";packet.render(document.getElementById("briefing-source").innerHTML);</script></body></html>'
    pages=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                context=browser.new_context(viewport={'width':1200,'height':1500},device_scale_factor=2)
                context.route('**/*',lambda route:route.abort())
                page=context.new_page();page.set_content(doc,wait_until='load',timeout=30000)
                page.evaluate('document.fonts.ready')
                page.wait_for_function('packet.ready && packet.pages.length > 0',timeout=30000)
                count=page.locator('.paper-page').count()
                if count>max_pages:raise ValueError(f'니보드 용량({max_pages}쪽)을 초과했습니다. 내용을 자르지 않고 중단했습니다.')
                for i in range(count):
                    box=page.locator('.paper-page').nth(i).bounding_box()
                    if box and box['height']>6000:raise ValueError('한 페이지가 너무 깁니다. 내용을 나눈 뒤 다시 생성하세요. 원본 니보드는 변경하지 않았습니다.')
                    raw=page.locator('.paper-page').nth(i).screenshot(type='png',animations='disabled',timeout=30000)
                    with Image.open(io.BytesIO(raw)) as image:pages.append(image.convert('RGB'))
            finally:browser.close()
    except BrowserError as exc:
        raise ValueError('HTML 니보드 렌더링 실패. Microsoft Edge가 설치되어 있는지 확인하세요. '+str(exc).splitlines()[0]) from exc
    return pages


def pack_page(page, aspect='a4'):
    # Model stretches each 1024x2048 half to a paper-shaped panel. Compress the
    # HTML A4 capture into that UV rectangle; the model restores its proportions.
    if aspect not in ('a4','texture'):raise ValueError('지원하지 않는 니보드 비율 보정입니다.')
    if aspect=='a4':return page.resize((1024,2048),Image.Resampling.LANCZOS)
    from PIL import ImageOps
    result=Image.new('RGB',(1024,2048),'#ece7dc')
    fitted=ImageOps.contain(page,(1024,2048),Image.Resampling.LANCZOS)
    result.paste(fitted,((1024-fitted.width)//2,(2048-fitted.height)//2))
    return result


def target_dir(root):
    root=Path(root).resolve()
    if not (root/'Bin/x64/Falcon BMS.exe').is_file():raise ValueError('BMS 설치 경로가 올바르지 않습니다.')
    target=root/'Data/TerrData/Objects/KoreaObj'
    for slot in SLOTS:
        p=target/f'{slot}.dds'
        if not p.is_file():raise ValueError(f'KTO/F-16 니보드 텍스처가 없습니다: {p}')
        b=p.read_bytes()[:128]
        if b[:4]!=b'DDS ' or b[12:20] != (2048).to_bytes(4,'little')*2 or b[84:88] not in (b'DXT1',b'DXT5'):
            raise ValueError(f'지원하지 않는 니보드 형식: {p.name}')
    return target


def encode_dds(canvas, original):
    """Retain the installed texture's compression and mip-level count."""
    fmt=original[84:88].decode('ascii')
    levels=max(1,min(12,struct.unpack_from('<I',original,28)[0]))
    image=canvas.convert('RGBA' if fmt=='DXT5' else 'RGB')
    data=[];header=None
    for level in range(levels):
        out=io.BytesIO();image.save(out,format='DDS',pixel_format=fmt);encoded=out.getvalue()
        if header is None:header=bytearray(encoded[:128])
        data.append(encoded[128:])
        image=image.resize((max(1,image.width//2),max(1,image.height//2)),Image.Resampling.LANCZOS)
    if levels>1:
        struct.pack_into('<I',header,8,struct.unpack_from('<I',header,8)[0]|0x20000)
        struct.pack_into('<I',header,28,levels)
        struct.pack_into('<I',header,108,0x1000|0x400008)
    return bytes(header)+b''.join(data)


def apply(root, home, markup, first_page=True, aspect="a4"):
    if not LOCK.acquire(blocking=False):raise ValueError('니보드 작업이 진행 중입니다.')
    try:
        target=target_dir(root)
        pages=render_pages(markup,max_pages=32 if first_page else 16)
        home=Path(home); export=home/'kneeboard';export.mkdir(parents=True,exist_ok=True)
        key=hashlib.sha256(str(target.resolve()).lower().encode()).hexdigest()[:16]
        backup=export/('original-'+key);backup.mkdir(exist_ok=True)
        before={slot:(target/f'{slot}.dds').read_bytes() for slot in SLOTS}
        generated={}
        selected=SLOTS if first_page else LATE_SLOTS
        for slot in SLOTS:
            original=backup/f'{slot}.dds'
            if not original.exists():write_bytes(original,before[slot])
            generated[slot]=original.read_bytes()
        for i,slot in enumerate(selected):
            canvas=Image.new('RGB',(2048,2048),'#eeeadd')
            used=False
            for side in range(2):
                n=i*2+side
                if n<len(pages):canvas.paste(pack_page(pages[n],aspect),(side*1024,0));used=True
            # Untouched slots retain original checklists, replacing any old export.
            original=backup/f'{slot}.dds'
            if not original.exists():write_bytes(original,before[slot])
            if used:
                generated[slot]=encode_dds(canvas,original.read_bytes())
            else:generated[slot]=original.read_bytes()
        for i,p in enumerate(pages):p.save(export/f'page-{i+1:02d}.png')
        try:
            for slot,data in generated.items():write_bytes(target/f'{slot}.dds',data)
        except OSError:
            for slot,data in before.items():write_bytes(target/f'{slot}.dds',data)
            raise
        info={'pages':len(pages),'target':str(target),'backup':str(backup),'slots':[f'{n}.dds' for n in SLOTS], 'first_page':first_page,'aspect':aspect,'message':f'HTML 브리핑 {len(pages)}쪽을 KTO / F-16 니보드에 적용했습니다. 좌우 니보드 {1 if first_page else 9}쪽부터 확인하세요. 이미 비행 중이면 다음 조종석 진입 때 확인하세요.'}
        write_bytes(export/'last.json',json.dumps(info,ensure_ascii=False,indent=2).encode('utf-8'))
        return info
    finally:LOCK.release()


def restore(root, home):
    with LOCK:
        target=target_dir(root)
        key=hashlib.sha256(str(target.resolve()).lower().encode()).hexdigest()[:16]
        backup=Path(home)/'kneeboard'/('original-'+key)
        available=[s for s in SLOTS if (backup/f'{s}.dds').is_file()]
        if not available:raise ValueError('원본 니보드 백업이 없습니다.')
        before={s:(target/f'{s}.dds').read_bytes() for s in SLOTS}
        try:
            for s in available:write_bytes(target/f'{s}.dds',(backup/f'{s}.dds').read_bytes())
        except OSError:
            for s,data in before.items():write_bytes(target/f'{s}.dds',data)
            raise
        return {'message':'원본 니보드 복원 완료. 다음 조종석 진입 때 확인하세요.'}
