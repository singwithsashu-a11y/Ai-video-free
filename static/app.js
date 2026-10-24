const uploaded = [];
const $ = id => document.getElementById(id);
const status = (msg, bad=false) => { $('status').textContent=msg; $('status').style.color=bad?'#ff9a9a':'#a1a8b8'; };
async function api(url, options={}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(()=>({detail:'Unexpected server response'}));
  if(!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}
(async()=>{try{const h=await api('/api/health');status(h.ffmpeg_available?'Renderer ready · FFmpeg detected':'Server online · Install FFmpeg to enable video rendering',!h.ffmpeg_available)}catch(e){status('Could not connect to the server: '+e.message,true)}})();
$('files').addEventListener('change', async e=>{
 for(const file of e.target.files){
  const fd=new FormData();fd.append('file',file);
  const item=document.createElement('div');item.className='media-item';item.textContent='Uploading '+file.name+'…';$('mediaList').prepend(item);
  try{const data=await api('/api/upload',{method:'POST',body:fd});uploaded.push({...data,original:file.name});item.innerHTML='';
   const left=document.createElement('span');left.textContent=data.name;
   const right=document.createElement('small');right.textContent=(data.size/1024/1024).toFixed(1)+' MB';
   item.append(left,right);item.dataset.id=data.id;item.dataset.name=data.name;
   item.title='Uploaded successfully';
  }catch(err){item.textContent=file.name+': '+err.message;item.style.color='#ff9a9a'}
 }
 e.target.value='';
});
$('render').addEventListener('click',async()=>{
 const vids=uploaded.filter(x=>!x.name.toLowerCase().endsWith('.srt'));
 if(!vids.length){$('renderStatus').textContent='Upload at least one video/audio file first.';return}
 const btn=$('render');btn.disabled=true;$('renderStatus').textContent='Rendering… Larger videos can take a while.';
 try{
  const endVal=$('end').value;
  const data=await api('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:vids.map(x=>x.id),start:Number($('start').value||0),end:endVal===''?null:Number(endVal),aspect:$('aspect').value,resolution:$('resolution').value,output_name:$('outputName').value})});
  $('renderStatus').innerHTML='Render complete. <a style="color:#a8f0cb" href="'+data.url+'" download>Download MP4</a>';
 }catch(err){$('renderStatus').textContent=err.message;$('renderStatus').style.color='#ff9a9a'}
 finally{btn.disabled=false}
});
$('generate').addEventListener('click',async()=>{
 const prompt=$('prompt').value.trim();if(!prompt){$('aiText').value='Describe your video idea first.';$('aiResult').hidden=false;return}
 const btn=$('generate');btn.disabled=true;btn.textContent='Generating…';$('aiResult').hidden=false;$('aiText').value='Working…';
 const provider=$('aiProvider').value;
 const mode=$('aiMode').value;
 const endpoint=provider==='cloud'?'/api/ai':provider==='adapter'?'/api/mj-ai/chat':'/api/local-ai';
 const instructions={script:'Write a practical video script with narration, scene-by-scene visuals, and on-screen text. Match the user language.',storyboard:'Create a scene-by-scene storyboard with shot, action, visual, on-screen text, and sound notes. Match the user language.',caption:'Write 5 concise social-video captions and relevant hashtags. Match the user language.'};
 const body=provider==='cloud'?{prompt,mode}:provider==='adapter'?{provider:'adapter',messages:[{role:'system',content:instructions[mode]||instructions.script},{role:'user',content:prompt}]}:{prompt,mode,provider};
 try{const data=await api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('aiText').value=data.text+(data.model?'\n\n[Model: '+data.model+']':'')}
 catch(err){$('aiText').value=err.message}
 finally{btn.disabled=false;btn.textContent='✦ Generate'}
});
$('copy').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('aiText').value);$('copy').textContent='Copied!';setTimeout(()=>$('copy').textContent='Copy result',1200)}catch(e){$('aiText').select();document.execCommand('copy')}});