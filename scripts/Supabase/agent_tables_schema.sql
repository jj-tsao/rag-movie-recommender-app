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
  model text,

  -- OpenTelemetry bridge
  trace_id text,
  span_id text
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
  final_rank int,  -- null if not served

  -- OpenTelemetry bridge
  trace_id text
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
  tier_latency_ms int,

  -- OpenTelemetry bridge
  trace_id text,
  span_id text
);

create index if not exists idx_tier_summaries_query_id on tier_summaries (query_id);
create index if not exists idx_tier_summaries_rule on tier_summaries (selection_rule, created_at desc);

-- -----------------------------------------------------------------------------
-- reflection_logs: Reflection agent next-step suggestions
-- -----------------------------------------------------------------------------
-- One row per reflection attempt capturing:
-- - Strategy chosen and suggestion text
-- - Outcome status (success, timeout, error)
-- - LLM token usage and latency
-- - Tier stats context for offline analysis
create table if not exists reflection_logs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  -- Identifiers
  query_id text not null,
  session_id text not null,
  user_id uuid,

  -- Reflection output (null if failed/timed out)
  strategy text,   -- 'more_like_title', 'explore_adjacent', 'shift_era'
  suggestion text,

  -- Outcome
  status text not null,  -- 'success', 'timeout', 'error'

  -- Performance metrics
  latency_ms int,
  input_tokens int,
  output_tokens int,
  model text,

  -- Context snapshot from curator (for offline analysis)
  tier_stats jsonb,

  -- OpenTelemetry bridge
  trace_id text,
  span_id text
);

create index if not exists idx_reflection_logs_query_id on reflection_logs (query_id);
create index if not exists idx_reflection_logs_strategy on reflection_logs (strategy, created_at desc);
create index if not exists idx_reflection_logs_status on reflection_logs (status);

-- RLS: backend-only table (accessed via service_role, not exposed to frontend)
alter table reflection_logs enable row level security;

-- -----------------------------------------------------------------------------
-- request_traces: End-to-end request lifecycle traces
-- -----------------------------------------------------------------------------
-- One row per API request capturing:
-- - Stage timings (orchestrator, pipeline, curator, tier, reflection)
-- - Overall status (completed vs error) with error details
-- - Candidate counts
--
-- Use for: latency budgets, error rate monitoring, stage-level debugging
create table if not exists request_traces (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  -- Identifiers
  query_id text not null,
  session_id text,
  user_id uuid,
  endpoint text not null,

  -- Lifecycle
  status text not null default 'completed',  -- 'completed' or 'error'
  error_stage text,    -- orchestrator, pipeline, curator_parse, curator_llm, tier, reflection
  error_type text,     -- exception class name
  error_message text,

  -- Stage timings (ms), null if stage didn't run
  orchestrator_ms int,
  pipeline_ms int,
  curator_ms int,
  tier_ms int,
  reflection_ms int,
  total_ms int,

  -- Counts
  candidates_retrieved int,
  candidates_served int,
  llm_calls int,
  total_input_tokens int,
  total_output_tokens int,

  -- OpenTelemetry bridge (root_span_id = the explore.request server span)
  trace_id text,
  root_span_id text
);

create index if not exists idx_traces_query on request_traces (query_id);
create index if not exists idx_traces_status on request_traces (status, created_at desc);
create index if not exists idx_traces_endpoint on request_traces (endpoint, created_at desc);

-- RLS: backend-only table
alter table request_traces enable row level security;

-- -----------------------------------------------------------------------------
-- daily_metrics: Automated evaluation metrics (one row per metric per day)
-- -----------------------------------------------------------------------------
-- Long/narrow schema: easy to add new metrics without migrations.
-- Groups: curator, latency, cost, errors, routing
--
-- Usage:
--   python -m jobs.eval_metrics              # compute yesterday's metrics
--   python -m jobs.eval_metrics --days 7     # backfill last 7 days
create table if not exists daily_metrics (
  id              uuid primary key default gen_random_uuid(),
  created_at      timestamptz not null default now(),
  metric_date     date not null,
  metric_name     text not null,
  metric_group    text not null,
  value           double precision,
  details         jsonb,
  unique (metric_date, metric_name)
);

create index if not exists idx_daily_metrics_date on daily_metrics (metric_date desc);
create index if not exists idx_daily_metrics_group on daily_metrics (metric_group, metric_date desc);

-- RLS: backend-only table
alter table daily_metrics enable row level security;

-- -----------------------------------------------------------------------------
-- judge_evaluations: LLM-as-judge evaluation scores per candidate
-- -----------------------------------------------------------------------------
-- Two separate evaluation types per candidate:
-- 1. Recommendation quality (relevance + novelty) — evaluates curator picks
-- 2. Explanation quality — evaluates explanation agent output
--
-- Usage:
--   python -m jobs.eval_judge              # evaluate yesterday's queries
--   python -m jobs.eval_judge --days 7     # backfill last 7 days
create table if not exists judge_evaluations (
  id              uuid primary key default gen_random_uuid(),
  created_at      timestamptz not null default now(),

  -- Identifiers
  eval_run_id     text not null,
  query_id        text not null,
  media_id        int not null,

  -- Context (denormalized for self-contained analysis)
  query_text      text,
  title           text,

  -- Recommendation judge scores (1-5, evaluates curator picks)
  relevance       int,
  novelty         int,
  rec_reasoning   text,

  -- Explanation judge score (1-5, evaluates explanation agent)
  explanation_quality int,
  expl_reasoning  text,

  -- Curator comparison (snapshot)
  curator_total_fit  int,
  curator_tier       text,

  -- Metadata
  judge_model     text,
  input_tokens    int,
  output_tokens   int,

  unique (eval_run_id, query_id, media_id)
);

create index if not exists idx_judge_eval_run on judge_evaluations (eval_run_id);
create index if not exists idx_judge_query on judge_evaluations (query_id);

-- RLS: backend-only table
alter table judge_evaluations enable row level security;

-- -----------------------------------------------------------------------------
-- Migration: OpenTelemetry trace bridge columns (idempotent; safe on existing DBs)
-- -----------------------------------------------------------------------------
-- Lets a flagged Supabase row pivot to its Tempo trace (and back, by filtering
-- Tempo on reelix.query_id then joining these tables in SQL). Re-running the
-- whole schema file is safe — ADD COLUMN IF NOT EXISTS is a no-op once applied.
alter table agent_decisions     add column if not exists trace_id text, add column if not exists span_id text;
alter table curator_evaluations add column if not exists trace_id text;
alter table tier_summaries      add column if not exists trace_id text, add column if not exists span_id text;
alter table reflection_logs     add column if not exists trace_id text, add column if not exists span_id text;
alter table request_traces      add column if not exists trace_id text, add column if not exists root_span_id text;

create index if not exists idx_request_traces_trace_id on request_traces (trace_id);
create index if not exists idx_agent_decisions_trace_id on agent_decisions (trace_id);
