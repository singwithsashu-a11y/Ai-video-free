"""MJ AI: multi-provider chat API. Provider keys stay on the server."""
import os
from typing import Literal
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/mj-ai", tags=["MJ AI"])
Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str = Field(min_length=1, max_length=24000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)
    provider: Literal["ollama", "openai-compatible"] = "ollama"
    model: str | None = Field(default=None, max_length=200)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=8192)


MJ_SYSTEM = (
    "You are MJ AI, a helpful multilingual assistant. Be honest about uncertainty, "
    "follow the user's language, explain reasoning clearly without claiming access to "
    "private model weights or tools you do not have, and help with writing, learning, "
    "coding, research planning, and creative work. Respect applicable safety and law."
)


@router.get("/status")
async def status():
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b").strip()
    cloud_ready = all(os.getenv(k, "").strip() for k in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL"))
    local = {"available": False, "models": [], "default_model": ollama_model}
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(f"{ollama_url}/api/tags")
        response.raise_for_status()
        local["available"] = True
        local["models"] = [m.get("name", "") for m in response.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        pass
    return {"name": "MJ AI", "local": local, "openai_compatible_configured": cloud_ready,
            "note": "No model is bundled with this app. Connect a local model or configure a server-side provider."}


@router.post("/chat")
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content.strip()} for m in req.messages]
    if not any(m["role"] == "user" for m in messages):
        raise HTTPException(422, "At least one user message is required.")
    if not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": MJ_SYSTEM})

    if req.provider == "ollama":
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
        model = (req.model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b")).strip()
        if not model:
            raise HTTPException(400, "Choose an installed Ollama model.")
        url = f"{base}/api/chat"
        payload = {"model": model, "messages": messages, "stream": False,
                   "options": {"temperature": req.temperature, "num_predict": req.max_tokens}}
        headers = {}
    else:
        base = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
        key = os.getenv("AI_API_KEY", "").strip()
        model = (req.model or os.getenv("AI_MODEL", "")).strip()
        if not base or not key or not model:
            raise HTTPException(400, "OpenAI-compatible provider is not configured. Set AI_BASE_URL, AI_API_KEY and AI_MODEL on the server; never put API keys in browser code.")
        url = f"{base}/chat/completions"
        payload = {"model": model, "messages": messages, "temperature": req.temperature, "max_tokens": req.max_tokens}
        headers = {"Authorization": f"Bearer {key}"}

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            # Do not return provider response bodies because they may contain internal details.
            raise HTTPException(502, f"{req.provider} provider returned HTTP {response.status_code}. Check model name and server configuration.")
        data = response.json()
        answer = (data.get("message", {}).get("content", "") if req.provider == "ollama"
                  else data.get("choices", [{}])[0].get("message", {}).get("content", ""))
        if not isinstance(answer, str) or not answer.strip():
            raise HTTPException(502, "The model returned an empty response.")
        return {"name": "MJ AI", "provider": req.provider, "model": model, "text": answer.strip()}
    except httpx.TimeoutException:
        raise HTTPException(504, "The model took too long to respond. Try a smaller model or shorter prompt.")
    except httpx.RequestError:
        raise HTTPException(503, "Could not reach the AI provider. Check that the backend can access the configured model service.")
