(function(){
 'use strict';
 const el=id=>document.getElementById(id);let visible=false,timer=null;
 function tab(update){
  visible=update;el('settings-general-panel').hidden=update;el('settings-update-panel').hidden=!update;
  el('settings-tab-general').setAttribute('aria-selected',String(!update));el('settings-tab-update').setAttribute('aria-selected',String(update));
  el('save-settings').hidden=update;el('retry-button').hidden=update;
  if(update)refresh();
 }
 async function action(path){
  try{const r=await fetch(path,{method:'POST'});const s=await r.json();if(!r.ok)throw Error(s.detail||'요청 실패');await refresh()}
  catch(e){el('update-message').textContent=e.message}
 }
 async function refresh(){
  clearTimeout(timer);
  try{
   const r=await fetch('/api/updates');if(!r.ok)throw Error('업데이트 상태를 불러오지 못했습니다.');const s=await r.json();
   const old=el('update-current').textContent;
   el('update-current').textContent=s.current;el('update-latest').textContent=s.latest||'—';
   el('update-repository').textContent=s.repository;el('update-message').textContent=s.message;
   el('update-notes').textContent=s.notes||'';
   el('update-result').textContent=s.last_install?.message||'';
   const busy=['checking','downloading','installing'].includes(s.phase);
   el('update-check').disabled=busy;el('update-install').disabled=busy||!s.available;
   el('update-cancel').hidden=s.phase!=='downloading';
   el('update-progress').hidden=s.phase!=='downloading';el('update-progress').max=s.total||1;el('update-progress').value=s.downloaded||0;
   el('update-download').textContent=s.phase==='downloading'?`${Math.round(s.downloaded/1048576)} / ${Math.round(s.total/1048576)} MB`:'';
   el('settings-button').textContent=s.available?'설정 · 새 버전':'설정';
   if(old&&old!==s.current)location.reload();
   timer=setTimeout(refresh,busy?1000:30000);
  }catch(e){
   if(visible)el('update-message').textContent='설치 중에는 잠시 연결이 끊깁니다. 완료 후 뷰어가 다시 열립니다. 연결을 기다리고 있습니다.';
   timer=setTimeout(refresh,3000);
  }
 }
 el('settings-tab-general').onclick=()=>tab(false);el('settings-tab-update').onclick=()=>tab(true);
 el('update-check').onclick=()=>action('/api/updates/check');el('update-install').onclick=()=>action('/api/updates/install');el('update-cancel').onclick=()=>action('/api/updates/cancel');
 el('settings-dialog').addEventListener('close',()=>{visible=false});
 window.updateSettings={general:()=>tab(false)};refresh();
})();
