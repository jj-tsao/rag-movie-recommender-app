from enum import Enum
from typing import List

from pydantic import BaseModel, field_validator, model_validator


class ChatMessage(BaseModel):
    role: str
    content: str


class MediaType(str, Enum):
    MOVIE = "movies"
    TV = "tvs"


class ChatRequest(BaseModel):
    question: str
    history: List[ChatMessage] = []
    media_type: MediaType = MediaType.MOVIE
    genres: List[str] = []
    providers: List[str] = []
    year_range: List[int] = [1920, 2025]

    @field_validator("question")
    def validate_question(cls, v):
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v

    @model_validator(mode="after")
    def validate_year_range(self) -> "ChatRequest":
        if len(self.year_range) != 2:
            raise ValueError("year_range must be a list of exactly two integers: [start, end]")
        return self
