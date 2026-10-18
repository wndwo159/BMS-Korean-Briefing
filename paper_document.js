/* Presentation only: paginates existing sanitized briefing HTML without changing source data. */
(function(){
'use strict';
const E=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e};
const readMode=()=>{try{return localStorage.getItem('bms-view-mode')||''}catch{return ''}};
const saveMode=mode=>{try{localStorage.setItem('bms-view-mode',mode)}catch{}};
const tabNames={'Mission Overview':'BRIEFING','Situation':'SITREP','Pilot Roster':'CREW','Package Elements':'PACKAGE','Threat Analysis':'THREATS','Steerpoints':'FLT PLAN','Comm Ladder':'COMM','Iff':'IFF','Link 16':'LINK 16','Ordnance':'LOADOUT','Weather':'WEATHER','Support':'SUPPORT','Rules of Engagement':'ROE','Emergency Procedures':'EMERG'};
class Packet{
 constructor(options={}){
  this.host=document.getElementById('briefing');this.tabs=document.getElementById('sections');this.pages=[];this.current=0;this.mode=readMode();this.meta={};this.html='';this.sections=[];this.ready=false;
  this.options=options;this.host.className=this.mode;
  document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>this.setMode(b.dataset.mode)));
  document.getElementById('previous-page')?.addEventListener('click',()=>this.show(this.current-1));
  document.getElementById('next-page')?.addEventListener('click',()=>this.show(this.current+1));
  document.getElementById('preview-button')?.addEventListener('click',()=>{const on=document.body.classList.toggle('print-preview');document.getElementById('preview-button').textContent=on?'화면 보기':'인쇄 미리보기'});
  document.getElementById('print-button')?.addEventListener('click',()=>window.print());
  document.getElementById('search')?.addEventListener('input',()=>this.search());
  document.getElementById('zoom-in')?.addEventListener('click',()=>this.zoom(1));
  document.getElementById('zoom-out')?.addEventListener('click',()=>this.zoom(-1));
  this.zoomValue=100;
  let scrolling=false;window.addEventListener('scroll',()=>{if(scrolling)return;scrolling=true;requestAnimationFrame(()=>{scrolling=false;this.followScroll()})},{passive:true});
  let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(()=>{if(this.html)this.paginate()},180)});
  document.fonts.ready.then(()=>{this.ready=true;if(this.html)this.paginate()});
  this.updateModeButtons();
 }
 updateModeButtons(){document.querySelectorAll('[data-mode]').forEach(b=>{b.classList.toggle('active',b.dataset.mode===this.mode);b.setAttribute('aria-pressed',String(b.dataset.mode===this.mode))})}
 setMode(mode){this.mode=mode;this.host.className=mode;saveMode(mode);this.updateModeButtons();if(this.html)this.paginate()}
 zoom(delta){this.zoomValue=Math.min(140,Math.max(80,this.zoomValue+delta*10));document.documentElement.style.setProperty('--paper-width',`min(${940*this.zoomValue/100}px,calc(100vw - 170px))`);document.getElementById('zoom-value').textContent=this.zoomValue+'%';this.paginate()}
 deriveMeta(source){
  const found={};
  const flight=source.textContent.match(/\b([A-Za-z][A-Za-z0-9]+)\s*\(([A-Z]{2,})\)/);if(flight){found.callsign=flight[1];found.mission=flight[2]}
  for(const row of source.querySelectorAll('tr')){const cells=[...row.cells];if(cells.length<2)continue;const label=(cells[0].querySelector('.en')||cells[0]).textContent;const value=(cells[1].querySelector('.en')||cells[1]).textContent;if(/Package #/i.test(label))found.package=value.match(/^\s*(\S+)/)?.[1];if(/Time on Target/i.test(label))found.tot=value.trim()}
  return found;
 }
 enhance(source){
  for(const el of source.querySelectorAll('.kr')){
   if(el.querySelector('.data-value'))continue;
   const text=el.textContent;el.replaceChildren();
   const re=/\b(?:[A-Za-z][A-Za-z-]*\d[\w./-]*|\d+(?:[.:,/\-]\d+)*(?:[A-Za-z]+)?)(?:\s+(?:MHz|NM|FT|ft|nm))?\b/g;
   let cursor=0;for(const m of text.matchAll(re)){el.append(document.createTextNode(text.slice(cursor,m.index)));el.append(E('span','data-value',m[0]));cursor=m.index+m[0].length}el.append(document.createTextNode(text.slice(cursor)));
   const t=text.match(/\b(\d{2}):(\d{2}):(\d{2})[zZ]\b/);if(t){const hours=Number(t[1])+9;const kst='KST '+String(hours%24).padStart(2,'0')+':'+t[2]+':'+t[3]+(hours>=24?' (+1일)':'');el.append(E('small','time-note',kst));el.title=kst}
  }
 }
 hasContent(section){
  const body=section.querySelector('.section-body');if(!body)return false;
  const meaningful=text=>!!text.trim()&&!/^(?:[-–—.\s]+|n\/?a|none|no data|없음|데이터 없음)$/i.test(text.trim());
  const originalText=node=>{const en=node.querySelectorAll('.en');return en.length?[...en].map(n=>n.textContent).join(' '):node.textContent};
  for(const row of body.querySelectorAll('tr')){
   const cells=[...row.cells];if(cells.every(c=>c.tagName==='TH'))continue;
   if(cells.some(c=>{const t=originalText(c).trim();return meaningful(t)&&!t.endsWith(':')}))return true;
  }
  for(const p of body.querySelectorAll('p,li'))if(meaningful(originalText(p)))return true;
  if(!body.querySelector('table,p,li'))return meaningful(originalText(body));
  return false;
 }
 cleanPackage(section){
  const name=section.querySelector('.source-heading')?.textContent||'';
  if(!/package elements/i.test(name))return;
  // Only presentation clones are edited; the original source and stored English stay intact.
  for(const table of section.querySelectorAll('table')){
   const head=[...table.rows].find(row=>[...row.cells].some(c=>/Flt\s*#/i.test(c.querySelector('.en')?.textContent||c.textContent)));
   if(!head)continue;
   const column=[...head.cells].findIndex(c=>/Flt\s*#/i.test(c.querySelector('.en')?.textContent||c.textContent));
   for(const row of table.rows){const cell=row.cells[column];if(!cell)continue;const original=(cell.querySelector('.en')||cell).textContent.trim();const marker=original.match(/^(\d+)\s*\(\s*x\s*\)$/i);if(marker)for(const value of cell.querySelectorAll('.kr,.en'))value.textContent=marker[1]}
  }
  for(const p of section.querySelectorAll('.section-body>p'))if(/^x\s*=\s*Primary Flight$/i.test((p.querySelector('.en')||p).textContent.trim()))p.remove();
 }
 render(html,meta={},sections=[]){this.html=html;this.meta=meta;this.sections=sections;this.paginate()}
 sourceName(section){return (this.sectionInfo.get(section.id)?.source||section.querySelector('.source-heading')?.textContent||'').trim().toLowerCase()}
 groupOf(section){
  const name=this.sourceName(section);
  if(/briefing record|mission overview|^situation$/.test(name))return 'briefing';
  if(/pilot roster|package elements|threat analysis/.test(name))return 'package';
  if(/steerpoints|flight plan/.test(name))return 'flight';
  if(/comm ladder/.test(name))return 'comms';
  if(/weather|^support$|rules of engagement/.test(name))return 'operations';
  if(/ordnance/.test(name))return 'loadout';
  if(/emergency/.test(name))return 'emergency';
  return 'other-'+section.id;
 }
 header(first){
  const header=E('header','page-header'+(first?'':' running-header'));
  const running=E('div','document-running');running.append(E('span','','FALCON BMS / AIR OPERATIONS'),E('span','','FLIGHT BRIEFING PACKAGE'));header.append(running);
  const heading=E('div','document-heading');const title=E('h1','','MISSION BRIEFING');title.append(E('span','korean-title','항공작전 임무 브리핑'));const stamp=E('div','document-copy-stamp');stamp.append(E('div','','PREFLIGHT COPY'),E('div','','KOREAN EDITION'));heading.append(title,stamp);header.append(heading);
  const fields=E('div','document-identifiers');for(const [key,label]of [['callsign','FLIGHT'],['mission','ROLE'],['package','PKG'],['tot','TOT']]){const value=this.renderMeta[key];if(!value||value==='—')continue;const item=E('span');item.append(E('span','field-label',label),E('strong','',value));fields.append(item)}if(fields.childElementCount)header.append(fields);return header;
 }
 newPage(){
  const page=E('section','paper-page current');page.setAttribute('aria-label','브리핑 문서 '+(this.pages.length+1)+'페이지');
  page.dataset.packetGroup=this.activeGroup||'briefing';
  page.append(this.header(this.pages.length===0));const content=E('div','page-content');page.append(content);
  const footer=E('footer','page-footer');footer.append(E('span','','FALCON BMS · SOURCE DATA PRESERVED'),E('span','page-number',''));page.append(footer);this.host.append(page);this.pages.push(page);return {page,content};
 }
 fits(content){return content.scrollHeight<=content.clientHeight+2}
 addSection(source,location,continued=false){
  const section=E('section','briefing-section');section.dataset.sourceId=source.id;
  const english=source.querySelector('.source-heading')?.textContent.trim()||'';
  const known=this.sectionInfo.get(source.id)||{};const key=known.source||english;
  if(/briefing record/i.test(key))section.classList.add('record-section');
  if(/mission overview/i.test(key))section.classList.add('mission-summary');
  if(/threat/i.test(key))section.classList.add('threat-section');
  if(/steerpoints|flight plan/i.test(key)){section.classList.add('flight-plan');location.page.classList.add('flight-plan-page')}
  if(!this.host.querySelector('#'+CSS.escape(source.id)))section.id=source.id;
  const title=E('h2');const number=this.sectionOrder.get(source.id);if(number)title.append(E('span','section-number',String(number).padStart(2,'0')+'.'));
  const titleKo=known.title||[...(source.querySelector('h2')?.childNodes||[])].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join('').trim()||english||'브리핑';
  title.append(E('span','heading-ko',titleKo));if(english)title.append(E('small','source-heading',english));if(continued)title.append(E('small','continued-label','계속 / CONT.'));
  const body=E('div','section-body');section.append(title,body);location.content.append(section);return {section,body};
 }
 paginate(){
  if(!this.html)return;
  const active=this.current;this.host.replaceChildren();this.pages=[];
  const source=E('div');source.innerHTML=this.html;
  this.sectionInfo=new Map(this.sections.map(s=>[s.id,s]));
  // Historical standalone exports may include an article wrapper. Use the same real sections.
  const allSections=[...source.querySelectorAll('.briefing-section')];
  const sections=allSections.filter(s=>this.hasContent(s)&&! /^(iff|link\s*16)$/.test(this.sourceName(s)));
  const groupOrder=['briefing','package','flight','comms','operations','loadout','emergency'];
  const rank=s=>{const index=groupOrder.indexOf(this.groupOf(s));return index<0?groupOrder.length:index};
  sections.sort((a,b)=>rank(a)-rank(b));
  for(const s of sections)this.cleanPackage(s);
  if(allSections.length&&!sections.length){this.tabs?.replaceChildren();this.host.append(E('p','empty-document','표시할 브리핑 데이터가 없습니다.'));return}
  if(!sections.length){const s=E('section','briefing-section');s.id='section-document';s.append(E('h2','','브리핑'));const body=E('div','section-body');while(source.firstChild)body.append(source.firstChild);s.append(body);source.append(s);sections.push(s)}
  this.renderMeta={...this.deriveMeta(source),...this.meta};this.enhance(source);
  this.sectionInfo=new Map(this.sections.map(s=>[s.id,s]));this.sectionOrder=new Map();let count=0;
  for(const s of sections){const info=this.sectionInfo.get(s.id)||{};const name=info.source||s.querySelector('.source-heading')?.textContent||'';if(!/briefing record/i.test(name))this.sectionOrder.set(s.id,++count)}
  this.activeGroup=sections.length?this.groupOf(sections[0]):'briefing';
  let location=this.newPage();let previousGroup=this.activeGroup;
  for(const sourceSection of sections){
   const group=this.groupOf(sourceSection);this.activeGroup=group;
   if(group!==previousGroup&&location.content.children.length)location=this.newPage();
   previousGroup=group;
   const blocks=[...(sourceSection.querySelector('.section-body')||sourceSection).children].filter(n=>n.tagName!=='H2');
   let chunk=this.addSection(sourceSection,location);
   // Keep a short section together whenever it fits on a fresh sheet.
   for(const block of blocks)chunk.body.append(block.cloneNode(true));
   if(this.fits(location.content))continue;
   const sectionHeight=chunk.section.getBoundingClientRect().height;
   chunk.section.remove();
   if(sectionHeight<location.content.clientHeight*.62&&location.content.children.length){location=this.newPage();chunk=this.addSection(sourceSection,location);for(const block of blocks)chunk.body.append(block.cloneNode(true));if(this.fits(location.content))continue;chunk.section.remove()}
   chunk=this.addSection(sourceSection,location);
   for(const block of blocks){
    const table=block.matches('.table-scroll')?block.querySelector('table'):null;
    if(!table){
     const clone=block.cloneNode(true);chunk.body.append(clone);
     if(!this.fits(location.content)){
      clone.remove();if(!chunk.body.children.length)chunk.section.remove();
      if(location.content.children.length){location=this.newPage();chunk=this.addSection(sourceSection,location,true)}
      else if(!chunk.section.isConnected)chunk=this.addSection(sourceSection,location);
      chunk.body.append(clone);if(!this.fits(location.content))location.page.classList.add('long-page');
     }
     continue;
    }
    const rows=[...table.rows];let shell,tbody;
    const createTable=(repeat)=>{shell=block.cloneNode(false);const t=table.cloneNode(false);tbody=E('tbody');t.append(tbody);shell.append(t);chunk.body.append(shell);if(rows[0]?.cells.length>=8)t.classList.add('dense-table');if(repeat&&rows[0]&&[...rows[0].cells].every(c=>c.tagName==='TH')){const head=rows[0].cloneNode(true);head.dataset.repeated='true';tbody.append(head)}};
    createTable(false);
    for(const row of rows){
     if([...row.cells].every(c=>c.tagName==='TH')&&tbody.querySelector('[data-repeated]'))continue;
     const clone=row.cloneNode(true);tbody.append(clone);
     if(this.fits(location.content))continue;
     clone.remove();const substantive=[...tbody.rows].filter(r=>!r.dataset.repeated&&![...r.cells].every(c=>c.tagName==='TH'));
     if(!substantive.length)shell.remove();
     if(!chunk.body.children.length)chunk.section.remove();
     if(location.content.children.length){location=this.newPage();chunk=this.addSection(sourceSection,location,true)}
     else if(!chunk.section.isConnected)chunk=this.addSection(sourceSection,location);
     createTable(true);tbody.append(clone);
     if(!this.fits(location.content))location.page.classList.add('long-page');
    }
   }
  }
  this.pages.forEach((page,index)=>{page.querySelector('.page-number').textContent='SHEET '+String(index+1).padStart(2,'0')+' / '+String(this.pages.length).padStart(2,'0')});
  this.navigation(sections);this.show(Math.min(active,this.pages.length-1),null,false);
 }
 navigation(sections){
  if(!this.tabs)return;this.tabs.replaceChildren();
  for(const section of sections){
   const number=this.sectionOrder.get(section.id);if(!number)continue;
   const info=this.sectionInfo.get(section.id)||{};const original=info.source||section.querySelector('.source-heading')?.textContent||'';
   const key=Object.keys(tabNames).find(k=>k.toLowerCase()===original.toLowerCase());
   const label=key?tabNames[key]:(info.title||original||'SECTION').slice(0,10);
   const a=E('a','section-link');a.href='#'+encodeURIComponent(section.id);a.dataset.section=section.id;a.title=info.title||original;
   if(/threat|emergency/i.test(original))a.dataset.tone='warning';a.append(E('span','number',String(number).padStart(2,'0')),document.createTextNode(label));
   a.addEventListener('click',event=>{event.preventDefault();const index=this.pages.findIndex(p=>p.querySelector('[data-source-id="'+CSS.escape(section.id)+'"]'));if(index>=0){this.show(index,section.id);history.replaceState(null,'','#'+encodeURIComponent(section.id))}});this.tabs.append(a);
  }
 }
 show(index,selected,scroll=true){
  if(!this.pages.length)return;this.current=Math.max(0,Math.min(index,this.pages.length-1));this.pages.forEach((p,i)=>p.classList.toggle('current',i===this.current));
  const label=document.getElementById('page-indicator');if(label)label.textContent=String(this.current+1).padStart(2,'0')+' / '+String(this.pages.length).padStart(2,'0');
  const prev=document.getElementById('previous-page'),next=document.getElementById('next-page');if(prev)prev.disabled=this.current===0;if(next)next.disabled=this.current===this.pages.length-1;
  const first=selected||this.pages[this.current].querySelector('.briefing-section:not(.record-section)')?.dataset.sourceId;
  for(const tab of this.tabs?.children||[]){tab.classList.toggle('active',tab.dataset.section===first);tab.setAttribute('aria-current',tab.dataset.section===first?'page':'false')}
  if(scroll){const target=selected?this.host.querySelector('#'+CSS.escape(selected)):this.pages[this.current];target?.scrollIntoView({behavior:'smooth',block:'start'})}
 }
 followScroll(){
  if(!this.pages.length)return;
  const line=Math.min(180,window.innerHeight*.3);let index=0;
  for(let i=0;i<this.pages.length;i++){if(this.pages[i].getBoundingClientRect().top<=line)index=i;else break}
  const sections=[...this.pages[index].querySelectorAll('.briefing-section:not(.record-section)')];let selected=sections[0]?.dataset.sourceId;
  for(const s of sections)if(s.getBoundingClientRect().top<=line)selected=s.dataset.sourceId;
  this.show(index,selected,false);
 }
 search(){const query=(document.getElementById('search')?.value||'').trim().toLowerCase();let first=-1;for(const [i,page]of this.pages.entries())for(const section of page.querySelectorAll('.briefing-section')){const match=!!query&&section.textContent.toLowerCase().includes(query);section.classList.toggle('search-result',match);if(match&&first<0)first=i}if(first>=0)this.show(first)}
}
window.BriefingPaper={Packet};
})();
