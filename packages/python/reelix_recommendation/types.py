from typing import Protocol, Any, runtime_checkable
from qdrant_client.models import Filter as QFilter
from reelix_core.types import UserTasteContext, QueryFilter, PromptsEnvelope

SparseVec = dict[str, list[float]]


@runtime_checkable
class OrchestrationRecipe(Protocol):
    name: str

    def build_inputs(
        self,
        *,
        media_type: str,
        query_text: str | None = None,
        query_filter: QueryFilter | None = None,
        user_context: UserTasteContext | None = None,
    ) -> tuple[list[float], SparseVec, QFilter]: ...

    def pipeline_params(self) -> dict[str, Any]: ...

    def build_prompt(
        self,
        *,
        query_text: str | None = None,
        batch_size: int,
        user_context: UserTasteContext | None = None,
        candidates,
    ) -> PromptsEnvelope: ...

    def build_context_log(self, ctx: UserTasteContext | None) -> dict[str, Any]: ...
