-- =============================================================================
-- Agent Logging Tables Schema
-- =============================================================================
-- These tables log LLM decision-making and curator evaluation data for the
-- agent-based /discovery/explore endpoint.
--
-- NOTE: Pipeline scores (dense_score, sparse_score, score_final) are stored
-- in rec_results table, NOT here. Join on query_id + media_id for analysis.
--
-- Query patterns after consolidation:
--   -- Pipeline performance (all endpoints)
--   SELECT * FROM rec_results WHERE query_id = 'xxx';
--
--   -- Curator evaluation with pipeline scores (agent endpoints only)
--   SELECT
--     ce.query_id, ce.media_id, ce.title,
--     ce.genre_fit, ce.tone_fit, ce.theme_fit, ce.tier,
--     rr.score_dense, rr.score_sparse, rr.score_final
--   FROM curator_evaluations ce
--   JOIN rec_results rr ON ce.query_id = rr.query_id AND ce.media_id = rr.media_id
--   WHERE ce.query_id = 'xxx';
-- =============================================================================

-- -----------------------------------------------------------------------------
-- agent_decisions: Orchestrator agent mode routing and planning decisions
-- -----------------------------------------------------------------------------
-- One row per agent invocation capturing:
-- - Mode routing (CHAT vs RECS)
-- - Spec generation (if RECS mode)
-- - LLM token usage and latency
create table if not exists agent_decisions (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  -- Identifiers
  query_id text not null,
  session_id text not null,
  user_id uuid,
  turn_number int not null default 1,

  -- Decision
  mode text not null,  -- 'CHAT' or 'RECS'
  decision_reasoning text,
  tool_called text,  -- 'recommendation_agent' or null for chat

  -- Spec (if RECS mode)
  spec_json jsonb,
  opening_summary text,

  -- Performance metrics
  planning_latency_ms int,
  input_tokens int,
  output_tokens int,
  model text
);

create index if not exists idx_agent_decisions_query_id on agent_decisions (query_id);
create index if not exists idx_agent_decisions_session_id on agent_decisions (session_id);
create index if not exists idx_agent_decisions_mode on agent_decisions (mode, created_at desc);

-- -----------------------------------------------------------------------------
-- curator_evaluations: Per-candidate LLM fit scores and tier assignments
-- -----------------------------------------------------------------------------
-- One row per candidate capturing curator agent evaluation:
-- - Fit scores (genre, tone, structure, theme)
-- - Tier assignment (strong_match, moderate_match, no_match)
-- - Whether it was served and its final rank
--
-- IMPORTANT: Pipeline scores are NOT stored here (deduplication with rec_results).
-- Join on query_id + media_id to get dense_score, sparse_score, score_final.
create table if not exists curator_evaluations (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  -- Identifiers
  query_id text not null,
  media_id int not null,
  media_type text not null,
  title text,

  -- Curator fit scores (0-2 scale)
  genre_fit int,      -- How well genres/sub-genres match
  tone_fit int,       -- How well emotional vibe/tone matches
  structure_fit int,  -- How well narrative structure matches
  theme_fit int,      -- How well thematic ideas align
  total_fit int,      -- Sum of fit scores

  -- Tier assignment
  tier text,  -- 'strong_match', 'moderate_match', 'no_match'

  -- Selection outcome
  is_served boolean not null default false,
  final_rank int  -- null if not served
);

create index if not exists idx_curator_evaluations_query_id on curator_evaluations (query_id);
create index if not exists idx_curator_evaluations_tier on curator_evaluations (tier, created_at desc);
create unique index if not exists idx_curator_evaluations_qid_mid on curator_evaluations (query_id, media_id);

-- -----------------------------------------------------------------------------
-- tier_summaries: Aggregate tier statistics per query
-- -----------------------------------------------------------------------------
-- One row per query capturing:
-- - Tier counts (strong, moderate, no_match)
-- - Selection rule applied
-- - Latency metrics
create table if not exists tier_summaries (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  -- Identifier
  query_id text not null unique,

  -- Tier counts
  total_candidates int not null,
  strong_count int not null default 0,
  moderate_count int not null default 0,
  no_match_count int not null default 0,
  served_count int not null default 0,

  -- Selection rule applied
  selection_rule text,  -- 'all_strong', 'strong_only', 'strong_plus_2_moderate', etc.

  -- Performance metrics
  curator_latency_ms int,
  tier_latency_ms int
);

create index if not exists idx_tier_summaries_query_id on tier_summaries (query_id);
create index if not exists idx_tier_summaries_rule on tier_summaries (selection_rule, created_at desc);
