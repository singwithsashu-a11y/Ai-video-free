# Claude AI Free Video Studio

An all-in-one, self-hostable AI video studio starter. The mobile-friendly interface includes:
- Upload video/audio and SRT subtitle files
- Trim clips and export vertical 9:16, square 1:1, or landscape 16:9 MP4
- Merge multiple clips
- Generate scripts, storyboards, captions, and hashtags using an OpenAI-compatible chat API
- FFmpeg-based rendering and downloadable output

## Requirements
- Python 3.11+
- FFmpeg and FFprobe installed and available on PATH

## Run locally
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open http://localhost:8000

## Configure AI
Set `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` in your server environment. The base URL should be the provider's OpenAI-compatible API base URL (the app appends `/chat/completions`). Restart the server after changing variables. Never place secret API keys in browser JavaScript or commit them to GitHub. Provider free tiers, limits, and pricing can change; this project does not include API credits.

## Current scope
This is an MVP starter, not a full professional timeline editor. Drag-and-drop timeline editing, automatic speech-to-text subtitles, AI text-to-video generation, avatar generation, accounts, and cloud project management are not implemented yet.

## Before public deployment
Add authentication, per-user storage isolation, quotas, upload scanning, a background job queue, HTTPS, persistent storage, secret management, and cleanup policies. Do not expose this server publicly without appropriate protections.
