import os, uuid, subprocess, json
from pathlib import Path
from typing import Optional
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.local_ai import router as local_ai_router

BASE = Path(__file__).resolve().parent.parent
STORAGE = BASE / "storage"
UPLOADS = STORAGE / "uploads"
OUTPUTS = STORAGE / "outputs"
for p in (UPLOADS, OUTPUTS):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Claude AI Free Video Studio")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
app.include_router(local_ai_router)
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".m4a", ".aac", ".srt"}

def run(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except FileNotFoundError:
        raise HTTPException(500, "FFmpeg/FFprobe is not installed or not on PATH.")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Render timed out. Try a shorter/smaller video.")
    if proc.returncode:
        raise HTTPException(400, (proc.stderr or "FFmpeg failed")[-1800:])
    return proc

def probe(path):
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name",
             "-show_entries", "stream=codec_type,width,height,codec_name", "-of", "json", str(path)])
    return json.loads(p.stdout)

@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    try:
        v = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        ffmpeg = v.returncode == 0
    except Exception:
        ffmpeg = False
    return {"ok": True, "ffmpeg_available": ffmpeg}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(415, f"Unsupported file type: {suffix or 'unknown'}")
    data = await file.read((MAX_MB * 1024 * 1024) + 1)
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_MB} MB limit.")
    uid = uuid.uuid4().hex
    target = UPLOADS / f"{uid}{suffix}"
    target.write_bytes(data)
    metadata = {}
    if suffix != ".srt":
        metadata = probe(target)
    return {"id": uid, "name": Path(file.filename or target.name).name,
            "path": str(target.relative_to(BASE)), "url": f"/api/media/{target.name}",
            "size": len(data), "metadata": metadata}

@app.get("/api/media/{filename}")
def media(filename: str):
    path = (UPLOADS / Path(filename).name).resolve()
    if not path.exists() or path.parent != UPLOADS.resolve():
        raise HTTPException(404, "File not found")
    return FileResponse(path)

class RenderRequest(BaseModel):
    files: list[str]
    operation: str = "edit"
    start: float = 0
    end: Optional[float] = None
    aspect: str = "9:16"
    resolution: str = "1080"
    subtitles_id: Optional[str] = None
    burn_subtitles: bool = False
    output_name: str = "my-video"

@app.post("/api/render")
def render(req: RenderRequest):
    if not req.files:
        raise HTTPException(400, "Upload at least one video first.")
    paths = []
    for fid in req.files:
        matches = list(UPLOADS.glob(f"{Path(fid).name}.*"))
        if not matches:
            matches = [p for p in UPLOADS.iterdir() if p.stem == Path(fid).stem]
        if not matches:
            raise HTTPException(404, f"Uploaded file not found: {fid}")
        paths.append(matches[0])
    if any(p.suffix.lower() == ".srt" for p in paths):
        raise HTTPException(400, "Choose video/audio files in the clip list; SRT files cannot be rendered as clips.")
    out_id = uuid.uuid4().hex
    out = OUTPUTS / f"{out_id}.mp4"
    width, height = {"9:16": (1080,1920), "16:9": (1920,1080), "1:1": (1080,1080)}.get(req.aspect, (1080,1920))
    if req.resolution == "720":
        width, height = (720,1280) if req.aspect == "9:16" else ((1280,720) if req.aspect == "16:9" else (720,720))
    filters = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    if len(paths) > 1:
        cmd = ["ffmpeg", "-y"]
        for p in paths:
            cmd += ["-i", str(p)]
        graph = "".join(f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v{i}];" for i in range(len(paths)))
        graph += "".join(f"[{i}:a]aresample=44100[a{i}];" for i in range(len(paths)))
        graph += "".join(f"[v{i}][a{i}]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=1:a=1[v][a]"
        cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-movflags", "+faststart", str(out)]
    else:
        p = paths[0]
        cmd = ["ffmpeg", "-y", "-i", str(p)]
        if req.start > 0:
            cmd += ["-ss", str(max(0, req.start))]
        if req.end is not None:
            duration = req.end - max(0, req.start)
            if duration <= 0:
                raise HTTPException(400, "End time must be greater than start time.")
            cmd += ["-t", str(duration)]
        cmd += ["-vf", filters, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    run(cmd)
    safe_name = "".join(c for c in req.output_name.strip() if c.isalnum() or c in "-_ ")[:70] or "my-video"
    return {"id": out_id, "url": f"/api/download/{out.name}", "filename": f"{safe_name}.mp4"}

@app.get("/api/download/{filename}")
def download(filename: str):
    path = (OUTPUTS / Path(filename).name).resolve()
    if not path.exists() or path.parent != OUTPUTS.resolve():
        raise HTTPException(404, "Rendered file not found")
    return FileResponse(path, media_type="video/mp4", filename=path.name)

class AIRequest(BaseModel):
    prompt: str
    mode: str = "script"

@app.post("/api/ai")
async def ai(req: AIRequest):
    base = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
    key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "").strip()
    if not base or not key or not model:
        raise HTTPException(400, "Set AI_BASE_URL, AI_API_KEY and AI_MODEL in server environment, then restart. Keep keys off the frontend.")
    system = {
      "script": "You are a skilled video scriptwriter. Produce a clear scene-by-scene short video script with narration, visual direction, and on-screen text. Match the user's language.",
      "caption": "Write 5 concise social video captions and relevant hashtags. Match the user's language.",
      "storyboard": "Create a practical scene-by-scene storyboard for a video, with shot, action, visual, on-screen text, and sound notes. Match the user's language."
    }.get(req.mode, "You are a helpful video production assistant. Match the user's language.")
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role":"system","content":system},{"role":"user","content":req.prompt}], "temperature":0.7})
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f"AI provider error: {r.text[:800]}")
        data = r.json()
        return {"text": data["choices"][0]["message"]["content"]}
    except httpx.RequestError as e:
        raise HTTPException(502, f"Could not reach AI provider: {str(e)}")
