from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
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
    def __init__(self, models) -> None:
        self.models = models
        self.started = False
        self.generate_calls: list[tuple[str, str]] = []

    async def startup(self) -> None:
        self.started = True

    async def shutdown(self) -> None:
        self.started = False

    def health_payload(self) -> dict:
        return {
            "status": "ok",
            "gemini_initialized": self.started,
            "model_count": len(self.models),
        }

    def list_models(self):
        return self.models

    async def generate(self, prompt: str, model: str, files=None):
        self.generate_calls.append((prompt, model))
        return _FakeOutput("ok")


def _make_client(manager: _FakeManager, default_model: str | None = "gemini-3-flash") -> TestClient:
    settings = GatewaySettings(
        cookie_path=Path("/tmp/cookies.json"),
        api_key=None,
        host="127.0.0.1",
        port=9090,
        log_level="INFO",
        request_timeout=300.0,
        default_model=default_model,
    )
    app = create_app(settings=settings, manager=manager)
    return TestClient(app)


def test_models_endpoint_hides_models_marked_unavailable():
    manager = _FakeManager(
        [
            SimpleNamespace(model_name="gemini-3-flash", display_name="Fast", is_available=True),
            SimpleNamespace(model_name="gemini-3-pro", display_name="Pro", is_available=False),
        ]
    )

    with _make_client(manager) as client:
        response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "id": "gemini-3-flash",
            "object": "model",
            "created": 0,
            "owned_by": "gemini-webapi",
        }
    ]


def test_chat_completions_rejects_explicitly_unavailable_model():
    manager = _FakeManager(
        [
            SimpleNamespace(model_name="gemini-3-flash", display_name="Fast", is_available=True),
            SimpleNamespace(model_name="gemini-3-pro", display_name="Pro", is_available=False),
        ]
    )

    with _make_client(manager) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-3-pro",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_model"
    assert manager.generate_calls == []


def test_chat_completions_rejects_unavailable_default_model():
    manager = _FakeManager(
        [
            SimpleNamespace(model_name="gemini-3-flash", display_name="Fast", is_available=True),
            SimpleNamespace(model_name="gemini-3-pro", display_name="Pro", is_available=False),
        ]
    )

    with _make_client(manager, default_model="gemini-3-pro") as client:
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_model"
    assert manager.generate_calls == []


def test_chat_completions_allows_available_model():
    manager = _FakeManager(
        [
            SimpleNamespace(model_name="gemini-3-flash", display_name="Fast", is_available=True),
            SimpleNamespace(model_name="gemini-3-pro", display_name="Pro", is_available=False),
        ]
    )

    with _make_client(manager) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-3-flash",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 200
    assert manager.generate_calls == [("System:\nNone\n\nConversation:\n\n[user]\nhello\n\nRespond as the assistant to the final user message.", "gemini-3-flash")]
