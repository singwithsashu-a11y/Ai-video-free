const $ = id => document.getElementById(id);
const uploaded = [];
let currentProjectId = null;
let API_BASE = (new URLSearchParams(location.search).get('api') || localStorage.getItem('mj-ai-api-base') || '').trim();
API_BASE = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
let browserWorker = null;
let pendingBrowserRequest = null;
let pendingChatImage = null;

document.querySelectorAll('[data-view-target]').forEach(button=>button.addEventListener('click',()=>switchView(button.dataset.viewTarget)));
function switchView(view){document.querySelectorAll('[data-view]').forEach(s=>s.classList.toggle('active',s.dataset.view===view));document.querySelectorAll('[data-view-target]').forEach(b=>b.classList.toggle('active',b.dataset.viewTarget===view));if(view==='edit')loadMedia();window.scrollTo({top:0,behavior:'smooth'});}
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
    const parts=[health.ffmpeg_available?'FFmpeg ready':'FFmpeg missing',mj.openai_compatible_configured?'Cloud AI configured':'Cloud AI not configured',mj.local.available?'Ollama connected':'Ollama offline',mj.adapter?.configured?'adapter installed ('+mj.adapter.base_model+')':'adapter not installed'];
    $('engineBadge').textContent=parts.join(' · ');
    setStatus('Backend online · Upload limit '+health.max_upload_mb+' MB · '+parts.join(' · '),!health.ffmpeg_available);
  } catch(err) {
    $('engineBadge').textContent='Backend not connected';
    setStatus('Static website is open, but its FastAPI backend is not connected. Browser AI/offline templates can still work; uploads, saved server projects and MP4 rendering need a backend URL. Open “Connect to your backend” to configure it.',true);
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
  const rawValue=$('apiBaseUrl').value.trim();
  const value=rawValue.endsWith('/') ? rawValue.slice(0, -1) : rawValue;
  if(value && !(value.startsWith('https://') || value.startsWith('http://'))){setStatus('Backend URL must begin with http:// or https://.',true);return;}
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
const CHAT_KEY='mj-ai-chat-memory-v1';
const LEARNING_KEY='mj-ai-approved-examples-v1';
const CHAT_SYSTEM='You are MJ AI Studio, a capable multilingual creative copilot. Reply in the same language and script as the user, including natural Hinglish when appropriate. Read the recent conversation and answer the latest request directly. Be concrete, structured, original and concise unless asked for detail. For video requests include a strong hook, duration, scene-by-scene visuals, camera/action, narration/dialogue, on-screen text, sound and transitions. For image questions describe visible details and do not invent facts. Ask at most one focused clarification only when essential. Never claim you rendered or generated media, used a tool, or permanently learned unless it actually happened. If a feature is unavailable, say so and offer the nearest working workflow.';
let chatHistory=loadJson(CHAT_KEY,[]);
let approvedExamples=loadJson(LEARNING_KEY,[]);
function loadJson(key,fallback){try{const value=JSON.parse(localStorage.getItem(key)||'null');return Array.isArray(value)?value:fallback;}catch{return fallback;}}
function saveChat(){chatHistory=chatHistory.slice(-30);try{localStorage.setItem(CHAT_KEY,JSON.stringify(chatHistory.map(({imageDataUrl,...m})=>m)));}catch{ $('chatStatus').textContent='Browser storage is full. Export useful examples, then clear old history.';}}
function offlineGenerate(prompt,mode){
  const idea=prompt.trim();
  if(mode==='caption')return 'HOOK: '+idea.slice(0,140)+'\n\nCAPTION 1: Ye kahani aapko sochne par majboor karegi — end tak dekho.\nCAPTION 2: Ek chhota sa idea, ek badi baat. Aapki kya rai hai?\nCAPTION 3: Is moment ko miss mat karna.\nCAPTION 4: Sach, emotion aur ek powerful message.\nCAPTION 5: Apne dost ke saath share karo.\n\n#Shorts #Reels #Hindi #Hinglish #Video';
  if(mode==='storyboard')return 'OFFLINE STORYBOARD TEMPLATE\nIDEA: '+idea+'\n\nSCENE 1 (0–3s) — HOOK: Show the most surprising image.\nSCENE 2 (3–8s) — CONTEXT: Establish place, person, or problem.\nSCENE 3 (8–15s) — DEVELOPMENT: Show two details that explain the idea.\nSCENE 4 (15–23s) — PAYOFF: Reveal the key moment.\nSCENE 5 (23–30s) — END: Resolve the idea and add a call to action.\n\nThis is a reusable offline template, not model-generated content.';
  return 'OFFLINE SCRIPT TEMPLATE\nIDEA: '+idea+'\n\nHOOK (0–3s): Start with a surprising question related to the idea.\nSCENE 1 (3–8s): Establish the situation with one clear visual.\nNARRATION: Explain why the topic matters.\nSCENE 2 (8–18s): Show the main conflict or emotional moment.\nSCENE 3 (18–27s): Deliver the reveal or emotional payoff.\nENDING (27–30s): Finish with a memorable line and a simple question.\n\nThis is a template, not a language-model answer. Use Browser AI or a connected backend for more customized generation.';
}
function renderChat(){
  const box=$('chatMessages');box.replaceChildren();
  if(!chatHistory.length){const welcome=document.createElement('div');welcome.className='welcome-card';welcome.innerHTML='<span class="welcome-icon">✦</span><h3>Hey! Let\'s make something great.</h3><p>Ask me anything, brainstorm a video, or attach a photo to discuss it.</p><div class="suggestions"><button class="suggestion" data-prompt="Create a viral 30-second Hinglish documentary Short with a strong hook.">🎬 Viral Short idea</button><button class="suggestion" data-prompt="Help me make a cinematic sad love music video, scene by scene.">🎵 Music video</button><button class="suggestion" data-prompt="Give me 5 original YouTube video ideas with strong hooks.">💡 Video ideas</button></div>';box.append(welcome);welcome.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',()=>{$('chatInput').value=b.dataset.prompt;$('chatInput').focus();}));return;}
  chatHistory.forEach((message,index)=>{
    const item=document.createElement('article');item.className='chat-message '+(message.role==='user'?'chat-user':'chat-assistant');
    const role=document.createElement('strong');role.textContent=message.role==='user'?'You':'MJ AI';
    const body=document.createElement('p');body.textContent=message.content;
    item.append(role,body);
    if(message.imageDataUrl){const img=document.createElement('img');img.src=message.imageDataUrl;img.alt='Image attached to this message';item.append(img);}
    if(message.role==='assistant'&&message.replyTo){
      const actions=document.createElement('div');actions.className='button-row';
      const feedback=document.createElement('button');feedback.className='secondary feedback-button';feedback.textContent=message.approved?'✓ Saved for learning':'👍 Helpful · save example';feedback.disabled=Boolean(message.approved);feedback.addEventListener('click',()=>approveExample(index));actions.append(feedback);
      const use=document.createElement('button');use.className='secondary feedback-button';use.textContent='↗ Use for video plan';use.addEventListener('click',()=>{$('prompt').value=message.content+'\\n\\nCreate a practical video plan from this answer.';$('aiMode').value='storyboard';switchView('create');});actions.append(use);item.append(actions);
    }
    box.append(item);
  });
  box.scrollTop=box.scrollHeight;
}
function approveExample(index){
  const answer=chatHistory[index];if(!answer||answer.role!=='assistant'||!answer.replyTo)return;
  const userMessage=chatHistory.findLast?chatHistory.slice(0,index).reverse().find(m=>m.role==='user'): [...chatHistory.slice(0,index)].reverse().find(m=>m.role==='user');
  if(!userMessage)return;
  answer.approved=true;
  approvedExamples.push({messages:[{role:'user',content:userMessage.content},{role:'assistant',content:answer.content}]});
  approvedExamples=approvedExamples.slice(-1000);
  try{localStorage.setItem(LEARNING_KEY,JSON.stringify(approvedExamples));}catch{}
  saveChat();renderChat();$('chatStatus').textContent='Answer approved. '+approvedExamples.length+' learning example(s) saved on this device; export them when ready.';
}
async function sendChat(){
  const input=$('chatInput'),prompt=input.value.trim();if(!prompt&&!pendingChatImage)return;
  const btn=$('sendChat'),provider=$('chatProvider').value;
  if(pendingChatImage&&(provider==='browser'||provider==='adapter'||provider==='offline')){$('chatStatus').textContent=provider==='offline'?'Offline templates cannot understand photos. Choose Cloud AI or an Ollama vision model.':'This engine cannot understand images. Choose Cloud AI with a vision-capable model or Ollama with a vision model.';return;}
  const imageDataUrl=pendingChatImage;input.value='';pendingChatImage=null;$('chatImagePreview').hidden=true;chatHistory.push({role:'user',content:prompt||'Please analyze this attached image.',imageDataUrl});saveChat();renderChat();
  btn.disabled=true;btn.textContent='Thinking…';$('chatStatus').textContent='MJ AI is preparing a reply…';
  try{
    let answer='',model='';
    if(['cloud','ollama','adapter'].includes(provider)&&!API_BASE) throw new Error('Backend URL is not connected. Open ⚙ Backend connection and enter your deployed FastAPI/Render URL. GitHub Pages alone cannot run the server model.');
    const context=chatHistory.slice(-12).map(m=>({role:m.role,content:m.content,...(m.imageDataUrl?{image_data_url:m.imageDataUrl}:{})}));
    if(provider==='offline'){
      answer='I can keep context from this browser, but Offline Template is not a real learning language model. You said: “'+prompt+'”\n\n'+offlineGenerate(prompt,'script');
    }else if(provider==='browser'){
      const result=await askBrowserAI([{role:'system',content:CHAT_SYSTEM},...context]);
      answer=result;
    }else if(provider==='adapter'||provider==='ollama'||provider==='cloud'){
      const providerName=provider==='adapter'?'adapter':provider==='ollama'?'ollama':'openai-compatible';
      const data=await api('/api/mj-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:providerName,messages:[{role:'system',content:CHAT_SYSTEM},...context],max_tokens:768,temperature:0.55})});
      answer=data.text;model=data.model||'';
    }
    if(!answer.trim())throw new Error('AI returned an empty response.');
    chatHistory.push({role:'assistant',content:answer,replyTo:prompt,model,approved:false});saveChat();renderChat();
    $('chatStatus').textContent='Reply ready. Recent context is saved in this browser; use “Helpful · save example” to approve training data.';
  }catch(err){
    $('chatStatus').textContent='Request failed: '+err.message+'. For photos, choose a vision-capable Cloud AI or Ollama vision model; check backend and provider settings.';
  }finally{btn.disabled=false;btn.textContent='Send message';}
}
$('sendChat')?.addEventListener('click',sendChat);
$('chatImageInput')?.addEventListener('change',async event=>{const file=event.target.files?.[0];event.target.value='';if(!file)return;if(!file.type.startsWith('image/')){$('chatStatus').textContent='Please choose an image file.';return;}if(file.size>15*1024*1024){$('chatStatus').textContent='Image is too large. Choose an image under 15 MB.';return;}try{pendingChatImage=await compressChatImage(file);$('chatPreviewImg').src=pendingChatImage;$('chatImageName').textContent=file.name;$('chatImagePreview').hidden=false;$('chatStatus').textContent='Photo attached. Ask a question about it, then send.';$('chatInput').focus();}catch(err){$('chatStatus').textContent='Could not read image: '+err.message;}});
$('removeChatImage')?.addEventListener('click',()=>{pendingChatImage=null;$('chatImagePreview').hidden=true;$('chatImageInput').value='';});
function compressChatImage(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('File read failed'));reader.onload=()=>{const img=new Image();img.onerror=()=>reject(new Error('Image could not be opened'));img.onload=()=>{const scale=Math.min(1,1024/Math.max(img.width,img.height));const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(img.width*scale));canvas.height=Math.max(1,Math.round(img.height*scale));canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);resolve(canvas.toDataURL('image/jpeg',0.78));};img.src=reader.result;};reader.readAsDataURL(file);});}
$('chatInput')?.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat();}});
$('chatProvider')?.addEventListener('change',()=>{if($('aiProvider'))$('aiProvider').value=$('chatProvider').value;});
$('aiProvider')?.addEventListener('change',()=>{if($('chatProvider'))$('chatProvider').value=$('aiProvider').value;});
$('clearChatMemory')?.addEventListener('click',()=>{
  if(!confirm('Clear conversation memory and saved chat history from this browser? Approved training examples will remain unless exported/removed separately.'))return;
  chatHistory=[];localStorage.removeItem(CHAT_KEY);renderChat();$('chatStatus').textContent='Conversation memory cleared from this browser.';
});
$('exportLearning')?.addEventListener('click',()=>{
  if(!approvedExamples.length){$('chatStatus').textContent='No approved examples yet. Tap “Helpful · save example” under a good MJ AI answer first.';return;}
  const jsonl=approvedExamples.map(row=>JSON.stringify(row)).join('\n')+'\n';
  const blob=new Blob([jsonl],{type:'application/jsonl;charset=utf-8'});const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download='mj-ai-approved-learning.jsonl';document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url);
  $('chatStatus').textContent='Exported '+approvedExamples.length+' approved example(s). Review/remove private data before using it for fine-tuning.';
});
renderChat();

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
      browserWorker=new Worker('static/browser-ai-worker.js',{type:'module'});
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
    if(['cloud','ollama','adapter'].includes(provider)&&!API_BASE) throw new Error('Backend URL is not connected. Open ⚙ Backend connection and enter your deployed FastAPI/Render URL. GitHub Pages alone cannot run the server model.');
    if(provider==='offline') {
      data={text:offlineGenerate(prompt,mode),provider:'offline-template'};
    } else if(provider==='browser') {
      $('aiProgress').hidden=false;$('aiProgress').textContent='Preparing on-device model. First download may be large; keep this tab open.';
      const text=await askBrowserAI([{role:'system',content:modeInstruction(mode)},{role:'user',content:prompt}]);
      data={text,provider:'browser-local'};
    } else if(provider==='adapter'||provider==='ollama') {
      data=await api('/api/mj-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:provider==='adapter'?'adapter':'ollama',messages:[{role:'system',content:modeInstruction(mode)},{role:'user',content:prompt}],max_tokens:768,temperature:0.55})});
    } else if(provider==='cloud') {
      data=await api('/api/mj-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:'openai-compatible',messages:[{role:'system',content:modeInstruction(mode)},{role:'user',content:prompt}],max_tokens:1200,temperature:0.55})});
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
$('sendResultToChat')?.addEventListener('click',()=>{switchView('chat');$('chatInput').value='Improve this video plan, make it more original and production-ready:\\n\\n'+$('aiText').value;$('chatInput').focus();});
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
