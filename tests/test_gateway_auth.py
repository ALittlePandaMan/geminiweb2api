from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from gemini_webapi.openai_server.app import create_app
from gemini_webapi.openai_server.config import GatewaySettings


class _FakeOutput:
    def __init__(self, text: str):
        self.text = text


class _FakeManager:
    def __init__(self) -> None:
        self.started = False

    async def startup(self) -> None:
        self.started = True

    async def shutdown(self) -> None:
        self.started = False

    def health_payload(self) -> dict:
        return {
            "status": "ok",
            "gemini_initialized": self.started,
            "model_count": 1,
        }

    def list_models(self):
        return ["gemini-3-flash"]

    async def generate(self, prompt: str, model: str, files=None):
        return _FakeOutput("ok")


def _make_client(api_key: str | None) -> TestClient:
    settings = GatewaySettings(
        cookie_path=Path("/tmp/cookies.json"),
        api_key=api_key,
        host="127.0.0.1",
        port=9090,
        log_level="INFO",
        request_timeout=300.0,
        default_model="gemini-3-flash",
    )
    app = create_app(settings=settings, manager=_FakeManager())
    return TestClient(app)


def test_models_allows_anonymous_requests_when_api_key_is_not_configured():
    with _make_client(api_key=None) as client:
        response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "gemini-3-flash"


def test_models_rejects_requests_without_bearer_token_when_api_key_is_configured():
    with _make_client(api_key="secret-key") as client:
        response = client.get("/v1/models")

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_models_rejects_requests_with_wrong_bearer_token():
    with _make_client(api_key="secret-key") as client:
        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer wrong-key"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_models_accepts_requests_with_matching_bearer_token():
    with _make_client(api_key="secret-key") as client:
        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer secret-key"},
        )

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "gemini-3-flash"


def test_chat_completions_requires_api_key_when_configured():
    with _make_client(api_key="secret-key") as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-3-flash",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_health_remains_public_even_when_api_key_is_configured():
    with _make_client(api_key="secret-key") as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
