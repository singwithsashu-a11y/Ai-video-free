"""Provider-switching chat API for MJ AI Studio.

The server never exposes provider API keys to the browser. Cloud/custom providers
must implement the OpenAI-compatible /chat/completions contract.
"""
import os
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.local_ai import offline_generate

router = APIRouter(prefix="/api", tags=["chat"])

Provider = Literal["cloud", "custom", "openai-compatible", "ollama", "offline"]
Mode = Literal["chat", "script", "storyboard", "caption", "ad_hook", "editing_idea", "strategy"]

SYSTEM_PROMPTS = {
    "chat": "You are MJ AI Studio, a helpful multilingual creative assistant. Match the user's language, including natural Hindi/Hinglish. Use recent conversation context and answer the latest request directly. Never claim to have rendered or generated media unless a tool actually did so.",
    "script": "You are a professional short-video scriptwriter. Match the user's language. Provide a strong hook, duration, scene-by-scene visuals, narration/dialogue, on-screen text, sound, transitions, and CTA. Be specific and avoid filler.",
    "storyboard": "You are a professional storyboard artist. Match the user's language. Create numbered scenes with duration, shot/framing, action, visual prompt, narration, on-screen text, sound, and transition. Preserve character/location continuity.",
    "caption": "Write five distinct social-video captions, one strong hook, and relevant hashtags. Match the user's language.",
    "ad_hook": "Create five original short-form ad hooks, then a concise scene-by-scene ad script and CTA. Match the user's language.",
    "editing_idea": "Act as a practical video editor. Give a timestamped edit plan with cuts, transitions, captions, sound design, pacing, and effects that can be made with common editing tools. Do not claim to edit a file.",
    "strategy": "Act as a short-form content strategist. Give a practical audience, angle, hook, format, retention, posting, and measurement plan. Match the user's language.",
}

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=16000)

class ChatRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=12000)
    messages: list[ChatMessage] = Field(default_factory=list, max_length=30)
    provider: Provider = "cloud"
    model: str | None = Field(default=None, max_length=200)
    mode: Mode = "chat"
    temperature: float = Field(default=0.65, ge=0, le=2)
    max_tokens: int = Field(default=768, ge=32, le=4096)

def _messages(req: ChatRequest) -> list[dict]:
    incoming = [m.model_dump() for m in req.messages]
    if req.prompt and req.prompt.strip():
        incoming.append({"role": "user", "content": req.prompt.strip()})
    if not incoming or not any(m["role"] == "user" for m in incoming):
        raise HTTPException(422, "Send a prompt or at least one user message.")
    system = SYSTEM_PROMPTS[req.mode]
    # Keep a single trusted system instruction at the front.
    incoming = [m for m in incoming if m["role"] != "system"]
    return [{"role": "system", "content": system}, *incoming[-24:]]

@router.get("/providers")
async def providers():
    """Report configured options without exposing secrets."""
    cloud_ready = all(os.getenv(k, "").strip() for k in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL"))
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    ollama_ready = False
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{ollama_base}/api/tags")
        ollama_ready = response.is_success
    except httpx.HTTPError:
        pass
    return {"providers": [
        {"id": "cloud", "label": "Cloud / custom OpenAI-compatible API", "configured": cloud_ready,
         "model": os.getenv("AI_MODEL", "") if cloud_ready else ""},
        {"id": "ollama", "label": "Ollama on backend host", "configured": ollama_ready,
         "model": os.getenv("OLLAMA_MODEL", "qwen2.5:3b")},
        {"id": "offline", "label": "Offline template (no language model)", "configured": True, "model": "template"},
    ]}

@router.post("/chat")
async def chat(req: ChatRequest):
    messages = _messages(req)
    if req.provider == "offline":
        latest = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        # Templates are intentionally labeled as templates, not AI inference.
        return {"text": offline_generate(latest, req.mode if req.mode in {"script", "storyboard", "caption"} else "script"),
                "provider": "offline-template", "model": "template"}

    if req.provider == "ollama":
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
        model = (req.model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b")).strip()
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(f"{base}/api/chat", json={
                    "model": model, "stream": False, "messages": messages,
                    "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
                })
            if response.status_code >= 400:
                raise HTTPException(502, f"Ollama returned HTTP {response.status_code}. Check model name and server logs.")
            answer = response.json().get("message", {}).get("content", "")
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Ollama timed out. Try a shorter prompt or smaller model.") from exc
        except httpx.RequestError as exc:
            raise HTTPException(503, "Ollama is not reachable from the backend host. A phone's localhost is not accessible to the server.") from exc
        if not isinstance(answer, str) or not answer.strip():
            raise HTTPException(502, "Ollama returned an empty response.")
        return {"text": answer.strip(), "provider": "ollama", "model": model}

    base = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
    key = os.getenv("AI_API_KEY", "").strip()
    configured_model = os.getenv("AI_MODEL", "").strip()
    model = (req.model or configured_model).strip()
    if not base or not key or not model:
        raise HTTPException(503, "Cloud/custom AI is not configured. Set AI_BASE_URL, AI_API_KEY and AI_MODEL on the backend.")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": req.temperature, "max_tokens": req.max_tokens},
            )
        if response.status_code >= 400:
            # Never echo provider response bodies; they can contain operational details.
            raise HTTPException(502, f"Configured AI provider returned HTTP {response.status_code}. Check model and server configuration.")
        data = response.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "AI provider timed out. Try a shorter prompt.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Could not reach the configured AI provider.") from exc
    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(502, "AI provider returned an empty response.")
    return {"text": answer.strip(), "provider": "openai-compatible", "model": model}
