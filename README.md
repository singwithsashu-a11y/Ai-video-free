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
- Browser-local multi-turn chat memory, user-approved positive examples, and JSONL export for a reviewed future fine-tuning dataset.
- Offline script/storyboard/caption templates that do not require a backend.

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

## Conversation memory and feedback-based learning

The **Talk to MJ AI · Learning Memory** panel keeps recent conversation history in the current browser's local storage and includes recent turns as context for follow-up replies. The user can clear that memory at any time. When an answer is useful, tap **Helpful · save example** to explicitly approve that user/assistant pair; use **Export approved learning data** to download a JSONL file. Review it for private information and incorrect answers before adding it to a training dataset.

This is a practical learning loop, not human-like self-training: conversation memory changes the context of replies but does not change model weights. Approved examples are not automatically sent to a server or automatically trained. Fine-tuning must be run deliberately, evaluated, and deployed as a new adapter. This prevents private chats or malicious feedback from silently poisoning the model.

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

### Install and smoke-test the completed GitHub Actions artifact

For the successful run linked in the project history, download the `mj-ai-improved-lora-adapter` artifact from [GitHub Actions run 40051547131](https://github.com/singwithsashu-a11y/Ai-video-free/actions/runs/40051547131), then extract it so `adapter_config.json` and `adapter_model.safetensors` are directly inside `models/mj-ai-lora/`. Do not commit the model files to Git.

~~~bash
pip install -r training/requirements-inference.txt
python training/test_adapter.py --adapter models/mj-ai-lora
~~~

This smoke test checks that the adapter loads and produces non-empty text for three prompts; it is not a quality or factual-accuracy benchmark. The successful training run used **64 examples for 2 epochs**, not one million. For the website API, set `MJ_AI_ADAPTER_PATH=models/mj-ai-lora` and `MJ_AI_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct` in the backend environment, then check `/api/mj-ai/status`. Select the `adapter` provider in requests to `/api/mj-ai/chat`. CPU inference can be slow and requires sufficient RAM.

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
- GitHub Pages is static hosting only; it cannot run FastAPI, SQLite, FFmpeg, or backend model inference. Browser AI and offline templates can work in the static frontend, but uploads, server-side media/project storage, and MP4 rendering require a separately hosted FastAPI backend. Configure the UI's **Connect to your backend** setting with the HTTPS URL of that API.
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

## Large-scale MJ AI training (1M examples)

The repository includes a Colab notebook at [training/MJ_AI_1M_Large_Scale_Training.ipynb](training/MJ_AI_1M_Large_Scale_Training.ipynb) for a real, user-supplied JSONL dataset with at least 1,000,000 valid chat examples. Store the dataset in Google Drive rather than Git; the notebook validates the row count, cleans/validates examples, runs LoRA fine-tuning, and exports the adapter ZIP to Drive. A GPU is strongly recommended, but Colab GPU access and runtime limits are not guaranteed; one million examples may need a paid/dedicated GPU or multiple planned runs.

**Important:** no million-example training has happened merely by adding this notebook. You must provide a million valid, high-quality examples and execute the notebook successfully. Do not inflate the dataset by repeating examples or generating low-quality synthetic duplicates. The output is a LoRA adapter for Qwen2.5-0.5B-Instruct, not a new foundation model. Evaluate on a held-out test set before using it in production.
