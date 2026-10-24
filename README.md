# MJ AI Studio — self-hostable AI video workspace

A responsive video editing starter with an actual FastAPI/FFmpeg backend, project saving, media library, optional server-side AI providers, and experimental browser-local Qwen generation.

## Current features

- Upload MP4, MOV, MKV, WEBM, AVI, M4V, MP3, WAV, M4A, AAC, OGG, FLAC and SRT files.
- Persistent media library stored on the server; list and remove uploaded files.
- Combine multiple video clips, trim a single clip, and export portrait 9:16, landscape 16:9 or square 1:1 MP4 in 720p or 1080p.
- Optional background soundtrack mixed with original clip audio, with adjustable music volume.
- Optional SRT subtitle burn-in.
- Save, load, update and delete project settings using SQLite.
- AI writing modes: script, storyboard, captions/hashtags.
- AI engines: browser-local Qwen model (no API key; experimental), local Ollama, the trained MJ AI LoRA adapter, offline template mode, or an optional OpenAI-compatible server provider.
- Mobile-responsive interface.

## Important model notes

**The LoRA adapter is not a complete model.** It must be loaded with the matching base model, currently `Qwen/Qwen2.5-0.5B-Instruct`. Download the adapter artifact from the successful GitHub Actions run, extract it so `adapter_config.json` is directly inside the adapter directory, and keep the weights on the backend host (not in Git).

The starter training dataset contains only a handful of examples. A successful training job verifies that the pipeline ran; it does not prove the adapter is high quality. Evaluate with held-out prompts and expand the dataset before relying on it.

### Browser-local AI on Android

The **Browser AI** option loads `onnx-community/Qwen2.5-0.5B-Instruct` via Transformers.js from a CDN. The first run downloads model files and can use hundreds of MB of data/storage and substantial RAM. Generation runs in the browser after loading, without a provider API key. WebGPU and WASM support vary by Android device/browser; low-memory devices may fail. This browser mode uses the base model, not the trained server-side LoRA adapter.

### Ollama and adapter inference

Ollama and the adapter run on the machine hosting the Python backend. They do not automatically run on the visitor's phone. Configure server environment variables:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
MJ_AI_ADAPTER_PATH=models/mj-ai-lora
MJ_AI_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
```

For adapter inference, install optional dependencies in the backend environment:

```bash
pip install -r training/requirements-inference.txt
```

For optional OpenAI-compatible inference, configure `AI_BASE_URL`, `AI_API_KEY` and `AI_MODEL` on the server. Never put provider keys in frontend JavaScript or commit them to Git.

## Run locally

Requirements: Python 3.11+, FFmpeg and FFprobe available on PATH.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Namecheap / cPanel deployment

See [DEPLOY_NAMECHEAP.md](DEPLOY_NAMECHEAP.md). Shared hosting can serve the frontend and may run the Python API through cPanel Setup Python App/Passenger, depending on the plan. **FFmpeg, long-running renders, large uploads, SQLite persistence, and ML inference may be restricted by the host.** Browser-local AI is the most realistic no-key option on a static/shared host, while rendering still needs the backend and FFmpeg. If the host does not provide FFmpeg, render jobs will not work there.

## API overview

- `GET /api/health` — backend, FFmpeg/FFprobe and upload limit.
- `POST /api/upload` — upload a media file.
- `GET /api/media` — list uploaded media.
- `GET /api/media/{filename}` — serve uploaded media.
- `DELETE /api/media/{file_id}` — remove uploaded media.
- `POST /api/render` — render clips with optional soundtrack and burned-in SRT.
- `GET /api/download/{filename}` — download rendered MP4.
- `GET /api/projects`, `POST /api/projects`, `GET/PUT/DELETE /api/projects/{id}` — project settings CRUD.
- `GET /api/local-ai/status`, `POST /api/local-ai` — Ollama and offline template modes.
- `GET /api/mj-ai/status`, `POST /api/mj-ai/chat` — Ollama, OpenAI-compatible and optional LoRA adapter inference.
- `POST /api/ai` — optional OpenAI-compatible script-writing endpoint.

## Security and production limitations

This starter does not yet include user accounts, tenant isolation, a public-facing authentication layer, a background render queue, per-user quotas, malware scanning, or cloud object storage. **Do not expose an untrusted public deployment with private media until authentication and access controls are added.** Uploaded files and project records are stored on the backend host. Add HTTPS, request limits, authentication, backups, cleanup policies and monitoring before production use.

This is an editing and writing starter, not a full professional non-linear editor or a text-to-video diffusion service.
