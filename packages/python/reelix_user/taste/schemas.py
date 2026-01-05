from pydantic import BaseModel
from datetime import datetime
from reelix_core.types import MediaType

class TasteProfileMeta(BaseModel):
    media_type: MediaType = MediaType.MOVIE
    positive_n: int | None = None
    negative_n: int | None = None
    dim: int | None = None
    model_name: str | None = None
    last_built_at: datetime | None = None

