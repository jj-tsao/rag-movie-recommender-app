from reelix_agent.orchestrator.session_memory import (
    build_turn_memory_delta,
    apply_delta_to_payload,
)
from app.infrastructure.cache.state_store import StateStore, SessionState


async def upsert_session_memory(
    *,
    state_store: StateStore,
    session_id: str,
    user_id: str,
    agent_result,
    ttl_sec: int = 7 * 24 * 3600,  # 7 days
) -> None:
    delta = build_turn_memory_delta(agent_result)
    ok = await state_store.update_session(
        session_id=session_id,
        ttl_sec=ttl_sec,
        mutate=lambda payload: apply_delta_to_payload(
            payload, user_id=user_id, delta=delta
        ),
    )
    if ok:
        return

    # create new session
    payload = {"user_id": user_id, "summary": None, "last_spec": None, "slot_map": None, "seen_media_ids": None}
    apply_delta_to_payload(payload, user_id=user_id, delta=delta)

    await state_store.put_session(
        session_id=session_id,
        state=SessionState(
            user_id=user_id,
            summary=payload["summary"],
            last_spec=payload["last_spec"],
            slot_map=payload["slot_map"],
            seen_media_ids=payload["seen_media_ids"],
        ),
        ttl_sec=ttl_sec,
    )
