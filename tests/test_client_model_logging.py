from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gemini_webapi.constants import Model
import gemini_webapi.client as client_module


def test_log_model_request_debug_writes_resolved_model_name_and_header(monkeypatch):
    messages: list[str] = []

    def fake_debug(message: str) -> None:
        messages.append(message)

    monkeypatch.setattr(client_module.logger, "debug", fake_debug)

    client_module._log_model_request_debug(Model.BASIC_PRO)

    assert len(messages) == 1
    assert "gemini-3-pro" in messages[0]
    assert "model_header" in messages[0]
    assert "x-goog-ext-525001261-jspb" in messages[0]
