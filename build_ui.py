"""Build self-contained presentation assets. No backend behavior is modified."""
import base64
from pathlib import Path
ROOT=Path(__file__).parent

def build():
    fonts=[('Pretendard','PretendardVariable.woff2','100 900'),('Plex Condensed','IBMPlexSansCondensed-SemiBold.woff2','600'),('Plex Mono','IBMPlexMono-Regular.woff2','400')]
    declarations=[]
    for family,file,weight in fonts:
        data=base64.b64encode((ROOT/'ui-assets'/file).read_bytes()).decode()
        declarations.append("@font-face{font-family:'"+family+"';src:url(data:font/woff2;base64,"+data+") format('woff2');font-weight:"+weight+";font-style:normal;font-display:swap}")
    texture=base64.b64encode((ROOT/'ui-assets'/'paper-handled-v2.png').read_bytes()).decode()
    css='\n'.join(declarations)+'\n'+(ROOT/'paper-theme.css').read_text('utf-8-sig').replace('__PAPER_TEXTURE__','data:image/png;base64,'+texture)
    (ROOT/'briefing.css').write_text(css,'utf-8')
    script=(ROOT/'paper_document.js').read_text('utf-8-sig')
    for name in ('viewer','standalone'):
        template=(ROOT/(name+'.template.html')).read_text('utf-8-sig')
        (ROOT/(name+'.html')).write_text(template.replace('__PAPER_SCRIPT__',script).replace('__UPDATE_SCRIPT__',(ROOT/'update_settings.js').read_text('utf-8')).replace('__OLLAMA_SCRIPT__',(ROOT/'ollama_settings.js').read_text('utf-8')),'utf-8')
if __name__=='__main__':build()
