import html,re
from bs4 import BeautifulSoup
from offline_translation import LABELS

def pair(ko,en,error=False):
    return '<span class="translation-pair"><span class="kr'+(' error' if error else '')+'">'+html.escape(ko)+'</span><span class="en">'+html.escape(en)+'</span></span>'

def render(soup):
    pre=soup.find('pre')
    sections=[]
    if not pre:
        body=soup.body or soup
        title=body.find(['h1','h2'])
        label=title.get_text(' ',strip=True) if title else '브리핑'
        sections=[{'id':'section-1','title':label,'source':label}]
        return '<section class="briefing-section" id="section-1"><h2 data-index="01">'+html.escape(label)+'</h2><div class="section-body">'+''.join(str(c) for c in body.contents)+'</div></section>',sections
    groups=[];current={'source':'Briefing Record','title':'브리핑 기록','lines':[]}
    for child in pre.children:
        if not hasattr(child,'select_one'):continue
        original=child.select_one('.en');translated=child.select_one('.kr')
        en=original.get_text() if original else child.get_text()
        ko=translated.get_text() if translated else en
        error=bool(child.select_one('.error'))
        if not en.strip():continue
        # Section boundaries are detected from the actual PRINT text, including unknown headings.
        stripped=en.strip()
        heading=(not en[0].isspace() and len(stripped)<100 and re.match(r'[A-Za-z]',stripped)
                 and not stripped.startswith(('BRIEFING RECORD','END_OF_BRIEFING'))
                 and (stripped.endswith(':') or stripped in ('Iff','Link 16') or re.match(r'^[A-Za-z -]+:\s*\t',stripped)))
        if heading:
            if current['lines']:groups.append(current)
            source=stripped.split('\t')[0].rstrip(': ')
            title=LABELS.get(source,ko.strip().rstrip(':'))
            current={'source':source,'title':title,'lines':[]}
            if '\t' in stripped:current['lines'].append((ko.strip().split('\t',1)[1] if '\t' in ko else stripped.split('\t',1)[1],stripped.split('\t',1)[1],False))
        else:current['lines'].append((ko,en,error))
    if current['lines']:groups.append(current)
    result=[]
    for index,g in enumerate(groups,1):
        identity=f'section-{index}';sections.append({'id':identity,'title':g['title'],'source':g['source']})
        result.append(f'<section class="briefing-section" id="{identity}"><h2 data-index="{index:02d}">'+html.escape(g['title'])+'<small class="source-heading">'+html.escape(g['source'].upper())+'</small></h2><div class="section-body">')
        rows=[]
        def flush():
            if not rows:return
            result.append('<div class="table-scroll"><table><tbody>')
            for kr,en,error in rows:
                original=re.split(r'\t+',en.strip());local=re.split(r'\t+',kr.strip())
                if len(local)!=len(original):local=original
                is_header=sum(x.strip().endswith(':') for x in original)>len(original)/2
                tag='th' if is_header else 'td'
                result.append('<tr>'+''.join('<'+tag+'>'+pair(k.strip(),e.strip(),error)+'</'+tag+'>' for k,e in zip(local,original))+'</tr>')
            result.append('</tbody></table></div>');rows.clear()
        for ko,en,error in g['lines']:
            if re.fullmatch(r'[-\s]+',en):continue
            if '\t' in en.strip():rows.append((ko,en,error))
            else:
                flush();result.append('<p>'+pair(ko.strip(),en.strip(),error)+'</p>')
        flush();result.append('</div></section>')
    return ''.join(result),sections

def metadata(text):
    def extract(pattern,default='—'):
        m=re.search(pattern,text,re.M);return m.group(1).strip() if m else default
    return {'callsign':extract(r'^\s*([A-Za-z][A-Za-z0-9]+)\s+\([A-Z]+\)'),
            'mission':extract(r'^\s*[A-Za-z][A-Za-z0-9]+\s+\(([A-Z]+)\)'),
            'package':extract(r'^\s*Package #:\s*([^\s(]+)'),
            'tot':extract(r'^\s*Time on Target:\s*(\S+)'),
            'generated':extract(r'BRIEFING RECORD generated at (.+?)\.')}
