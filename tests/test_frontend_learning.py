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
    assert "GitHub Pages is frontend-only" in html
    assert "FFmpeg rendering need a running FastAPI backend" in html
