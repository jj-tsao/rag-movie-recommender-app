from pydantic import BaseModel, Field


class UserPreferencesUpsertResponse(BaseModel):
    user_id: str
    genres_include: list[str] = Field(default_factory=list)
    keywords_include: list[str] = Field(default_factory=list)
