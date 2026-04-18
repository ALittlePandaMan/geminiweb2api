from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "gemini-webapi"


class ModelListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object: str = "list"
    data: list[ModelCard]


class MessageTextPart(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["text"]
    text: str


class MessageImageUrl(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str


class MessageImageUrlPart(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["image_url"]
    image_url: MessageImageUrl


MessageContentPart = Annotated[
    MessageTextPart | MessageImageUrlPart,
    Field(discriminator="type"),
]


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["system", "user", "assistant"]
    content: str | list[MessageContentPart]

    @model_validator(mode="after")
    def validate_content(self) -> "ChatMessage":
        if isinstance(self.content, str):
            if self.content.strip() == "":
                raise ValueError("content must not be empty")
            return self

        has_text = any(
            isinstance(part, MessageTextPart) and part.text.strip() != ""
            for part in self.content
        )
        has_image = any(isinstance(part, MessageImageUrlPart) for part in self.content)
        if not self.content or not (has_text or has_image):
            raise ValueError("content must not be empty")
        return self


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str | None = None
    messages: list[ChatMessage]
    n: int = 1
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    seed: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    user: str | None = None
    metadata: dict[str, str] | None = None
    tools: list[dict[str, object]] | None = None
    tool_choice: str | dict[str, object] | None = None
    function_call: str | dict[str, object] | None = None
    functions: list[dict[str, object]] | None = None
    response_format: dict[str, object] | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    modalities: list[str] | None = None
    audio: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_supported_fields(self) -> "ChatCompletionRequest":
        # Common OpenAI-compatible clients send control fields we do not implement.
        # Accept them here and ignore them later instead of failing provider checks.
        if self.n != 1:
            raise ValueError("n must be 1")
        if not self.messages:
            raise ValueError("messages must not be empty")
        return self


class ChatCompletionMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    message: ChatCompletionMessage
    finish_reason: Literal["stop"] | None = None
    logprobs: None = None


class CompletionUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    object: str = "chat.completion"
    created: int = 0
    model: str
    choices: list[ChatCompletionChoice]
    usage: CompletionUsage


class ChatCompletionChunkDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["assistant"] | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: Literal["stop"] | None = None
    logprobs: None = None


class ChatCompletionChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    object: str = "chat.completion.chunk"
    created: int = 0
    model: str
    choices: list[ChatCompletionChunkChoice]
