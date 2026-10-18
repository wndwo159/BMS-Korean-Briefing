import io
import struct
from pathlib import Path
import pytest
from PIL import Image
import kneeboard as kb

SAMPLE='''<section class="briefing-section"><h2>비행계획 / 스티어포인트<small class="source-heading">STEERPOINTS</small></h2><div class="section-body"><div class="table-wrap"><table><tr><th>#</th><th>시각</th><th>고도</th></tr><tr><td>1</td><td><span class="kr">22:15:28z</span><span class="en">duplicate english</span></td><td>24.0M</td></tr></table></div></div></section><section class="briefing-section"><h2>피아식별 (Iff)<small class="source-heading">IFF</small></h2><div class="section-body">SECRET-OMIT</div></section>'''

def fake_bms(tmp_path):
    root=tmp_path/'BMS';exe=root/'Bin/x64/Falcon BMS.exe';exe.parent.mkdir(parents=True);exe.touch()
    target=root/'Data/TerrData/Objects/KoreaObj';target.mkdir(parents=True)
    out=io.BytesIO();Image.new('RGB',(2048,2048),'white').save(out,format='DDS',pixel_format='DXT1')
    for s in kb.SLOTS:(target/f'{s}.dds').write_bytes(out.getvalue())
    return root,target,out.getvalue()

def test_html_capture_and_capacity():
    pages=kb.render_pages(SAMPLE)
    assert len(pages)==1
    assert pages[0].width==1880 and 1.40<pages[0].height/pages[0].width<1.43
    assert kb.pack_page(pages[0]).size==(1024,2048)
    with pytest.raises(ValueError,match='0쪽'):kb.render_pages(SAMPLE,max_pages=0)

def test_dds_backup_repeat_and_restore(tmp_path,monkeypatch):
    monkeypatch.setattr(kb,"render_pages",lambda *a,**k:[Image.new("RGB",(1880,2660),"#ece7dc")])
    root,target,original=fake_bms(tmp_path);home=tmp_path/'home'
    info=kb.apply(root,home,SAMPLE,first_page=False)
    changed=(target/'7990.dds').read_bytes()
    assert changed!=original and changed[84:88]==b'DXT1'
    assert Image.open(io.BytesIO(changed)).size==(2048,2048)
    assert (Path(info['backup'])/'7990.dds').read_bytes()==original
    kb.apply(root,home,SAMPLE,first_page=False)
    assert (Path(info['backup'])/'7990.dds').read_bytes()==original
    kb.restore(root,home)
    assert all((target/f'{s}.dds').read_bytes()==original for s in kb.SLOTS)

def test_failed_install_rolls_back(tmp_path,monkeypatch):
    root,target,original=fake_bms(tmp_path);real=kb.write_bytes;failed=False
    monkeypatch.setattr(kb,"render_pages",lambda *a,**k:[Image.new("RGB",(1880,2660),"#ece7dc")])
    def fail_once(path,data):
        nonlocal failed
        if Path(path)==target/'7991.dds' and not failed:
            failed=True;raise OSError('locked')
        real(path,data)
    monkeypatch.setattr(kb,'write_bytes',fail_once)
    with pytest.raises(OSError):kb.apply(root,tmp_path/'home',SAMPLE)
    assert all((target/f'{s}.dds').read_bytes()==original for s in kb.SLOTS)

def test_overflow_and_invalid_root(tmp_path):
    with pytest.raises(ValueError):kb.target_dir(tmp_path)

def test_installed_dxt5_mipmap_format():
    original=bytearray(128);original[84:88]=b'DXT5';struct.pack_into('<I',original,28,12)
    data=kb.encode_dds(Image.new('RGB',(2048,2048),'#eeeadd'),original)
    assert data[84:88]==b'DXT5'
    assert struct.unpack_from('<I',data,28)[0]==12
    assert len(data)==5592560
    with Image.open(io.BytesIO(data)) as image:
        image.load();assert image.size==(2048,2048)


def test_switch_first_page_cleans_previous_export(tmp_path,monkeypatch):
    root,target,original=fake_bms(tmp_path);home=tmp_path/'home'
    monkeypatch.setattr(kb,'render_pages',lambda *a,**k:[Image.new('RGB',(1880,2660),'#ece7dc')])
    kb.apply(root,home,SAMPLE,first_page=False)
    assert (target/'7990.dds').read_bytes()!=original
    kb.apply(root,home,SAMPLE,first_page=True)
    assert (target/'7982.dds').read_bytes()!=original
    assert (target/'7990.dds').read_bytes()==original
    kb.restore(root,home)
    assert all((target/f'{s}.dds').read_bytes()==original for s in kb.SLOTS)
