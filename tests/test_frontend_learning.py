from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_static_frontend_has_conversation_and_learning_controls():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="chatMessages"' in html
    assert 'id="chatInput"' in html
    assert 'id="exportLearning"' in html
    assert 'id="clearChatMemory"' in html
    assert "CHAT_KEY='mj-ai-chat-memory-v1'" in js
    assert "LEARNING_KEY='mj-ai-approved-examples-v1'" in js
    assert "approveExample(index)" in js


def test_offline_generation_does_not_require_backend_api():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "function offlineGenerate(prompt,mode)" in js
    assert "if(provider==='offline')" in js
    assert "data={text:offlineGenerate(prompt,mode),provider:'offline-template'}" in js


def test_static_hosting_message_explains_backend_required_for_rendering():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "GitHub Pages hosts only this interface" in html
    assert "FFmpeg rendering need your deployed FastAPI backend" in html


def test_chat_first_workspace_has_tabs_and_photo_attachment():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert 'data-view-target="chat"' in html
    assert 'data-view-target="create"' in html
    assert 'id="chatImageInput"' in html
    assert 'id="chatImagePreview"' in html
    assert "compressChatImage(file)" in js
    assert "image_data_url" in js


def test_browser_model_uses_smaller_generation_budget():
    worker = (ROOT / "static" / "browser-ai-worker.js").read_text(encoding="utf-8")
    assert "max_new_tokens: 192" in worker


def test_backend_ai_requires_a_configured_backend_url():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "Backend URL is not connected" in js
    assert "Cloud AI configured" in js


def test_render_blueprint_has_health_check_and_server_start_command():
    config = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "uvicorn app.main:app --host 0.0.0.0 --port $PORT" in config
    assert "healthCheckPath: /api/health" in config
    assert "AI_API_KEY" in config



def test_provider_switching_chat_api_is_registered():
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    chat_api = (ROOT / "app" / "chat_api.py").read_text(encoding="utf-8")
    assert "app.include_router(chat_api_router)" in main
    assert '@router.post("/chat")' in chat_api
    assert '@router.get("/providers")' in chat_api
    assert '"ollama"' in chat_api
    assert '"offline"' in chat_api
    assert "AI_BASE_URL" in chat_api
    assert "AI_API_KEY" in chat_api
    assert "AI_MODEL" in chat_api
    assert "Never echo provider response bodies" in chat_api
