from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GatewaySettings:
    cookie_path: Path
    api_key: str | None = None
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    request_timeout: float = 300.0
    default_model: str | None = None

    @property
    def api_key_required(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_env(cls) -> "GatewaySettings":
        cookie_path = os.getenv("GEMINI_GATEWAY_COOKIE_PATH")
        if not cookie_path:
            raise ValueError("GEMINI_GATEWAY_COOKIE_PATH is required")

        return cls(
            api_key=os.getenv("GEMINI_GATEWAY_API_KEY") or None,
            cookie_path=Path(cookie_path),
            host=os.getenv("GEMINI_GATEWAY_HOST", "127.0.0.1"),
            port=int(os.getenv("GEMINI_GATEWAY_PORT", "8000")),
            log_level=os.getenv("GEMINI_GATEWAY_LOG_LEVEL", "INFO"),
            request_timeout=float(os.getenv("GEMINI_GATEWAY_REQUEST_TIMEOUT", "300.0")),
            default_model=os.getenv("GEMINI_GATEWAY_MODEL_DEFAULT") or None,
        )
