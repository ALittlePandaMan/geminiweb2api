from __future__ import annotations

from collections.abc import AsyncGenerator
import json
from pathlib import Path

from gemini_webapi import GeminiClient
from gemini_webapi.constants import Model
from gemini_webapi.types import ModelOutput

from .config import GatewaySettings


class GatewayClientManager:
    def __init__(self, settings: GatewaySettings):
        self._settings = settings
        self._client: GeminiClient | None = None
        self._started = False

    def _load_cookie_values(self) -> dict[str, str]:
        data = json.loads(Path(self._settings.cookie_path).read_text(encoding="utf-8"))
        return self._normalize_cookie_values(data)

    def _normalize_cookie_values(self, data) -> dict[str, str]:
        if isinstance(data, list):
            return self._normalize_cookie_items(data)

        if isinstance(data, dict):
            cookies = data.get("cookies")
            if isinstance(cookies, dict):
                return self._normalize_cookie_items(cookies.items())
            if isinstance(cookies, list):
                return self._normalize_cookie_items(cookies)
            if all(isinstance(key, str) and isinstance(value, str) for key, value in data.items()):
                return dict(data)

        raise ValueError("Unsupported cookies.json format")

    def _normalize_cookie_items(self, items) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for item in items:
            if isinstance(item, tuple) and len(item) == 2:
                name, value = item
                if isinstance(name, str) and isinstance(value, str):
                    normalized[name] = value
                continue

            if not isinstance(item, dict):
                continue

            name = item.get("name")
            value = item.get("value")
            if isinstance(name, str) and isinstance(value, str):
                normalized[name] = value

        if normalized:
            return normalized

        raise ValueError("Unsupported cookies.json format")

    async def startup(self) -> None:
        cookies = self._load_cookie_values()
        secure_1psid = cookies.get("__Secure-1PSID")
        if not secure_1psid:
            raise ValueError("__Secure-1PSID is required in cookies.json")

        secure_1psidts = cookies.get("__Secure-1PSIDTS", "")
        extra_cookies = {
            key: value
            for key, value in cookies.items()
            if key not in {"__Secure-1PSID", "__Secure-1PSIDTS"}
        }

        client = GeminiClient(
            secure_1psid=secure_1psid,
            secure_1psidts=secure_1psidts,
        )
        if extra_cookies:
            client.cookies = extra_cookies
        await client.init(
            timeout=self._settings.request_timeout,
            auto_refresh=True,
            verbose=self._settings.log_level.upper() == "DEBUG",
        )
        self._client = client
        self._started = True

    async def shutdown(self) -> None:
        try:
            if self._client is not None:
                await self._client.close()
        finally:
            self._client = None
            self._started = False

    async def generate(
        self,
        prompt: str,
        model: str,
        files: list[str] | None = None,
    ):
        if self._client is None:
            raise RuntimeError("Gateway client is not started")
        return await self._client.generate_content(
            prompt,
            files=files,
            model=model,
        )

    async def stream_generate(
        self,
        prompt: str,
        model: str,
        files: list[str] | None = None,
    ) -> AsyncGenerator[ModelOutput, None]:
        if self._client is None:
            raise RuntimeError("Gemini client is not initialized")
        async for chunk in self._client.generate_content_stream(
            prompt,
            files=files,
            model=model,
        ):
            yield chunk

    def list_models(self):
        if self._client is not None:
            models = self._client.list_models()
            if models:
                return models

        return [member for member in Model if member is not Model.UNSPECIFIED]

    def health_payload(self) -> dict:
        models = self.list_models() if self._started else []
        return {
            "status": "ok",
            "gemini_initialized": self._started,
            "model_count": len(models),
        }
