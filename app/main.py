"""MJ AI Video Studio API: uploads, FFmpeg rendering, projects, and AI routes."""
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.local_ai import router as local_ai_router
from app.mj_ai import router as mj_ai_router

BASE = Path(__file__).resolve().parent.parent
STORAGE = BASE / "storage"
UPLOADS = STORAGE / "uploads"
OUTPUTS = STORAGE / "outputs"
DB_PATH = STORAGE / "studio.sqlite3"
for folder in (UPLOADS, OUTPUTS):
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MJ AI Video Studio", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
app.include_router(local_ai_router)
app.include_router(mj_ai_router)

MAX_MB = max(1, int(os.getenv("MAX_UPLOAD_MB", os.getenv("MAX_FILE_SIZE_MB", "500"))))
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
SUBTITLE_EXTS = {".srt"}
ALLOWED = VIDEO_EXTS | AUDIO_EXTS | SUBTITLE_EXTS


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")


init_db()


def run(cmd, *, timeout=3600):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise HTTPException(500, "FFmpeg/FFprobe is not installed or not on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "Render timed out. Try a shorter or smaller video.") from exc
    if proc.returncode:
        detail = (proc.stderr or "FFmpeg failed")[-1800:]
        raise HTTPException(400, detail)
    return proc


def probe(path: Path):
    proc = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,format_name:stream=codec_type,width,height,codec_name",
        "-of", "json", str(path),
    ], timeout=30)
    try:
        data = json.loads(proc.stdout)
        data["duration"] = float(data.get("format", {}).get("duration", 0) or 0)
        data["streams"] = data.get("streams", [])
        return data
    except (ValueError, TypeError):
        raise HTTPException(422, "Could not read media metadata. Check that the file is valid.")


def uploaded_path(file_id: str) -> Path:
    # IDs are generated UUIDs; never accept arbitrary filesystem paths from a request.
    candidate_id = Path(file_id or "").name
    if not re.fullmatch(r"[a-f0-9]{32}", candidate_id):
        raise HTTPException(400, "Invalid uploaded file ID.")
    matches = list(UPLOADS.glob(f"{candidate_id}.*"))
    if len(matches) != 1:
        raise HTTPException(404, "Uploaded file not found. Upload it again.")
    path = matches[0].resolve()
    if path.parent != UPLOADS.resolve():
        raise HTTPException(400, "Invalid media path.")
    return path


def subtitle_filter(path: Path) -> str:
    # Escape characters interpreted by FFmpeg's filter parser.
    value = str(path.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,").replace("[", "\\[").replace("]", "\\]")
    return f"subtitles='{value}'"


@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    versions = {}
    for binary in ("ffmpeg", "ffprobe"):
        try:
            proc = subprocess.run([binary, "-version"], capture_output=True, text=True, timeout=5)
            versions[binary] = proc.returncode == 0
        except Exception:
            versions[binary] = False
    return {"ok": True, "ffmpeg_available": versions["ffmpeg"], "ffprobe_available": versions["ffprobe"], "max_upload_mb": MAX_MB}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    original_name = Path(file.filename or "upload").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(415, f"Unsupported file type: {suffix or 'unknown'}")
    data = await file.read((MAX_MB * 1024 * 1024) + 1)
    await file.close()
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds the {MAX_MB} MB upload limit.")
    file_id = uuid.uuid4().hex
    target = UPLOADS / f"{file_id}{suffix}"
    target.write_bytes(data)
    metadata = {}
    kind = "subtitle" if suffix in SUBTITLE_EXTS else ("audio" if suffix in AUDIO_EXTS else "video")
    if kind != "subtitle":
        try:
            metadata = probe(target)
            streams = metadata.get("streams", [])
            if kind == "video" and not any(s.get("codec_type") == "video" for s in streams):
                target.unlink(missing_ok=True)
                raise HTTPException(415, "This file does not contain a video stream.")
            if kind == "audio" and not any(s.get("codec_type") == "audio" for s in streams):
                target.unlink(missing_ok=True)
                raise HTTPException(415, "This file does not contain an audio stream.")
        except HTTPException:
            target.unlink(missing_ok=True)
            raise
    return {"id": file_id, "name": original_name, "kind": kind,
            "url": f"/api/media/{target.name}", "size": len(data), "metadata": metadata}


@app.get("/api/media/{filename}")
def media(filename: str):
    safe_name = Path(filename).name
    path = (UPLOADS / safe_name).resolve()
    if not path.exists() or path.parent != UPLOADS.resolve():
        raise HTTPException(404, "File not found.")
    return FileResponse(path)


@app.delete("/api/media/{file_id}")
def delete_media(file_id: str):
    path = uploaded_path(file_id)
    path.unlink(missing_ok=True)
    return {"ok": True, "deleted_id": file_id}


class ProjectInput(BaseModel):
    name: str = Field(default="Untitled project", min_length=1, max_length=100)
    data: dict = Field(default_factory=dict)


@app.get("/api/projects")
def list_projects():
    with db() as conn:
        rows = conn.execute("SELECT id, name, created_at, updated_at FROM projects ORDER BY updated_at DESC LIMIT 100").fetchall()
    return {"projects": [dict(row) for row in rows]}


@app.post("/api/projects")
def save_project(req: ProjectInput):
    project_id = uuid.uuid4().hex
    now = utc_now()
    with db() as conn:
        conn.execute("INSERT INTO projects(id,name,data,created_at,updated_at) VALUES(?,?,?,?,?)",
                     (project_id, req.name.strip(), json.dumps(req.data), now, now))
    return {"id": project_id, "name": req.name.strip(), "data": req.data, "created_at": now, "updated_at": now}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Project not found.")
    return {"id": row["id"], "name": row["name"], "data": json.loads(row["data"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"]}


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, req: ProjectInput):
    now = utc_now()
    with db() as conn:
        cur = conn.execute("UPDATE projects SET name=?, data=?, updated_at=? WHERE id=?",
                           (req.name.strip(), json.dumps(req.data), now, project_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Project not found.")
        row = conn.execute("SELECT created_at FROM projects WHERE id=?", (project_id,)).fetchone()
    return {"id": project_id, "name": req.name.strip(), "data": req.data, "created_at": row["created_at"], "updated_at": now}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    with db() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Project not found.")
    return {"ok": True, "deleted_id": project_id}


class RenderRequest(BaseModel):
    files: list[str] = Field(min_length=1, max_length=30)
    start: float = Field(default=0, ge=0)
    end: Optional[float] = Field(default=None, gt=0)
    aspect: str = "9:16"
    resolution: str = "1080"
    audio_id: Optional[str] = None
    subtitles_id: Optional[str] = None
    burn_subtitles: bool = False
    music_volume: float = Field(default=0.25, ge=0, le=2)
    output_name: str = Field(default="my-video", max_length=100)


@app.post("/api/render")
def render(req: RenderRequest):
    if req.aspect not in {"9:16", "16:9", "1:1"}:
        raise HTTPException(422, "Aspect must be 9:16, 16:9, or 1:1.")
    if req.resolution not in {"720", "1080"}:
        raise HTTPException(422, "Resolution must be 720 or 1080.")
    paths = [uploaded_path(fid) for fid in req.files]
    if any(p.suffix.lower() not in VIDEO_EXTS for p in paths):
        raise HTTPException(400, "Choose video files only in the clip list.")
    audio_path = uploaded_path(req.audio_id) if req.audio_id else None
    if audio_path and audio_path.suffix.lower() not in AUDIO_EXTS:
        raise HTTPException(400, "The selected soundtrack is not an audio file.")
    srt_path = uploaded_path(req.subtitles_id) if req.subtitles_id else None
    if srt_path and srt_path.suffix.lower() not in SUBTITLE_EXTS:
        raise HTTPException(400, "The selected subtitle file must be an SRT file.")
    if req.burn_subtitles and not srt_path:
        raise HTTPException(400, "Choose an SRT subtitle file before enabling subtitle burn-in.")

    width, height = {
        ("9:16", "1080"): (1080, 1920), ("16:9", "1080"): (1920, 1080), ("1:1", "1080"): (1080, 1080),
        ("9:16", "720"): (720, 1280), ("16:9", "720"): (1280, 720), ("1:1", "720"): (720, 720),
    }[(req.aspect, req.resolution)]
    output_id = uuid.uuid4().hex
    output_path = OUTPUTS / f"{output_id}.mp4"

    with tempfile.TemporaryDirectory(prefix="mj-ai-render-") as temp_name:
        temp = Path(temp_name)
        normalized = []
        for index, source in enumerate(paths):
            metadata = probe(source)
            streams = metadata.get("streams", [])
            if not any(s.get("codec_type") == "video" for s in streams):
                raise HTTPException(422, f"{source.name} does not contain a video stream.")
            duration = float(metadata.get("duration") or 0)
            if duration <= 0:
                raise HTTPException(422, f"Could not determine duration of {source.name}.")
            start = req.start if len(paths) == 1 else 0
            end = req.end if len(paths) == 1 and req.end is not None else duration
            if start >= duration or end <= start:
                raise HTTPException(422, "Trim end must be greater than trim start and within the video duration.")
            end = min(end, duration)
            clip_duration = end - start
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            target = temp / f"clip-{index:03d}.mp4"
            cmd = ["ffmpeg", "-y"]
            if start:
                cmd += ["-ss", str(start)]
            cmd += ["-i", str(source)]
            if not has_audio:
                cmd += ["-f", "lavfi", "-t", str(clip_duration), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
            cmd += ["-t", str(clip_duration), "-map", "0:v:0"]
            cmd += ["-map", "0:a:0" if has_audio else "1:a:0"]
            vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
            cmd += ["-vf", vf, "-af", "aresample=44100", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "22", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                    "-movflags", "+faststart", str(target)]
            run(cmd, timeout=1800)
            normalized.append(target)

        concat_list = temp / "concat.txt"
        concat_list.write_text("".join(f"file '{str(p).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in normalized), encoding="utf-8")
        joined = temp / "joined.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(joined)], timeout=1800)

        cmd = ["ffmpeg", "-y", "-i", str(joined)]
        if audio_path:
            cmd += ["-i", str(audio_path)]
        video_filter = subtitle_filter(srt_path) if req.burn_subtitles and srt_path else None
        if audio_path:
            filter_parts = [f"[0:a]volume=1.0[original]", f"[1:a]volume={req.music_volume}[music]",
                            "[original][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"]
            if video_filter:
                filter_parts.insert(0, f"[0:v]{video_filter}[vout]")
            cmd += ["-filter_complex", ";".join(filter_parts)]
            cmd += ["-map", "[vout]" if video_filter else "0:v:0", "-map", "[aout]"]
        else:
            if video_filter:
                cmd += ["-vf", video_filter]
            cmd += ["-map", "0:v:0", "-map", "0:a:0"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path)]
        run(cmd, timeout=3600)

    safe_name = "".join(c for c in req.output_name.strip() if c.isalnum() or c in "-_ ")[:70].strip() or "my-video"
    return {"id": output_id, "url": f"/api/download/{output_path.name}",
            "filename": f"{safe_name}.mp4", "size": output_path.stat().st_size}


@app.get("/api/download/{filename}")
def download(filename: str):
    safe_name = Path(filename).name
    if not re.fullmatch(r"[a-f0-9]{32}\.mp4", safe_name):
        raise HTTPException(400, "Invalid output filename.")
    path = (OUTPUTS / safe_name).resolve()
    if not path.exists() or path.parent != OUTPUTS.resolve():
        raise HTTPException(404, "Rendered file not found.")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


class AIRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    mode: str = "script"


@app.post("/api/ai")
async def ai(req: AIRequest):
    base = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
    key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "").strip()
    if not base or not key or not model:
        raise HTTPException(400, "Set AI_BASE_URL, AI_API_KEY and AI_MODEL in the server environment, then restart. Keep keys off the frontend.")
    system = {
        "script": "You are a skilled video scriptwriter. Produce a clear scene-by-scene short video script with narration, visual direction, and on-screen text. Match the user's language.",
        "caption": "Write 5 concise social video captions and relevant hashtags. Match the user's language.",
        "storyboard": "Create a practical scene-by-scene storyboard with shot, action, visual, on-screen text, and sound notes. Match the user's language.",
    }.get(req.mode, "You are a helpful video production assistant. Match the user's language.")
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "system", "content": system},
                      {"role": "user", "content": req.prompt}], "temperature": 0.7},
            )
        if response.status_code >= 400:
            raise HTTPException(502, f"AI provider returned HTTP {response.status_code}. Check server configuration.")
        data = response.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not isinstance(answer, str) or not answer.strip():
            raise HTTPException(502, "AI provider returned an empty response.")
        return {"text": answer.strip(), "provider": "openai-compatible", "model": model}
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "AI provider timed out. Try a shorter prompt.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Could not reach the configured AI provider.") from exc
