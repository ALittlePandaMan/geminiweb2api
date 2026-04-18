from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
import mimetypes
import tempfile
from time import time
from urllib.parse import unquote_to_bytes, urlparse
from urllib.request import urlopen

import orjson

from .schemas import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionResponse,
    CompletionUsage,
    ChatMessage,
    MessageImageUrlPart,
    MessageTextPart,
)

@dataclass
class PreparedPrompt:
    prompt_text: str
    files: list[Path]
    cleanup_paths: list[Path]

    def cleanup(self) -> None:
        for path in self.cleanup_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue


def _suffix_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return ""
    return mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) or ""


def _suffix_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix
    return suffix if suffix else ""


def _write_temp_file(data: bytes, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(
        prefix="gemini_gateway_",
        suffix=suffix or ".bin",
        delete=False,
    ) as tmp:
        tmp.write(data)
        return Path(tmp.name)


def _decode_data_url(url: str) -> tuple[bytes, str | None]:
    header, sep, payload = url.partition(",")
    if not sep or not header.startswith("data:"):
        raise ValueError("Unsupported image_url data URL")

    meta = header[5:]
    content_type = meta.split(";", 1)[0] or "application/octet-stream"

    if ";base64" in meta:
        data = base64.b64decode(payload)
    else:
        data = unquote_to_bytes(payload)

    return data, content_type


def _download_remote_url(url: str) -> tuple[bytes, str | None]:
    with urlopen(url, timeout=30) as response:
        content_type = response.headers.get_content_type()
        return response.read(), content_type


async def _materialize_image_url(url: str) -> Path:
    if url.startswith("data:"):
        data, content_type = _decode_data_url(url)
        suffix = _suffix_from_content_type(content_type)
        return _write_temp_file(data, suffix)

    if url.startswith("http://") or url.startswith("https://"):
        data, content_type = await asyncio.to_thread(_download_remote_url, url)
        suffix = _suffix_from_content_type(content_type) or _suffix_from_url(url)
        return _write_temp_file(data, suffix)

    raise ValueError("Unsupported image_url scheme")


async def _message_text(message: ChatMessage, cleanup_paths: list[Path]) -> tuple[str, list[Path]]:
    content = message.content
    if content is None:
        return "", []
    if isinstance(content, str):
        return content, []

    fragments: list[str] = []
    files: list[Path] = []
    for part in content:
        if isinstance(part, MessageTextPart) and part.text.strip():
            fragments.append(part.text)
        elif isinstance(part, MessageImageUrlPart):
            image_path = await _materialize_image_url(part.image_url.url)
            cleanup_paths.append(image_path)
            files.append(image_path)
            fragments.append(f"[image attached: {image_path.name}]")

    return "\n".join(fragments), files


async def render_messages_to_prompt(messages: list[ChatMessage]) -> tuple[str, list[Path], list[Path]]:
    system_texts: list[str] = []
    conversation_turns: list[str] = []
    files: list[Path] = []
    cleanup_paths: list[Path] = []
    for message in messages:
        text, message_files = await _message_text(message, cleanup_paths)
        files.extend(message_files)
        if message.role == "system":
            system_texts.append(text)
        else:
            conversation_turns.append(f"[{message.role}]\n{text}")

    system_block = "\n\n".join(system_texts) if system_texts else "None"
    rendered_messages: list[str] = []
    rendered_messages.append(f"System:\n{system_block}")
    rendered_messages.append("Conversation:")
    rendered_messages.extend(conversation_turns)
    rendered_messages.append("Respond as the assistant to the final user message.")
    return "\n\n".join(rendered_messages), files, cleanup_paths


async def prepare_messages_for_gemini(messages: list[ChatMessage]) -> PreparedPrompt:
    prompt_text, files, cleanup_paths = await render_messages_to_prompt(messages)
    return PreparedPrompt(
        prompt_text=prompt_text,
        files=files,
        cleanup_paths=cleanup_paths,
    )


def _estimate_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)


def build_chat_completion_response(
    request_id: str,
    model: str,
    content: str,
    prompt_text: str,
) -> dict[str, object]:
    completion_tokens = _estimate_tokens(content)
    prompt_tokens = _estimate_tokens(prompt_text)
    response = ChatCompletionResponse(
        id=request_id,
        created=int(time()),
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(content=content),
                finish_reason="stop",
            )
        ],
        usage=CompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
    return response.model_dump(mode="json")


def build_role_chunk(
    request_id: str,
    model: str,
    *,
    created: int | None = None,
) -> dict[str, object]:
    chunk = ChatCompletionChunk(
        id=request_id,
        created=int(time()) if created is None else created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(role="assistant"),
                finish_reason=None,
            )
        ],
    )
    return chunk.model_dump(mode="json", exclude_none=True)


def build_delta_chunk(
    request_id: str,
    model: str,
    content: str,
    *,
    created: int | None = None,
) -> dict[str, object]:
    chunk = ChatCompletionChunk(
        id=request_id,
        created=int(time()) if created is None else created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(content=content),
                finish_reason=None,
            )
        ],
    )
    return chunk.model_dump(mode="json", exclude_none=True)


def build_stop_chunk(
    request_id: str,
    model: str,
    *,
    created: int | None = None,
) -> dict[str, object]:
    chunk = ChatCompletionChunk(
        id=request_id,
        created=int(time()) if created is None else created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(),
                finish_reason="stop",
            )
        ],
    )
    return chunk.model_dump(mode="json", exclude_none=True)


def encode_sse(payload: object) -> bytes:
    if isinstance(payload, bytes):
        body = payload
    elif isinstance(payload, str):
        body = payload.encode("utf-8")
    else:
        body = orjson.dumps(payload)
    return b"data: " + body + b"\n\n"


async def iter_chat_completion_sse(
    request_id: str,
    model: str,
    stream: AsyncGenerator,
) -> AsyncGenerator[bytes, None]:
    created = int(time())
    yield encode_sse(build_role_chunk(request_id, model, created=created))
    async for chunk in stream:
        if getattr(chunk, "text_delta", ""):
            yield encode_sse(
                build_delta_chunk(
                    request_id,
                    model,
                    chunk.text_delta,
                    created=created,
                )
            )
    yield encode_sse(build_stop_chunk(request_id, model, created=created))
    yield b"data: [DONE]\n\n"
