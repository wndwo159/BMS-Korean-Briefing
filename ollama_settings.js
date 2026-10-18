/* Guided local model setup. Downloads only start after an explicit button click. */
const ollamaSettings=(()=>{
 const el=id=>document.getElementById(id);let timer=null,lastState='',online=false;
 const request=async(path,body)=>{const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok){let error=await r.json();throw Error(error.detail||'요청 실패')}return r.json()};
 function update(){const enabled=el('setting-provider').value==='ollama';el('ollama-guide').hidden=!enabled;for(const k of ['model','ollama_url'])el('setting-'+k).closest('label').hidden=!enabled;for(const k of ['openai_model'])el('setting-'+k).closest('label').hidden=el('setting-provider').value!=='openai'}
 async function refresh(preferred){
  const select=el('setting-model');preferred=preferred||select.value;
  el('ollama-status').textContent='Ollama와 설치된 모델 확인 중…';
  try{
   const data=await request('/api/models?url='+encodeURIComponent(el('setting-ollama_url').value));online=data.reachable;
   select.replaceChildren(new Option(data.models.length?'사용할 모델을 선택하세요':'설치된 모델이 없습니다',''));
   for(const model of data.models){const size=model.size?' · '+(model.size/1e9).toFixed(1)+' GB':'';select.add(new Option(model.name+size,model.name))}
   if([...select.options].some(o=>o.value===preferred))select.value=preferred;
   select.disabled=!online||!data.models.length;
   el('ollama-status').textContent=online?`Ollama 연결됨 · 설치된 모델 ${data.models.length}개`:data.installed?'Ollama는 설치되어 있지만 실행되지 않았습니다.':'Ollama가 실행되지 않았습니다. 미설치 상태라면 아래 공식 설치 안내를 따르세요.';
   el('ollama-start').disabled=online||!data.installed;
   el('ollama-pull').disabled=!online;
   el('ollama-catalog').replaceChildren();for(const model of data.catalog){const option=new Option(model.title+' · '+model.size,model.name);option.dataset.description=model.description;el('ollama-catalog').add(option)}
   el('ollama-catalog').onchange=()=>el('ollama-model-note').textContent=el('ollama-catalog').selectedOptions[0]?.dataset.description||'';el('ollama-catalog').onchange();
   draw(data.download);
  }catch(error){online=false;select.disabled=true;el('ollama-pull').disabled=true;el('ollama-status').textContent=error.message}
 }
 function draw(job){
  const active=['downloading','cancelling'].includes(job.state);
  el('ollama-pull').disabled=!online||active;el('ollama-cancel').hidden=!active;el('ollama-cancel').disabled=job.state==='cancelling';
  el('ollama-download-progress').hidden=job.state==='idle';el('ollama-download-progress').value=job.percent||0;
  const bytes=job.total?` · 현재 파일 ${job.percent}% (${(job.completed/1e9).toFixed(2)} / ${(job.total/1e9).toFixed(2)} GB)`:'';
  el('ollama-download-status').textContent=job.state==='idle'?'':`${job.model} · ${job.status}${active?bytes:''}${job.error?' · '+job.error:''}`;
 }
 async function tick(){
  if(!el('settings-dialog').open)return;
  try{const job=await request('/api/ollama/download');draw(job);if(job.state==='complete'&&lastState!=='complete'){lastState=job.state;await refresh(job.model)}else lastState=job.state}catch{}
  timer=setTimeout(tick,1200);
 }
 async function show(config){
  clearTimeout(timer);lastState='';el('setting-ollama_url').closest('label').after(el('ollama-guide'));update();
  el('setting-provider').onchange=()=>{update();if(el('setting-provider').value==='ollama')refresh()};
  el('ollama-refresh').onclick=()=>refresh();
  el('ollama-start').onclick=async()=>{try{await request('/api/ollama/start',{});el('ollama-status').textContent='Ollama 실행 요청을 보냈습니다. 잠시 후 다시 확인을 누르세요.'}catch(error){el('ollama-status').textContent=error.message}};
  el('ollama-pull').onclick=async()=>{try{const job=await request('/api/ollama/pull',{model:el('ollama-catalog').value,url:el('setting-ollama_url').value});lastState='downloading';draw(job)}catch(error){el('ollama-download-status').textContent=error.message}};
  el('ollama-cancel').onclick=async()=>{try{draw(await request('/api/ollama/cancel',{}))}catch(error){el('ollama-download-status').textContent=error.message}};
  if(config.provider==='ollama')await refresh(config.model);tick();
 }
 return {show};
})();
