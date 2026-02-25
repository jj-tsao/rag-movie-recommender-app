# Conversation Export: Mentioned Titles Filtering Implementation

**Date:** 2026-01-31
**Feature:** Exclude mentioned movies from recommendation results

---

## Problem Statement

When users ask "I like Interstellar, what do you recommend?", the same movie (Interstellar) appears in the results. The system doesn't extract and filter mentioned titles.

---

## Solution Discussion

### Initial Exploration

Explored the recommendation pipeline to understand the data flow:
- `/discovery/explore` endpoint in `routes_agent.py`
- Orchestrator → Recommendation Tool → Retrieval Pipeline → Curator flow
- Found that `build_qfilter()` already supports `exclude_ids` but wasn't being used
- `RecQuerySpec` has `seed_titles` field (unused)

### Design Options Considered

**Option 1: Filter at Qdrant query time**
- Add `exclude_titles` to `build_qfilter()` using MatchText
- Pros: Zero extra round trips
- Cons: Ranking issues - if we request K candidates and some are filtered, we get K-1 results

**Option 2: Filter after pipeline (top-level)**
- Filter after `pipeline.run()` returns
- Pros: Simple implementation
- Cons: `final_top_k=12` means filtering could return only 10-11 results (significant loss)

**Option 3: Filter inside pipeline, after RRF fusion (CHOSEN)**
- Filter after RRF fusion (~320 candidates) but before metadata reranking
- Pros: Guaranteed K results, efficient, localized change
- Cons: Slightly more invasive change

### Final Decision

**Option 3** was chosen because:
1. Pipeline returns `final_top_k=12` - filtering after would cause significant result loss
2. Filtering after fusion (~320 candidates) preserves ranking integrity
3. Reranker works on clean candidate set

---

## Implementation

### Files Modified

#### 1. `/packages/python/reelix_agent/tools/recommendation_tool.py`

Added `mentioned_titles` field to `RECOMMENDATION_AGENT_SCHEMA`:

```python
"mentioned_titles": {
    "type": "array",
    "description": (
        "Movie titles explicitly mentioned by user as examples "
        "(e.g., 'I like Interstellar', 'similar to The Matrix'). "
        "Extract title only. These will be automatically excluded from results."
    ),
    "items": {"type": "string"},
    "default": [],
},
```

Added extraction logic in `handle_recommendation_agent()`:

```python
# Extract mentioned_titles and store in spec for filtering
mentioned_titles = raw_spec.get("mentioned_titles") or []
if mentioned_titles:
    spec.seed_titles = mentioned_titles
    print(f"[recommendation_tool] Will exclude mentioned titles: {mentioned_titles}")
```

#### 2. `/packages/python/reelix_agent/orchestrator/orchestrator_prompts.py`

Added LLM instructions for title extraction:

```markdown
- mentioned_titles:
  - Extract movie titles explicitly mentioned by the user as examples or comparisons.
  - Include titles from phrases like: "I like X", "similar to X", "something like X", "movies like X".
  - Extract the title only, not descriptors (e.g., "The Matrix" not "The Matrix trilogy").
  - These titles will be automatically excluded from results to avoid recommending what the user already knows.
  - Do NOT extract slot references like "#3" or "the third one" here (those are handled via session memory).
```

#### 3. `/packages/python/reelix_agent/orchestrator/agent_rec_runner.py`

Pass mentioned titles to pipeline:

```python
candidates, traces = self._pipeline.run(
    media_type=spec.media_type.value,
    dense_vec=dense_vec,
    sparse_vec=sparse_vec,
    qfilter=qfilter,
    user_context=user_context,
    mentioned_titles=spec.seed_titles if spec.seed_titles else None,
    **pipeline_params,
)
```

#### 4. `/packages/python/reelix_recommendation/recommend.py`

Added helper functions:

```python
def _normalize_title(title: str) -> str:
    """Normalize title for comparison (lowercase, no punctuation)."""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)  # Remove punctuation
    title = re.sub(r'\s+', ' ', title)     # Normalize whitespace
    return title.strip()


def _filter_mentioned_titles(
    candidates: List[Candidate],
    mentioned_titles: List[str],
) -> List[Candidate]:
    """Filter out candidates whose titles match mentioned_titles (case-insensitive)."""
    if not mentioned_titles:
        return candidates

    normalized_mentioned = {_normalize_title(t) for t in mentioned_titles}

    filtered = []
    for candidate in candidates:
        title = candidate.payload.get("title", "")
        if _normalize_title(title) not in normalized_mentioned:
            filtered.append(candidate)
        else:
            print(f"[Pipeline] Filtered mentioned title: {title}")

    return filtered
```

Added parameter to `run()` method:

```python
def run(
    self,
    *,
    # ... existing params ...
    mentioned_titles: List[str] | None = None,
) -> Tuple[List[Candidate], Dict[int, ScoreTrace]]:
```

Added filtering after RRF fusion:

```python
pool = merge_by_id(dense, sparse, pool_ids)

# 3.5) Filter mentioned titles before reranking
if mentioned_titles:
    pool = _filter_mentioned_titles(pool, mentioned_titles)
    print(f"[Pipeline] After filtering mentioned titles: {len(pool)} candidates")

# 4) metadata rerank
```

---

## Data Flow

```
User: "I like Interstellar, what do you recommend?"
  │
  ▼
Orchestrator LLM extracts:
  mentioned_titles: ["Interstellar"]
  │
  ▼
recommendation_tool.py:
  spec.seed_titles = ["Interstellar"]
  │
  ▼
agent_rec_runner.py:
  pipeline.run(mentioned_titles=["Interstellar"])
  │
  ▼
recommend.py (after RRF fusion):
  ~320 candidates → filter → ~319 candidates
  │
  ▼
Metadata reranking → CE reranking → top-12
  │
  ▼
Returns 12 results (without Interstellar)
```

---

## Pipeline Flow Diagram

```
1. Dense retrieval → 300 candidates
2. Sparse retrieval → 20 candidates
3. RRF fusion → ~320 candidates
   👉 FILTER HERE (remove mentioned titles)
4. Metadata reranking → top-100 from remaining ~318
5. Cross-encoder → top-30 from metadata results
6. Final sort → top-12
```

---

## Edge Cases Handled

1. **Case insensitivity** - `_normalize_title()` converts to lowercase
2. **Punctuation** - Normalization removes punctuation
3. **Exact match only** - No substring matching (avoids false positives)
4. **Typos** - No fuzzy tolerance for MVP
5. **Guaranteed K results** - Filtering happens early in pipeline
6. **Session memory** - Existing `seen_media_ids` still applies novelty penalty

---

## Testing

```bash
cd apps/api
uvicorn app.main:app --reload --port 7860
```

Test query: "I like Interstellar, what do you recommend?"

Expected logs:
```
[recommendation_tool] Will exclude mentioned titles: ['Interstellar']
[Pipeline] Filtered mentioned title: Interstellar
[Pipeline] After filtering mentioned titles: 318 candidates
```

Expected result: Top-12 recommendations without Interstellar

---

## Future Enhancements (Out of Scope)

1. Slot reference exclusion ("not like #3")
2. Year-based disambiguation ("Joker (2019)")
3. Fuzzy matching for typos
4. Full-text index on Qdrant for faster title lookups

---

## Performance Impact

- **Latency**: <1ms for filtering ~320 candidates
- **Network**: No extra round trips
- **Ranking quality**: Preserved - reranker works on clean candidate set
