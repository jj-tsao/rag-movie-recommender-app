from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reelix_agent.core.types import AgentMode, InteractiveAgentResult, RecQuerySpec

JsonObj = dict[str, Any]


@dataclass(frozen=True)
class MemoryDelta:
    summary_delta: JsonObj | None = None
    last_spec: JsonObj | None = None
    slot_map: JsonObj | None = None
    seen_media_ids_delta: list[int] | None = None


def _spec_to_json(spec: RecQuerySpec) -> JsonObj:
    if hasattr(spec, "model_dump"):  # pydantic v2
        return spec.model_dump(mode="json")
    return spec.dict()  # pragma: no cover


def _to_int_or_none(x: Any) -> int | None:
    try:
        return int(x)
    except Exception:
        return None

def _build_slot_map(final_recs: list) -> tuple[JsonObj, list[int]]:
    slot_map: JsonObj = {}
    seen: list[int] = []
    seen_set: set[int] = set()

    for idx, c in enumerate(final_recs, start=1):
        p = getattr(c, "payload", None) or {}
        raw_id = p.get("media_id", getattr(c, "id", None))
        media_id = _to_int_or_none(raw_id)

        slot_map[str(idx)] = {
            "media_id": media_id,  # store as int|null
            "title": p.get("title") or p.get("name"),
            "release_year": p.get("release_year"),
        }

        if media_id is not None and media_id not in seen_set:
            seen_set.add(media_id)
            seen.append(media_id)

    return slot_map, seen


def _summary_delta_from_spec(result: InteractiveAgentResult) -> JsonObj:
    """
    Keep this SMALL and “sticky”. Avoid copying the entire spec.
    """
    delta: JsonObj = {"constraints": {}, "prefs": {}}
    mem = result.turn_memory
    spec = result.query_spec

    # intent
    if isinstance(mem, dict):
        # Always record turn_kind if present
        turn_kind = mem.get("turn_kind")
        if turn_kind:
            delta["turn_kind"] = turn_kind
        if "recent_feedback" in mem:
            delta["recent_feedback"] = mem.get("recent_feedback")
        if "last_user_message" in mem:
            delta["last_user_message"] = mem.get("last_user_message")
        if "last_admin_message" in mem:
            delta["last_admin_message"] = mem.get("last_admin_message")

    # constraints
    if spec is not None:
        if spec.providers:
            delta["constraints"]["providers"] = list(spec.providers)
        if spec.max_runtime_minutes is not None:
            delta["constraints"]["max_runtime_minutes"] = spec.max_runtime_minutes
        if spec.year_range:
            # store as [start, end]
            delta["constraints"]["year_range"] = [int(spec.year_range[0]), int(spec.year_range[1])]

        # prefs
        if spec.exclude_genres:
            delta["prefs"]["exclude_genres"] = list(spec.exclude_genres)
        if spec.core_genres:
            delta["prefs"]["core_genres"] = list(spec.core_genres)
    return delta


def build_turn_memory_delta(result: InteractiveAgentResult) -> MemoryDelta:
    """
    Deterministic: memory derived from the agent’s output.
    """
    if result.mode == AgentMode.RECS and result.query_spec:
        slot_map, seen_delta = _build_slot_map(result.final_recs or [])
        return MemoryDelta(
            summary_delta=_summary_delta_from_spec(result),
            last_spec=_spec_to_json(result.query_spec),
            slot_map=slot_map,
            seen_media_ids_delta=seen_delta,
        )
        
    # CHAT mode: persist memory_delta if present (turn_kind/chat, recent_feedback)
    if isinstance(getattr(result, "turn_memory", None), dict):
        return MemoryDelta(summary_delta=_summary_delta_from_spec(result))

    # Default: no write
    return MemoryDelta()


def merge_json(a: JsonObj | None, b: JsonObj | None) -> JsonObj | None:
    """
    Small, safe merge:
      - dicts merge recursively
      - lists: union (stable)
      - scalars: overwrite
    """
    if not b:
        return a
    if not a:
        return b

    def _merge(x: Any, y: Any) -> Any:
        if isinstance(x, dict) and isinstance(y, dict):
            out = dict(x)
            for k, v in y.items():
                out[k] = _merge(out.get(k), v) if k in out else v
            return out
        if isinstance(x, list) and isinstance(y, list):
            seen = set()
            out = []
            for item in x + y:
                key = str(item)
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
            return out
        return y

    return _merge(a, b)

def apply_summary_delta(summary: JsonObj | None, delta: JsonObj) -> JsonObj:
    """
    Apply a summary delta with correct semantics:
    - overwrite volatile keys: turn_kind, recent_feedback
    - merge stable keys: constraints, prefs
    """
    summary = summary or {}
    delta = delta or {}

    # overwrite volatile keys
    if "turn_kind" in delta:
        summary["turn_kind"] = delta["turn_kind"]

    # allow explicit clearing by writing null
    if "recent_feedback" in delta:
        summary["recent_feedback"] = delta["recent_feedback"]

    # include the user and admin message in this turn (CHAT mode only)
    if "last_user_message" in delta:
        summary["last_user_message"] = delta["last_user_message"]
    if "last_admin_message" in delta:
        summary["last_admin_message"] = delta["last_admin_message"]

    # merge stable keys
    stable: JsonObj = {}
    if "constraints" in delta:
        stable["constraints"] = delta["constraints"]
    if "prefs" in delta:
        stable["prefs"] = delta["prefs"]

    merged = merge_json(summary, stable) or summary
    # Special-case: year_range is a 2-int list that should REPLACE, not union-merge.
    # (merge_json unions lists, which breaks ranges like [1970, 2025].)
    delta_constraints = delta.get("constraints")
    if isinstance(delta_constraints, dict) and "year_range" in delta_constraints:
        merged.setdefault("constraints", {})
        if isinstance(merged["constraints"], dict):
            merged["constraints"]["year_range"] = delta_constraints.get("year_range")
    return merged


def merge_int_list_dedupe(old: list[int] | None, add: list[int] | None, *, cap: int = 200) -> list[int] | None:
    if not old and not add:
        return old
    old = old or []
    add = add or []
    out: list[int] = []
    seen: set[int] = set()

    # keep order: old first, then new additions
    for x in old + add:
        if x is None:
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)

    # cap to most recent N (keep tail)
    if cap and len(out) > cap:
        out = out[-cap:]
    return out


def apply_delta_to_payload(payload: JsonObj, *, user_id: str, delta: MemoryDelta) -> None:
    # ownership reset
    if payload.get("user_id") and payload.get("user_id") != user_id:
        payload.clear()
        payload["user_id"] = user_id
        payload["summary"] = None
        payload["last_spec"] = None
        payload["slot_map"] = None
        payload["seen_media_ids"] = None
    else:
        payload.setdefault("user_id", user_id)

    # determine turn_kind (if present)
    turn_kind = None
    if delta.summary_delta and isinstance(delta.summary_delta, dict):
        turn_kind = delta.summary_delta.get("turn_kind")

    # clear old intent-scoped state on "new"
    if turn_kind == "new":
        payload["last_spec"] = None
        payload["slot_map"] = None
        payload["seen_media_ids"] = None

    # summary merge
    if delta.summary_delta:
        payload["summary"] = apply_summary_delta(payload.get("summary"), delta.summary_delta)

    # last_spec / slot_map write (don’t rewrite if we just cleared and you want “fresh”)
    if delta.last_spec is not None:
        payload["last_spec"] = delta.last_spec

    if delta.slot_map is not None:
        payload["slot_map"] = delta.slot_map

    if delta.seen_media_ids_delta is not None:
        payload["seen_media_ids"] = merge_int_list_dedupe(
            payload.get("seen_media_ids"),
            delta.seen_media_ids_delta,
            cap=200,
        )