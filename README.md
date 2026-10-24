# MJ AI Studio — AI Video Editor & Model Lab

**MJ AI Studio** is a self-hostable video-editing workspace with an optional AI writing assistant and an experimental fine-tuning pipeline. It combines a responsive web interface, FastAPI backend, FFmpeg rendering, project persistence, and multiple text-generation options.

> **Reality check:** this repository does not contain a ChatGPT/Claude-class model trained from scratch. The MJ AI training pipeline fine-tunes a small existing model with LoRA. Quality depends on the base model, training data, compute, and evaluation. A successful workflow run proves the training job completed—not that the model is excellent.

## Features

- Upload common video/audio formats and SRT subtitles.
- Manage a server-side media library and saved projects.
- Combine clips, trim video, choose 9:16 / 16:9 / 1:1 output, and export MP4 in supported resolutions.
- Mix background music with original audio and adjust music volume.
- Burn SRT subtitles into rendered video.
- AI writing for scripts, storyboards, captions, and hashtags.
- AI options: browser-local Qwen (experimental), Ollama, optional OpenAI-compatible endpoint, offline templates, and optional MJ AI LoRA adapter inference.
- Training scripts and a manually triggered GitHub Actions LoRA training workflow.
- Responsive interface for desktop and mobile.

## Quick start (local)

### Requirements
- Python 3.11+
- FFmpeg and FFprobe installed and available on PATH
- For AI inference/training, see the model sections below

### Install and run

~~~bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

Open http://127.0.0.1:8000.

Optional server configuration (set these in your host's environment, not frontend JavaScript):

~~~env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
MJ_AI_ADAPTER_PATH=models/mj-ai-lora
MJ_AI_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
~~~

For an optional OpenAI-compatible server, configure AI_BASE_URL, AI_API_KEY, and AI_MODEL on the backend only. Never commit secrets to Git.

## Run AI without a provider API key

### Browser-local Qwen (experimental)
The Browser AI option downloads onnx-community/Qwen2.5-0.5B-Instruct through Transformers.js/CDN and generates in the browser after loading. The initial download may use hundreds of MB of data/storage and substantial RAM. WebGPU/WASM support varies by device and browser; low-memory Android devices may fail. This uses the base model and **does not load the server-side MJ AI LoRA adapter**.

### Local Ollama
Install Ollama on the machine running the backend, download a compatible model such as qwen2.5:3b, then configure OLLAMA_BASE_URL and OLLAMA_MODEL. Ollama runs on the backend host, not automatically on each visitor's phone.

### MJ AI LoRA adapter
The adapter is a small set of learned weights, **not a standalone model**. Load it with the same base model used during training. After downloading the training artifact, extract it so adapter_config.json and adapter weights are directly inside the configured adapter directory. Keep model files out of Git.

~~~bash
pip install -r training/requirements-inference.txt
~~~

Example environment settings:

~~~env
MJ_AI_ADAPTER_PATH=models/mj-ai-lora
MJ_AI_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
~~~

## Train or retrain MJ AI

The repository includes a manual GitHub Actions workflow: [MJ AI LoRA Training](.github/workflows/mj-ai-train.yml).

1. Open the repository's **Actions** tab.
2. Select **MJ AI LoRA Training**.
3. Click **Run workflow**.
4. Start with the default small base model and one epoch for a smoke test.
5. Wait for the run to finish and inspect every step.
6. If successful, download the mj-ai-lora-adapter artifact from that run (artifact retention is limited).
7. Evaluate the adapter on prompts that were not used for training before deploying it.

The workflow uses a standard GitHub-hosted CPU runner. Model downloads and fine-tuning can take a long time, run out of memory, or hit the job timeout. GitHub Actions does not provide a free GPU by default; a completed CPU run is only a small experiment. For serious training, use a compatible GPU environment and monitor quotas/costs.

### Train locally

~~~bash
python training/prepare_dataset.py training/seed_data.jsonl /tmp/mj-ai-processed.jsonl
pip install transformers datasets peft accelerate
python training/train_lora.py \\
  --model Qwen/Qwen2.5-0.5B-Instruct \\
  --data /tmp/mj-ai-processed.jsonl \\
  --output training/output/mj-ai-lora \\
  --epochs 1 \\
  --max-length 256
~~~

Use only data you own or have permission to use. Keep private data, credentials, and copyrighted material you cannot use out of the dataset. Expand and review seed examples, maintain a held-out evaluation set, compare before/after outputs, and preserve the base model. See [training/README.md](training/README.md), [model plan](training/MJ_AI_MODEL_PLAN.md), and [adapter deployment notes](training/ADAPTER_DEPLOYMENT.md).

## Deployment

- [Namecheap / cPanel deployment guide](DEPLOY_NAMECHEAP.md)
- GitHub Pages is static hosting only; it cannot run FastAPI, SQLite, FFmpeg, or backend model inference. Configure the UI's **Connect to your backend** setting with the HTTPS URL of a separately hosted API.
- For a Pages frontend, set STUDIO_CORS_ORIGINS on the backend to the exact frontend origin (typically https://singwithsashu-a11y.github.io).
- Shared hosting may restrict FFmpeg, long renders, file sizes, persistent storage, and machine-learning dependencies. Verify the host supports the required runtime before deployment.

## API overview

- GET /api/health — backend/tool health and upload limits.
- POST /api/upload, GET /api/media, GET /api/media/{filename}, DELETE /api/media/{file_id} — media library.
- POST /api/render, GET /api/download/{filename} — video rendering and download.
- GET/POST /api/projects, GET/PUT/DELETE /api/projects/{id} — project persistence.
- GET /api/local-ai/status, POST /api/local-ai — local/offline generation modes.
- GET /api/mj-ai/status, POST /api/mj-ai/chat — MJ AI, Ollama, compatible endpoint, and optional adapter inference.
- POST /api/ai — optional OpenAI-compatible writing endpoint.

## Security and known limitations

This is an evolving starter, not yet a hardened public multi-user production service. The project does not currently provide a complete authentication/tenant-isolation system, public API abuse controls, a background render queue, per-user quotas, malware scanning, or cloud object storage. Do not expose private user media on an untrusted public deployment until access controls are implemented and tested. Add HTTPS, authentication, upload/request limits, backups, cleanup, monitoring, and rate limits before production use.

Video editing here is a practical FFmpeg-based workflow, not a full professional non-linear editor or a text-to-video diffusion model. Contributions and bug reports are welcome.
