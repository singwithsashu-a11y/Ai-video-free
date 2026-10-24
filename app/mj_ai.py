"""MJ AI: multi-provider chat API. Provider keys stay on the server.

The optional adapter provider loads a PEFT LoRA adapter on top of its matching
base model. Set MJ_AI_ADAPTER_PATH and MJ_AI_BASE_MODEL on the backend.
"""
import os
import threading
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/mj-ai", tags=["MJ AI"])
Role = Literal["system", "user", "assistant"]

class Message(BaseModel):
    role: Role
    content: str = Field(min_length=1, max_length=24000)

class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)
    provider: Literal["ollama", "openai-compatible", "adapter"] = "ollama"
    model: str | None = Field(default=None, max_length=200)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=8192)

MJ_SYSTEM = (
    "You are MJ AI, a helpful multilingual assistant. Be honest about uncertainty, "
    "follow the user's language, explain reasoning clearly without claiming access to "
    "private model weights or tools you do not have, and help with writing, learning, "
    "coding, research planning, and creative work. Respect applicable safety and law."
)

_adapter_lock = threading.Lock()
_adapter_model = None
_adapter_tokenizer = None
_adapter_device = None

def _adapter_settings():
    adapter_path = Path(os.getenv("MJ_AI_ADAPTER_PATH", "models/mj-ai-lora")).expanduser()
    base_model = os.getenv("MJ_AI_BASE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct").strip()
    return adapter_path, base_model

def _load_adapter():
    """Load the adapter once, lazily, so normal app startup needs no ML packages."""
    global _adapter_model, _adapter_tokenizer, _adapter_device
    if _adapter_model is not None:
        return _adapter_model, _adapter_tokenizer, _adapter_device
    with _adapter_lock:
        if _adapter_model is not None:
            return _adapter_model, _adapter_tokenizer, _adapter_device
        adapter_path, base_model = _adapter_settings()
        if not (adapter_path / "adapter_config.json").is_file():
            raise RuntimeError(
                f"Adapter config not found at {adapter_path}. Copy the extracted adapter there "
                "or set MJ_AI_ADAPTER_PATH to its folder."
            )
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Adapter inference dependencies are missing. Install training/requirements-inference.txt."
            ) from exc
        tokenizer = AutoTokenizer.from_pretrained(base_model)
        model = AutoModelForCausalLM.from_pretrained(base_model)
        model = PeftModel.from_pretrained(model, str(adapter_path))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        model.eval()
        _adapter_model, _adapter_tokenizer, _adapter_device = model, tokenizer, device
    return _adapter_model, _adapter_tokenizer, _adapter_device

def _generate_adapter(messages, temperature, max_tokens):
    import torch
    model, tokenizer, device = _load_adapter()
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=temperature > 0,
            temperature=max(temperature, 0.01),
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

@router.get("/status")
async def status():
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b").strip()
    cloud_ready = all(os.getenv(k, "").strip() for k in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL"))
    adapter_path, adapter_base = _adapter_settings()
    adapter_ready = (adapter_path / "adapter_config.json").is_file()
    local = {"available": False, "models": [], "default_model": ollama_model}
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(f"{ollama_url}/api/tags")
        response.raise_for_status()
        local["available"] = True
        local["models"] = [m.get("name", "") for m in response.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        pass
    return {
        "name": "MJ AI",
        "local": local,
        "openai_compatible_configured": cloud_ready,
        "adapter": {
            "configured": adapter_ready,
            "base_model": adapter_base,
            "adapter_path": str(adapter_path),
            "provider": "adapter",
            "note": "Requires optional Transformers/PEFT dependencies and enough RAM/VRAM."
        },
        "note": "No model is bundled with this app. Connect a local model, install the adapter, or configure a server-side provider."
    }

@router.post("/chat")
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content.strip()} for m in req.messages]
    if not any(m["role"] == "user" for m in messages):
        raise HTTPException(422, "At least one user message is required.")
    if not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": MJ_SYSTEM})

    if req.provider == "adapter":
        try:
            answer = await run_in_threadpool(
                _generate_adapter, messages, req.temperature, req.max_tokens
            )
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception:
            raise HTTPException(502, "MJ AI adapter inference failed. Check the base model, adapter compatibility, and server logs.")
        if not answer:
            raise HTTPException(502, "The adapter model returned an empty response.")
        _, base_model = _adapter_settings()
        return {"name": "MJ AI", "provider": "adapter", "model": base_model, "text": answer}

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
