from reelix_core.types import UserTasteContext
from reelix_retrieval.query_encoder import Encoder as QueryEncoder
from reelix_recommendation.base_recipe import BaseRecipe
from reelix_core.types import QueryFilter, PromptsEnvelope


class ForYouFeedRecipe(BaseRecipe):
    name = "for_you_feed"

    def __init__(self, query_encoder: QueryEncoder):
        self.query_encoder = query_encoder

    def build_inputs(
        self,
        *,
        media_type: str,
        query_text: str | None,
        query_filter: QueryFilter,
        user_context: UserTasteContext | None,
    ):
        if not user_context:
            raise ValueError("ForYouFeedRecipe requires user_context")

        dense_vec = user_context.taste_vector
        bm25_bag = self.build_bm25_query(
            genres=user_context.signals.genres_include,
            keywords=user_context.signals.keywords_include,
        )
        sparse_vec = self.query_encoder.encode_sparse(bm25_bag, media_type)

        filters = self.build_discover_filter(user_context, query_filter)

        return dense_vec, sparse_vec, filters

    def pipeline_params(self):
        return dict(
            final_top_k=20,
            # sparse_depth=40,
            weights=dict(
                dense=0.54,
                sparse=0.12,
                rating=0.15,
                popularity=0.04,
                genre=0.10,
                recency=0.05,
            ),
        )

    def build_prompt(
        self,
        *,
        query_text: str,
        batch_size: int = 8,
        user_context: UserTasteContext,
        candidates: list,
        llm_model: str | None = None,
        llm_params: dict | None = None,
    ) -> PromptsEnvelope:
        system_prompt = self.get_system_prompt(recipe_name=self.name)
        user_prompt = self.build_user_prompt(
            recipe_name=self.name,
            candidates=candidates,
            user_signals=user_context.signals,
            batch_size=batch_size,
        )
        envelope = self.build_prompt_envelope(
            self.name, system_prompt, user_prompt, candidates
        )

        return envelope


class InteractiveRecipe(BaseRecipe):
    name = "interactive"

    def __init__(self, query_encoder: QueryEncoder):
        self.query_encoder = query_encoder

    def build_inputs(
        self,
        *,
        media_type: str,
        query_text: str | None,
        query_filter: QueryFilter | None,
        user_context: UserTasteContext | None,
    ):
        if not query_text or not query_filter:
            raise ValueError("InteractiveRecipe requires query_text and query_filter")

        dense_vec, sparse_vec = self.query_encoder.dense_and_sparse(
            text=query_text, media_type=media_type
        )

        filters = self.build_filter(query_filter)

        return dense_vec, sparse_vec, filters

    def pipeline_params(self):
        return dict(
            final_top_k=20,
            weights=dict(
                dense=0.60, sparse=0.10, rating=0.18, popularity=0.12, genre=0.00
            ),
        )

    def build_prompt(
        self,
        *,
        query_text: str,
        batch_size: int = 20,
        user_context: UserTasteContext,
        candidates,
    ) -> PromptsEnvelope:
        system_prompt = self.get_system_prompt(recipe_name=self.name)
        user_prompt = self.build_user_prompt(
            recipe_name=self.name,
            candidates=candidates,
            query_text=query_text,
            batch_size=batch_size,
            user_signals=user_context.signals if user_context else None,
        )

        envelope = self.build_prompt_envelope(
            self.name, system_prompt, user_prompt, candidates
        )

        return envelope
