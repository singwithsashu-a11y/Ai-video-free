# AI Video Studio — Local-first, no API key required

A self-hostable video studio with FFmpeg editing and three writing modes:
- **Local Ollama** — real local language-model writing; no provider API key or cloud AI bill.
- **Offline Template** — works without Ollama, internet AI, or API keys; clearly labelled deterministic templates, not an LLM.
- **Optional Cloud API** — retains support for an OpenAI-compatible provider if you choose it.
- Upload video/audio/SRT, trim and export vertical 9:16, square 1:1, or landscape 16:9 MP4; merge clips.

## Important: where the AI runs

Ollama runs on the same machine as the Python backend by default at `http://127.0.0.1:11434`. If you open a website hosted on shared hosting, localhost means that hosting server — it does **not** mean your phone or personal computer. Most shared hosting plans cannot run Ollama models or GPU video-generation models. To use genuine local AI, run this backend on your own Windows/Linux/macOS computer (or a separate server that you control). The website can still be hosted separately, but the backend must be configured securely to reach your local service; do not expose Ollama directly to the public internet.

## Run locally

Requirements: Python 3.11+, FFmpeg and FFprobe on PATH. Ollama is optional if you only want editing and offline templates.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Enable real local AI (no API key)

1. Install Ollama from [ollama.com](https://ollama.com).
2. Download a model once (model files use disk space and the first download needs internet):
   ```bash
   ollama pull qwen2.5:3b
   ```
3. Keep Ollama running and start the video studio. The default endpoint is `http://127.0.0.1:11434` and default model is `qwen2.5:3b`.
4. In **AI creative assistant**, choose **Local Ollama · No API key**.

Optional environment variables:
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `OLLAMA_MODEL=qwen2.5:3b`

You can choose another model already installed in Ollama. Model speed/quality depends on your RAM, CPU/GPU, and model size. Local AI does not mean zero hardware requirements.

## Offline mode

Choose **Offline template · No install**. This mode needs no AI server and no API key, but it creates structured starter templates rather than intelligent, model-generated writing.

## Optional cloud AI

Set `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` in the backend environment and choose **Cloud API · Optional**. Never put secret API keys in browser JavaScript or commit them to GitHub.

## Current scope and limitations

This is an MVP, not a professional multi-track editor. AI text generation is local/cloud/offline as described above; full text-to-video diffusion, avatar generation, automatic speech transcription, user accounts, project collaboration, and cloud project management are not implemented by this starter. FFmpeg rendering requires FFmpeg/FFprobe installed on the backend host. Some shared hosts disable or limit FFmpeg and long-running processes.

Before public deployment, add authentication, per-user storage isolation, quotas, upload scanning, a background job queue, HTTPS, persistent storage, secret management, and cleanup policies. Do not expose this server publicly without appropriate protections.
