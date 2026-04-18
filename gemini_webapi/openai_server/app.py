from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from gemini_webapi.exceptions import ModelInvalid

from .adapter import (
    build_chat_completion_response,
    iter_chat_completion_sse,
    prepare_messages_for_gemini,
)
from .client_manager import GatewayClientManager
from .config import GatewaySettings
from .errors import (
    invalid_api_key_exception,
    map_gemini_exception,
    register_exception_handlers,
)
from .schemas import (
    ChatCompletionRequest,
    ModelCard,
    ModelListResponse,
)


async def _prepend_first_chunk(first_chunk: object, stream: AsyncGenerator) -> AsyncGenerator:
    yield first_chunk
    async for chunk in stream:
        yield chunk


async def _empty_stream() -> AsyncGenerator:
    if False:
        yield None


async def _stream_with_cleanup(stream: AsyncGenerator, cleanup) -> AsyncGenerator:
    try:
        async for chunk in stream:
            yield chunk
    finally:
        cleanup()


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _authorize_request(request: Request) -> None:
    settings = getattr(request.app.state, "settings", None)
    if settings is None or not settings.api_key_required:
        return

    token = _extract_bearer_token(request.headers.get("Authorization"))
    if token != settings.api_key:
        raise invalid_api_key_exception()


def _model_name(model: object) -> str:
    return getattr(model, "model_name", str(model))


def _model_is_available(model: object) -> bool:
    return getattr(model, "is_available", True)


def _public_models(models: list[object]) -> list[object]:
    return [model for model in models if _model_is_available(model)]


def _ensure_model_is_available(manager: GatewayClientManager, model_name: str) -> None:
    models = manager.list_models()
    if not models:
        return

    for model in models:
        aliases = {
            _model_name(model),
            getattr(model, "display_name", None),
        }
        if model_name in aliases and not _model_is_available(model):
            raise ModelInvalid(
                f"Model '{model_name}' is not available for the current Gemini session. "
                "Refresh cookies or use one of the models returned by /v1/models."
            )


def create_app(
    *,
    settings: GatewaySettings | None = None,
    manager: GatewayClientManager | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved_settings = settings
        if resolved_settings is None:
            resolved_settings = GatewaySettings.from_env()

        resolved_manager = manager
        if resolved_manager is None:
            resolved_manager = GatewayClientManager(resolved_settings)

        app.state.settings = resolved_settings
        app.state.client_manager = resolved_manager
        await resolved_manager.startup()
        try:
            yield
        finally:
            await resolved_manager.shutdown()

    app = FastAPI(
        title="Gemini OpenAI-Compatible Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.state.settings = settings
    app.state.client_manager = manager

    @app.get("/health")
    async def health(request: Request) -> dict:
        return request.app.state.client_manager.health_payload()

    @app.get("/v1/models")
    async def list_models(request: Request) -> dict:
        _authorize_request(request)
        cards = []
        models = request.app.state.client_manager.list_models()
        for model in _public_models(models):
            model_name = _model_name(model)
            cards.append(ModelCard(id=model_name))
        return ModelListResponse(data=cards).model_dump()

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request, payload: ChatCompletionRequest) -> dict:
        prepared = None
        try:
            _authorize_request(request)
            settings = request.app.state.settings
            default_model = getattr(settings, "default_model", None) if settings is not None else None
            model = payload.model or default_model
            if not model:
                raise ValueError("model is required")

            _ensure_model_is_available(request.app.state.client_manager, model)
            prepared = await prepare_messages_for_gemini(payload.messages)
            prompt_text = prepared.prompt_text
            request_id = f"chatcmpl-{uuid4().hex}"
            manager = request.app.state.client_manager
            generate_kwargs = {"model": model, "files": prepared.files or None}

            if payload.stream:
                stream = manager.stream_generate(prompt_text, **generate_kwargs)
                try:
                    first_chunk = await anext(stream)
                except StopAsyncIteration:
                    return StreamingResponse(
                        _stream_with_cleanup(
                            iter_chat_completion_sse(request_id, model, _empty_stream()),
                            prepared.cleanup,
                        ),
                        media_type="text/event-stream",
                    )
                except Exception as exc:
                    prepared.cleanup()
                    raise map_gemini_exception(exc) from exc
                return StreamingResponse(
                    _stream_with_cleanup(
                        iter_chat_completion_sse(
                            request_id,
                            model,
                            _prepend_first_chunk(first_chunk, stream),
                        ),
                        prepared.cleanup,
                    ),
                    media_type="text/event-stream",
                )

            output = await manager.generate(prompt_text, **generate_kwargs)
            if not hasattr(output, "text"):
                raise TypeError("Gemini output is missing text")
            content = output.text
            return build_chat_completion_response(
                request_id=request_id,
                model=model,
                content=content,
                prompt_text=prompt_text,
            )
        except Exception as exc:
            raise map_gemini_exception(exc) from exc
        finally:
            if prepared is not None and not payload.stream:
                prepared.cleanup()

    return app


app = create_app()
