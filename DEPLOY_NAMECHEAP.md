# Namecheap cPanel deployment notes

This guide is for the existing FastAPI application in this repository. Exact capabilities depend on the Namecheap hosting plan.

## 1. Create a Python application

1. In cPanel, open **Setup Python App** (if your plan provides it).
2. Select Python 3.11 or newer.
3. Choose an application root outside the public web document root when possible, for example `mj-ai-studio`.
4. Set the application URL and startup configuration according to the cPanel/Passenger interface.
5. Upload/clone this repository into the application root.
6. Install the packages from `requirements.txt` into the virtual environment created by cPanel.

The repository includes `passenger_wsgi.py` as the Passenger entry point. If the host asks for an application startup file, use `passenger_wsgi.py`; the callable is named `application`. Follow the host's exact instructions for the Python application root and restart mechanism.

## 2. Persistent writable directories

The Python process needs write access to `storage/uploads` and `storage/outputs`. The SQLite project/media database is created at `storage/studio.sqlite3`. Confirm the application user can write to these paths. Back up this directory before upgrades or cleanup.

## 3. FFmpeg is required for server rendering

The backend calls both `ffmpeg` and `ffprobe` from PATH. Some shared-hosting plans do not provide these binaries or do not allow long-running processes. Check with hosting support whether both binaries are available and permitted. If they are unavailable, the website and browser AI may load but server-side MP4 rendering will return an error. Do not try to bypass host restrictions.

## 4. Environment variables

Configure environment variables in the cPanel Python app interface or the host-supported environment file location. Do not expose secrets in `static/` or commit them.

Optional local Ollama (only if the same server can run Ollama):
```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
```

Optional server-side LoRA adapter:
```env
MJ_AI_ADAPTER_PATH=/absolute/path/to/models/mj-ai-lora
MJ_AI_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
```

Install `training/requirements-inference.txt` only if you have sufficient disk/RAM and the host allows PyTorch/Transformers. Shared hosting usually is not suitable for loading language models or GPU inference. The base model downloads separately.

Optional cloud provider:
```env
AI_BASE_URL=
AI_API_KEY=
AI_MODEL=
```

## 5. Browser AI

The frontend's Browser AI mode downloads the small ONNX Qwen model directly to each visitor's browser via a CDN. It does not require an API key or server-side model runtime, but the initial download can be large and mobile RAM/browser support varies. It does not use the trained LoRA adapter.

## 6. Verify deployment

After restarting the app:
- Open the configured website URL.
- Check `/api/health` for backend and FFmpeg/FFprobe availability.
- Check `/api/mj-ai/status` for server-side provider/adapter status.
- Upload a short test video and render 720p first.
- Try Browser AI separately; the first model download requires internet.

## 7. Public deployment warning

This starter currently has no login or per-user authorization. Anyone who can reach an exposed API may be able to upload media, render jobs, or alter/delete projects and media. Do not put private media on a public instance until authentication, quotas and access controls are implemented. Keep uploads/outputs out of public document directories when your hosting layout allows it.
