const $ = id => document.getElementById(id);
const uploaded = [];
let currentProjectId = null;
let API_BASE = (new URLSearchParams(location.search).get('api') || localStorage.getItem('mj-ai-api-base') || '').trim().replace(/\\/$/,'');
let browserWorker = null;
let pendingBrowserRequest = null;

function setStatus(message, bad=false) {
  $('status').textContent = message;
  $('status').style.color = bad ? '#ff9a9a' : '#a1a8b8';
}
function apiUrl(url) {
  if (!API_BASE) return url;
  return API_BASE + (url.startsWith('/') ? url : '/'+url);
}
async function api(url, options={}) {
  const response = await fetch(apiUrl(url), options);
  const data = await response.json().catch(()=>({detail:'Unexpected server response'}));
  if (!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
}
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024*1024) return (bytes/1024).toFixed(1)+' KB';
  return (bytes/1024/1024).toFixed(1)+' MB';
}
function selectedClipIds() {
  return Array.from($('clipSelect').selectedOptions).map(o=>o.value).filter(Boolean);
}
function renderSelectors(preferred={}) {
  const oldSelected = preferred.clips || selectedClipIds();
  const videos = uploaded.filter(x=>x.kind==='video');
  const audios = uploaded.filter(x=>x.kind==='audio');
  const subtitles = uploaded.filter(x=>x.kind==='subtitle');
  $('clipSelect').replaceChildren();
  if (!videos.length) {
    const o=document.createElement('option');o.disabled=true;o.textContent='Upload video files first';$('clipSelect').append(o);
  } else {
    videos.forEach(file=>{const o=document.createElement('option');o.value=file.id;o.textContent=file.name;$('clipSelect').append(o);});
    const matching=oldSelected.filter(id=>videos.some(v=>v.id===id));
    const chosen=matching.length?matching:videos.map(v=>v.id);
    Array.from($('clipSelect').options).forEach(o=>o.selected=chosen.includes(o.value));
  }
  $('audioSelect').replaceChildren();
  const noneAudio=document.createElement('option');noneAudio.value='';noneAudio.textContent='Keep original video audio';$('audioSelect').append(noneAudio);
  audios.forEach(file=>{const o=document.createElement('option');o.value=file.id;o.textContent=file.name;$('audioSelect').append(o);});
  $('audioSelect').value=preferred.audio_id || '';
  $('subtitleSelect').replaceChildren();
  const noSrt=document.createElement('option');noSrt.value='';noSrt.textContent='No subtitles';$('subtitleSelect').append(noSrt);
  subtitles.forEach(file=>{const o=document.createElement('option');o.value=file.id;o.textContent=file.name;$('subtitleSelect').append(o);});
  $('subtitleSelect').value=preferred.subtitles_id || '';
}
function renderMediaList() {
  $('mediaCount').textContent=uploaded.length+' file'+(uploaded.length===1?'':'s');
  $('mediaList').replaceChildren();
  if (!uploaded.length) {
    const p=document.createElement('p');p.className='muted';p.textContent='Your uploaded files will appear here.';$('mediaList').append(p);
    return;
  }
  uploaded.forEach(file=>{
    const row=document.createElement('div');row.className='media-item';
    const main=document.createElement('div');
    const name=document.createElement('div');name.className='filename';name.textContent=file.name;
    const meta=document.createElement('small');meta.textContent=formatBytes(file.size)+(file.metadata?.duration?' · '+Math.round(file.metadata.duration)+' sec':'');
    main.append(name,meta);
    const actions=document.createElement('div');actions.className='media-actions';
    const kind=document.createElement('span');kind.className='kind';kind.textContent=file.kind;
    const remove=document.createElement('button');remove.className='remove-media';remove.textContent='Remove';remove.addEventListener('click',()=>removeMedia(file.id));
    actions.append(kind,remove);row.append(main,actions);$('mediaList').append(row);
  });
}
async function refreshServices() {
  $('engineBadge').textContent='Checking services…';
  try {
    const [health,mj]=await Promise.all([api('/api/health'),api('/api/mj-ai/status')]);
    const parts=[health.ffmpeg_available?'FFmpeg ready':'FFmpeg missing',mj.local.available?'Ollama connected':'Ollama offline',mj.adapter?.configured?'adapter installed':'adapter not installed'];
    $('engineBadge').textContent=parts.join(' · ');
    setStatus('Backend online · Upload limit '+health.max_upload_mb+' MB · '+parts.join(' · '),!health.ffmpeg_available);
  } catch(err) {
    $('engineBadge').textContent='Service check failed';
    setStatus('Backend status check failed: '+err.message,true);
  }
}
async function loadMedia() {
  try {
    const data=await api('/api/media');
    uploaded.splice(0,uploaded.length,...data.files);
    renderMediaList();renderSelectors();
  } catch(err) {
    setStatus('Could not load media library: '+err.message,true);
  }
}
async function removeMedia(id) {
  const file=uploaded.find(x=>x.id===id);
  if (!file) return;
  try {
    await api('/api/media/'+encodeURIComponent(id),{method:'DELETE'});
    const index=uploaded.findIndex(x=>x.id===id);if(index>=0)uploaded.splice(index,1);
    renderMediaList();renderSelectors();
  } catch(err) { setStatus('Could not remove file: '+err.message,true); }
}
$('refreshStatus').addEventListener('click',refreshServices);
if ($('apiBaseUrl')) $('apiBaseUrl').value=API_BASE;
$('saveApiBase')?.addEventListener('click',async()=>{
  const value=$('apiBaseUrl').value.trim().replace(/\/$/,'');
  if(value && !/^https?:\/\//i.test(value)){setStatus('Backend URL must begin with http:// or https://.',true);return;}
  API_BASE=value;
  if(value)localStorage.setItem('mj-ai-api-base',value);else localStorage.removeItem('mj-ai-api-base');
  await refreshServices();await loadMedia();
  try{await refreshProjects();}catch(err){setStatus('Backend connected, but projects could not be loaded: '+err.message,true);}
});
$('clearApiBase')?.addEventListener('click',async()=>{
  API_BASE='';localStorage.removeItem('mj-ai-api-base');if($('apiBaseUrl'))$('apiBaseUrl').value='';
  await refreshServices();await loadMedia();try{await refreshProjects();}catch(err){setStatus('Could not load projects: '+err.message,true);}
});
$('files').addEventListener('change',async event=>{
  const files=Array.from(event.target.files||[]);
  event.target.value='';
  for (const file of files) {
    const row=document.createElement('div');row.className='media-item';
    const name=document.createElement('span');name.textContent='Uploading '+file.name+'…';row.append(name);$('mediaList').prepend(row);
    const form=new FormData();form.append('file',file);
    try {
      const data=await api('/api/upload',{method:'POST',body:form});
      uploaded.unshift(data);renderMediaList();renderSelectors();
      const videoOption=Array.from($('clipSelect').options).find(o=>o.value===data.id);
      if(videoOption) videoOption.selected=true;
      if(data.kind==='audio') $('audioSelect').value=data.id;
      if(data.kind==='subtitle') $('subtitleSelect').value=data.id;
    } catch(err) {name.textContent=file.name+': '+err.message;name.style.color='#ff9a9a';}
  }
});
$('clearMedia').addEventListener('click',async()=>{
  if(!uploaded.length)return;
  if(!confirm('Remove all uploaded media from this server?'))return;
  for(const file of [...uploaded]) await removeMedia(file.id);
});
$('musicVolume').addEventListener('input',()=>{$('volumeLabel').textContent=$('musicVolume').value+'%'});
$('render').addEventListener('click',async()=>{
  const files=selectedClipIds();
  if(!files.length){$('renderStatus').textContent='Upload and select at least one video clip.';return;}
  if($('burnSubtitles').checked&&!$('subtitleSelect').value){$('renderStatus').textContent='Select an SRT file or turn off subtitle burn-in.';return;}
  const btn=$('render');btn.disabled=true;btn.textContent='Rendering…';$('renderStatus').textContent='Preparing clips and rendering. Keep this tab open.';
  try {
    const endValue=$('end').value;
    const payload={files,start:Number($('start').value||0),end:endValue===''?null:Number(endValue),
      aspect:$('aspect').value,resolution:$('resolution').value,audio_id:$('audioSelect').value||null,
      subtitles_id:$('subtitleSelect').value||null,burn_subtitles:$('burnSubtitles').checked,
      music_volume:Number($('musicVolume').value)/100,output_name:$('outputName').value};
    const data=await api('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    $('renderStatus').replaceChildren();
    const msg=document.createElement('span');msg.textContent='Render complete · '+formatBytes(data.size||0)+' · ';
    const link=document.createElement('a');link.href=apiUrl(data.url);link.download=data.filename;link.textContent='Download '+data.filename;
    $('renderStatus').append(msg,link);
  } catch(err) { $('renderStatus').textContent=err.message;$('renderStatus').style.color='#ff9a9a'; }
  finally {btn.disabled=false;btn.textContent='▶ Render MP4';}
});
function modeInstruction(mode) {
  return ({
    script:'Write a practical video script with a strong hook, numbered scenes, durations, narration, visuals, on-screen text, and a closing CTA. Be specific and match the user language.',
    storyboard:'Create a numbered scene-by-scene storyboard with duration, camera framing, character action, visual prompt, dialogue/narration, sound and transition. Preserve character and location continuity.',
    caption:'Write five distinct short-video captions, a strong hook, a concise description and relevant hashtags. Match the user language.'
  })[mode]||'Help create a video. Match the user language.';
}
function askBrowserAI(messages) {
  return new Promise((resolve,reject)=>{
    if(!browserWorker) {
      browserWorker=new Worker('/static/browser-ai-worker.js',{type:'module'});
      browserWorker.onmessage=event=>{
        const data=event.data||{};
        if(data.type==='progress') {$('aiProgress').hidden=false;$('aiProgress').textContent=data.message||'Loading model…';return;}
        if(!pendingBrowserRequest)return;
        const pending=pendingBrowserRequest;pendingBrowserRequest=null;
        if(data.type==='result')resolve(data.text);else reject(new Error(data.message||'Browser AI failed.'));
      };
      browserWorker.onerror=event=>{if(pendingBrowserRequest){pendingBrowserRequest.reject(new Error(event.message||'Browser model worker failed.'));pendingBrowserRequest=null;}};
    }
    if(pendingBrowserRequest){reject(new Error('A browser AI request is already running.'));return;}
    pendingBrowserRequest={resolve,reject};
    browserWorker.postMessage({type:'generate',messages});
  });
}
$('generate').addEventListener('click',async()=>{
  const prompt=$('prompt').value.trim();
  if(!prompt){$('aiResult').hidden=false;$('aiText').value='Describe your video idea first.';return;}
  const btn=$('generate');btn.disabled=true;btn.textContent='Generating…';$('aiResult').hidden=false;$('aiText').value='Working…';$('aiProgress').hidden=true;
  const provider=$('aiProvider').value,mode=$('aiMode').value;
  try {
    let data;
    if(provider==='browser') {
      $('aiProgress').hidden=false;$('aiProgress').textContent='Preparing on-device model. First download may be large; keep this tab open.';
      const text=await askBrowserAI([{role:'system',content:modeInstruction(mode)},{role:'user',content:prompt}]);
      data={text,provider:'browser-local'};
    } else if(provider==='adapter') {
      data=await api('/api/mj-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:'adapter',messages:[{role:'system',content:modeInstruction(mode)},{role:'user',content:prompt}],max_tokens:2048})});
    } else if(provider==='cloud') {
      data=await api('/api/ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,mode})});
    } else {
      data=await api('/api/local-ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,mode,provider})});
    }
    $('aiText').value=data.text+(data.model?'\n\n[Model: '+data.model+']':'');
    $('aiProgress').textContent=provider==='browser'?'Generated on this device.':'Generated with '+(data.provider||provider)+(data.model?' · '+data.model:'')+'.';
  } catch(err) {
    $('aiText').value=err.message;
    $('aiProgress').textContent='AI request failed. Check the selected engine and its setup.';
  } finally {btn.disabled=false;btn.textContent='✦ Generate with AI';}
});
$('copy').addEventListener('click',async()=>{
  try{await navigator.clipboard.writeText($('aiText').value);$('copy').textContent='Copied!';setTimeout(()=>$('copy').textContent='Copy result',1200);}
  catch(err){$('aiText').select();document.execCommand('copy');}
});
$('useScript').addEventListener('click',()=>{$('prompt').value=$('aiText').value;$('prompt').focus();});
function projectPayload() {
  return {files:selectedClipIds(),audio_id:$('audioSelect').value||null,subtitles_id:$('subtitleSelect').value||null,
    burn_subtitles:$('burnSubtitles').checked,aspect:$('aspect').value,resolution:$('resolution').value,
    start:Number($('start').value||0),end:$('end').value===''?null:Number($('end').value),
    music_volume:Number($('musicVolume').value)/100,output_name:$('outputName').value};
}
function applyProject(data) {
  const d=data||{};
  renderSelectors({clips:d.files||[],audio_id:d.audio_id||'',subtitles_id:d.subtitles_id||''});
  ['aspect','resolution','outputName'].forEach(key=>{if(d[key]!==undefined&&$(key))$(key).value=d[key];});
  $('start').value=d.start??0;$('end').value=d.end??'';
  $('musicVolume').value=Math.round((d.music_volume??0.25)*100);$('volumeLabel').textContent=$('musicVolume').value+'%';
  $('burnSubtitles').checked=Boolean(d.burn_subtitles);
}
async function refreshProjects(selectId='') {
  const data=await api('/api/projects');
  $('projectSelect').replaceChildren();
  const empty=document.createElement('option');empty.value='';empty.textContent='Load saved project…';$('projectSelect').append(empty);
  data.projects.forEach(p=>{const o=document.createElement('option');o.value=p.id;o.textContent=p.name;$('projectSelect').append(o);});
  if(selectId)$('projectSelect').value=selectId;
}
$('saveProject').addEventListener('click',async()=>{
  const btn=$('saveProject');btn.disabled=true;
  try {
    const payload={name:$('projectName').value.trim()||'Untitled project',data:projectPayload()};
    const data=currentProjectId
      ?await api('/api/projects/'+currentProjectId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      :await api('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    currentProjectId=data.id;$('projectName').value=data.name;await refreshProjects(data.id);setStatus('Project saved: '+data.name);
  } catch(err){setStatus('Could not save project: '+err.message,true);}
  finally{btn.disabled=false;}
});
$('loadProject').addEventListener('click',async()=>{
  const id=$('projectSelect').value;if(!id){setStatus('Choose a saved project first.',true);return;}
  try {
    const project=await api('/api/projects/'+id);currentProjectId=id;$('projectName').value=project.name;
    applyProject(project.data);setStatus('Loaded project: '+project.name);
  } catch(err){setStatus('Could not load project: '+err.message,true);}
});
$('deleteProject').addEventListener('click',async()=>{
  const id=$('projectSelect').value||currentProjectId;if(!id){setStatus('Choose a project to delete.',true);return;}
  if(!confirm('Delete this saved project?'))return;
  try{await api('/api/projects/'+id,{method:'DELETE'});if(currentProjectId===id)currentProjectId=null;await refreshProjects();setStatus('Project deleted.');}
  catch(err){setStatus('Could not delete project: '+err.message,true);}
});
$('projectSelect').addEventListener('change',()=>{currentProjectId=$('projectSelect').value||null;});
(async()=>{await refreshServices();await loadMedia();try{await refreshProjects();}catch(err){setStatus('Projects could not be loaded: '+err.message,true);}})();
