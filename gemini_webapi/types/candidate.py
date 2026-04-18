import html
from textwrap import shorten

from pydantic import BaseModel, field_validator

from .image import Image, WebImage, GeneratedImage


class Candidate(BaseModel):
    """
    A single reply candidate object in the model output. A full response from Gemini usually contains multiple reply candidates.

    Parameters
    ----------
    rcid: `str`
        Reply candidate ID to build the metadata
    text: `str`
        Text output
    thoughts: `str`, optional
        Model's thought process, can be empty. Only populated with `-thinking` models
    web_images: `list[WebImage]`, optional
        List of web images in reply, can be empty.
    generated_images: `list[GeneratedImage]`, optional
        List of generated images in reply, can be empty
    """

    rcid: str
    text: str
    text_delta: str | None = None
    thoughts: str | None = None
    thoughts_delta: str | None = None
    web_images: list[WebImage] = []
    generated_images: list[GeneratedImage] = []

    def __str__(self) -> str:
        return shorten(self.text, width=100)

    def __repr__(self) -> str:
        return (
            f"Candidate(rcid={self.rcid!r}, text={shorten(self.text, width=100)!r}, "
            f"images={self.images!r})"
        )

    @field_validator("text", "thoughts")
    @classmethod
    def decode_html(cls, value: str) -> str:
        """
        Auto unescape HTML entities in text/thoughts if any.
        """

        if value:
            value = html.unescape(value)
        return value

    @property
    def images(self) -> list[Image]:
        return self.web_images + self.generated_images
