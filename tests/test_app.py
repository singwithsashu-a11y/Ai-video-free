from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_homepage_serves_studio():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_health_endpoint_reports_app_alive():
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "ffmpeg_available" in payload


def test_cloud_ai_endpoint_explains_missing_server_configuration(monkeypatch):
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    response = client.post("/api/ai", json={"prompt": "Write a short video script", "mode": "script"})
    assert response.status_code == 400
    assert "AI_BASE_URL" in response.json()["detail"]


def test_offline_ai_endpoint_works_without_api_key():
    response = client.post(
        "/api/local-ai",
        json={"prompt": "A sad Hinglish music reel", "mode": "script", "provider": "offline"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "offline-template"
    assert "A sad Hinglish music reel" in payload["text"]


def test_local_ai_status_is_nonfatal_when_ollama_is_missing():
    response = client.get("/api/local-ai/status")
    assert response.status_code == 200
    assert "available" in response.json()


def test_mj_ai_status_endpoint_reports_available_providers(monkeypatch):
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    response = client.get("/api/mj-ai/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "MJ AI"
    assert "local" in payload
    assert payload["openai_compatible_configured"] is False


def test_mj_ai_chat_requires_provider_configuration(monkeypatch):
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    response = client.post("/api/mj-ai/chat", json={
        "provider": "openai-compatible",
        "messages": [{"role": "user", "content": "Hello MJ AI"}]
    })
    assert response.status_code == 400
    assert "AI_BASE_URL" in response.json()["detail"]


def test_media_library_endpoint_returns_list():
    response = client.get("/api/media")
    assert response.status_code == 200
    assert isinstance(response.json()["files"], list)


def test_projects_can_be_saved_loaded_updated_and_deleted():
    created = client.post("/api/projects", json={
        "name": "Test project",
        "data": {"files": ["a" * 32], "aspect": "9:16", "burn_subtitles": False}
    })
    assert created.status_code == 200
    project = created.json()
    project_id = project["id"]
    try:
        fetched = client.get(f"/api/projects/{project_id}")
        assert fetched.status_code == 200
        assert fetched.json()["data"]["aspect"] == "9:16"

        updated = client.put(f"/api/projects/{project_id}", json={
            "name": "Updated project", "data": {"aspect": "16:9"}
        })
        assert updated.status_code == 200
        assert updated.json()["name"] == "Updated project"
        assert client.get("/api/projects").status_code == 200
    finally:
        deleted = client.delete(f"/api/projects/{project_id}")
        assert deleted.status_code == 200
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_render_rejects_invalid_uploaded_file_id():
    response = client.post("/api/render", json={"files": ["../../etc/passwd"]})
    assert response.status_code == 400


def test_adapter_provider_reports_missing_adapter_cleanly(monkeypatch, tmp_path):
    monkeypatch.setenv("MJ_AI_ADAPTER_PATH", str(tmp_path / "not-installed"))
    response = client.get("/api/mj-ai/status")
    assert response.status_code == 200
    assert response.json()["adapter"]["configured"] is False
