import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.2';

env.allowLocalModels = false;
env.useBrowserCache = true;

let generatorPromise = null;
const MODEL_ID = 'onnx-community/Qwen2.5-0.5B-Instruct';

function progressText(progress) {
  if (progress?.status === 'progress') {
    const pct = Number.isFinite(progress.progress) ? Math.round(progress.progress) + '%' : '';
    return 'Downloading on-device model files ' + pct;
  }
  if (progress?.status === 'done') return 'Model file ready';
  if (progress?.status === 'initiate') return 'Preparing model file…';
  if (progress?.status === 'download') return 'Downloading model file…';
  return progress?.status ? 'Loading model: ' + progress.status : 'Loading on-device Qwen model…';
}

async function getGenerator() {
  if (!generatorPromise) {
    generatorPromise = pipeline('text-generation', MODEL_ID, {
      dtype: 'q4',
      device: self.navigator?.gpu ? 'webgpu' : 'wasm',
      progress_callback: progress => self.postMessage({type:'progress', message:progressText(progress)})
    }).catch(error => {
      generatorPromise = null;
      throw error;
    });
  }
  return generatorPromise;
}

self.onmessage = async event => {
  const request = event.data || {};
  if (request.type !== 'generate') return;
  try {
    self.postMessage({type:'progress',message:'Loading the small on-device model. First use can take several minutes; Cloud AI is faster when configured.'});
    const generator = await getGenerator();
    self.postMessage({type:'progress',message:'Generating on your device…'});
    const output = await generator(request.messages || [], {
      max_new_tokens: 192,
      do_sample: true,
      temperature: 0.55,
      repetition_penalty: 1.08
    });
    let generated = output?.[0]?.generated_text;
    let answer = '';
    if (Array.isArray(generated)) {
      const assistants = generated.filter(message => message && message.role === 'assistant');
      answer = String(assistants.at(-1)?.content || '');
    } else if (typeof generated === 'string') {
      answer = generated;
    }
    if (!answer.trim()) throw new Error('The browser model returned an empty response.');
    self.postMessage({type:'result',text:answer.trim()});
  } catch (error) {
    self.postMessage({
      type:'error',
      message:'Browser AI could not run on this device. It may need more RAM, a compatible browser/WebGPU setup, or a successful model download. Details: ' + (error?.message || String(error))
    });
  }
};
