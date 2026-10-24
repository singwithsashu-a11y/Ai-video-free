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


def test_ai_endpoint_explains_missing_server_configuration(monkeypatch):
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    response = client.post("/api/ai", json={"prompt": "Write a short video script", "mode": "script"})
    assert response.status_code == 400
    assert "AI_BASE_URL" in response.json()["detail"]
