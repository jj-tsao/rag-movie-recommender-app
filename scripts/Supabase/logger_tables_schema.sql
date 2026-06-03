-- Core query log (/discovery & /recommendations)
create table if not exists rec_queries (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  endpoint text not null check (endpoint in ('discovery/for-you','discovery/explore','recommendations/interactive')),
  query_id text not null,
  user_id uuid,
  session_id text not null,
  media_type text not null,
  query_text text,
  query_filters jsonb,
  ctx_log jsonb,
  pipeline_version text,
  batch_size int not null,
  request_meta jsonb,
  trace_id text  -- OTel trace id (32-hex) → pivot to Tempo
);

create index if not exists idx_rec_queries_endpoint_time on rec_queries (endpoint, created_at desc);
create index if not exists idx_rec_queries_qid on rec_queries (query_id);

-- Candidates (/discovery & /recommendations)
create table if not exists rec_results (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  endpoint text not null check (endpoint in ('discovery/for-you','discovery/explore','recommendations/interactive')),
  query_id text not null,
  media_type text,
  media_id int not null,
  rank int,
  title text,
  score_final double precision,
  score_dense double precision,
  score_sparse double precision,
  meta_breakdown jsonb,
  why_summary text,
  stage text not null,
  source_meta jsonb,
  trace_id text  -- OTel trace id (32-hex) → pivot to Tempo
);
create index if not exists idx_rec_results_ep_qid_rank on rec_results (endpoint, query_id, rank);
create UNIQUE INDEX rec_results_unq_endp_qid_mid ON rec_results (endpoint, query_id, media_id);

-- -----------------------------------------------------------------------------
-- Migration: OpenTelemetry trace bridge columns (idempotent; safe on existing DBs)
-- -----------------------------------------------------------------------------
alter table rec_queries add column if not exists trace_id text;
alter table rec_results add column if not exists trace_id text;
