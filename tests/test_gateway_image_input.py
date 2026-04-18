from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from gemini_webapi.openai_server.app import create_app
import gemini_webapi.openai_server.adapter as adapter_module
from gemini_webapi.openai_server.config import GatewaySettings


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8B"
    "g0cAAAAASUVORK5CYII="
)


class _FakeOutput:
    def __init__(self, text: str):
        self.text = text


class _FakeManager:
    def __init__(self) -> None:
        self.started = False
        self.last_prompt: str | None = None
        self.last_model: str | None = None
        self.last_files_count: int = 0
        self.files_exist_during_call: bool = False

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
        self.last_prompt = prompt
        self.last_model = model
        files = files or []
        self.last_files_count = len(files)
        self.files_exist_during_call = all(Path(file).exists() for file in files)
        return _FakeOutput("ok")


def _make_client(manager: _FakeManager) -> TestClient:
    settings = GatewaySettings(
        cookie_path=Path("/tmp/cookies.json"),
        api_key=None,
        host="127.0.0.1",
        port=9090,
        log_level="INFO",
        request_timeout=300.0,
        default_model="gemini-3-flash",
    )
    app = create_app(settings=settings, manager=manager)
    return TestClient(app)


def test_chat_completions_accepts_data_url_image_input():
    manager = _FakeManager()

    with _make_client(manager) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-3-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image."},
                            {"type": "image_url", "image_url": {"url": PNG_DATA_URL}},
                        ],
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert manager.last_model == "gemini-3-flash"
    assert manager.last_files_count == 1
    assert manager.files_exist_during_call is True
    assert "[image attached:" in (manager.last_prompt or "")


def test_chat_completions_accepts_image_only_message():
    manager = _FakeManager()

    with _make_client(manager) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-3-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": PNG_DATA_URL}},
                        ],
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert manager.last_files_count == 1
    assert manager.files_exist_during_call is True


def test_chat_completions_accepts_remote_image_url(monkeypatch):
    manager = _FakeManager()

    def fake_download_remote_url(url: str):
        assert url == "https://example.com/test.png"
        return b"fake-image-bytes", "image/png"

    monkeypatch.setattr(adapter_module, "_download_remote_url", fake_download_remote_url)

    with _make_client(manager) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-3-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image."},
                            {
                                "type": "image_url",
                                "image_url": {"url": "https://example.com/test.png"},
                            },
                        ],
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert manager.last_files_count == 1
    assert manager.files_exist_during_call is True
