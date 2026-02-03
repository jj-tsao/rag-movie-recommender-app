-- ========== 0) Extensions & helpers ==========
create extension if not exists pgcrypto;   -- gen_random_uuid()
create extension if not exists citext;     -- case-insensitive text
create extension if not exists vector;     -- pgvector for storing user taste vector

-- Trigger for last update time
create or replace function public.tg_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- User identity check for RLS
create or replace function public.is_me(uid uuid)
returns boolean language sql stable as $$
  select uid = auth.uid()
$$;


-- ========== 1) Core tables ==========
create table if not exists public.app_user (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  email        citext unique,
  display_name text,
  locale       text default 'en-US',
  tz           text  default 'America/Los_Angeles',
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);
drop trigger if exists app_user_updated_at on public.app_user;
create trigger app_user_updated_at
before update on public.app_user
for each row execute procedure public.tg_set_updated_at();

-- Auto-provision app_user row on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public as $$
declare
  v_display_name text;
  v_email citext;
begin
  v_email := nullif(new.email::citext, '');
  v_display_name := nullif(trim((new.raw_user_meta_data->>'display_name')), '');

  insert into public.app_user (user_id, email, display_name)
  values (
    new.id,
    v_email,  -- can be null for anonymous users
    coalesce(v_display_name, case when v_email is not null then split_part(v_email, '@', 1)
                                  else 'Guest-' || left(new.id::text, 8) end)
  )
  on conflict (user_id) do nothing;

  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

-- User preferences
create table if not exists public.user_preferences (
  user_id           uuid primary key references public.app_user(user_id) on delete cascade,
  genres_include    text[] default '{}',
  genres_exclude    text[] default '{}',
  keywords_include  text[] default '{}',
  keywords_exclude  text[] default '{}',
  languages         text[] default '{"en"}',
  year_min          int,
  year_max          int,
  runtime_min       int,
  runtime_max       int,
  maturity_ratings  text[] default '{}',
  include_movies    boolean default true,
  include_tv        boolean default true,
  prefer_recency    boolean default true,
  diversity_level   smallint default 2 check (diversity_level in (0,1,2)), -- 0=strict,1=balanced,2=explore
  updated_at        timestamptz default now(),
  -- range sanity checks
  constraint chk_year_range
    check (year_min is null or year_max is null or year_min <= year_max),
  constraint chk_runtime_range
    check (runtime_min is null or runtime_max is null or runtime_min <= runtime_max)
);
drop trigger if exists user_preferences_updated_at on public.user_preferences;
create trigger user_preferences_updated_at
before update on public.user_preferences
for each row execute procedure public.tg_set_updated_at();

-- Subscriptions (soft-remove via active=false)
create table if not exists public.user_subscriptions (
  user_id     uuid not null references public.app_user(user_id) on delete cascade,
  provider_id bigint not null,   -- tmdb provider_id
  active      boolean default true,
  updated_at  timestamptz default now(),
  primary key (user_id, provider_id)
);
create index if not exists idx_user_subs_user on public.user_subscriptions(user_id);
drop trigger if exists user_subscriptions_updated_at on public.user_subscriptions;
create trigger user_subscriptions_updated_at
before update on public.user_subscriptions
for each row execute procedure public.tg_set_updated_at();

-- Interactions (insert only)
create table if not exists public.user_interactions (
  interaction_id bigserial primary key,
  user_id        uuid not null references public.app_user(user_id) on delete cascade,
  media_type     text not null check (media_type in ('movie','tv')),
  media_id        bigint not null,
  title           text not null,
  event_type     text not null check (event_type in (
                    'impression','rec_reaction', 'add_to_watchlist', 'remove_from_watchlist','mark_watched','rating','dismiss',
                    'trailer_view','dismiss','share','subs_update','settings_change')),
  value          real default 0.0,
  position       int default 0.0,
  source         text not null default 'in_product' check (source in ('taste_onboarding','for_you_feed','in_product','vibe_query','other')),
  query_id       str,
  session_id     str,
  context_json   jsonb default '{}'::jsonb,
  occurred_at    timestamptz default now()
  weight         real default 1.0,
);
create index if not exists idx_ui_user_time on public.user_interactions(user_id, occurred_at desc);
create index if not exists idx_ui_user_media on public.user_interactions(user_id, media_id);
create index if not exists idx_ui_event on public.user_interactions(event_type);
create index if not exists user_interactions_source_idx on public.user_interactions (source);

--  user_settings
create table if not exists public.user_settings (
  user_id uuid primary key references public.app_user(user_id) on delete cascade,
  -- Recommendation behavior
  provider_filter_mode text not null
    check (provider_filter_mode in ('SELECTED','ALL')) default 'SELECTED',
  default_sort_order text
    check (default_sort_order in ('popularity','rating','recency'))
    default 'popularity',

  -- UI / personalization
  language_ui text default 'en-US',
  autoplay_trailers boolean default true,

  -- Onboarding
  onboarding_completed boolean default false,

  updated_at timestamptz default now()
);

drop trigger if exists user_settings_updated_at on public.user_settings;
create trigger user_settings_updated_at
before update on public.user_settings
for each row execute procedure public.tg_set_updated_at();

-- Follows (soft-delete via is_deleted)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_display_name text;
begin
  v_display_name := nullif(trim((new.raw_user_meta_data->>'display_name')), '');
  insert into public.app_user (user_id, email, display_name)
  values (
    new.id,
    new.email,
    coalesce(v_display_name, split_part(new.email, '@', 1))
  )
  on conflict (user_id) do nothing;

  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

-- Alert rules (keep; no delete policy; disable via is_active=false)
create table if not exists public.user_alert_rules (
  rule_id          bigserial primary key,
  user_id          uuid not null references public.app_user(user_id) on delete cascade,
  trigger_type     text not null check (trigger_type in ('announce','release_date','streaming_availability','new_season')),
  target_type      text not null check (target_type in ('title','person','franchise','profile_match')),
  target_ref       text,  -- nullable when target_type='profile_match'
  providers_filter text[] default '{}',
  lead_days        int default 3,
  is_active        boolean default true,
  created_at       timestamptz default now()
);
create index if not exists idx_alerts_user on public.user_alert_rules(user_id);

-- Notification prefs
create table if not exists public.user_notifications (
  user_id          uuid primary key references public.app_user(user_id) on delete cascade,
  email_enabled    boolean default true,
  push_enabled     boolean default false,
  digest_frequency text not null check (digest_frequency in ('off','daily','weekly')) default 'weekly',
  quiet_hours      int4range,
  updated_at       timestamptz default now()
);
drop trigger if exists user_notifications_updated_at on public.user_notifications;
create trigger user_notifications_updated_at
before update on public.user_notifications
for each row execute procedure public.tg_set_updated_at();

-- Agent state (cachey; recomputable)
create table if not exists public.user_agent_state (
  user_id            uuid primary key references public.app_user(user_id) on delete cascade,
  last_profile_build timestamptz,
  last_alert_scan    timestamptz,
  backlog_json       jsonb default '{}'::jsonb,
  notes              text,
  updated_at         timestamptz default now()
);
drop trigger if exists user_agent_state_updated_at on public.user_agent_state;
create trigger user_agent_state_updated_at
before update on public.user_agent_state
for each row execute procedure public.tg_set_updated_at();

-- User taste profile with taste vectors
create table if not exists public.user_taste_profile (
  user_id     uuid not null references public.app_user(user_id) on delete cascade,
  media_type  text not null check (media_type in ('movie','tv')),
  model_name  text not null,                     -- e.g. 'bge-base-en-v1.5'
  dim         int  not null default 768,
  dense       vector(768) not null,              -- match your prod dim
  positive_n  int not null default 0,
  negative_n  int not null default 0,
  params      jsonb not null default '{}'::jsonb, -- α,β,γ,δ, λ, etc.
  last_built_at timestamptz not null default now(),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  primary key (user_id, media_type, model_name)
);
create or replace function public.tg_set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end $$;

drop trigger if exists user_taste_profile_updated_at on public.user_taste_profile;
create trigger user_taste_profile_updated_at
before update on public.user_taste_profile
for each row execute procedure public.tg_set_updated_at();

-- ========== 2) RLS: enable + granular policies (no DELETE) ==========
alter table public.app_user           enable row level security;
alter table public.user_preferences   enable row level security;
alter table public.user_subscriptions enable row level security;
alter table public.user_interactions  enable row level security;
alter table public.user_follows       enable row level security;
alter table public.user_alert_rules   enable row level security;
alter table public.user_notifications enable row level security;
alter table public.user_agent_state   enable row level security;
alter table public.user_settings enable row level security;
alter table public.user_taste_profile enable row level security;

do $$
begin
  -- app_user
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='app_user' and policyname='app_user_select_own'
  ) then
    create policy app_user_select_own on public.app_user for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='app_user' and policyname='app_user_insert_own'
  ) then
    create policy app_user_insert_own on public.app_user for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='app_user' and policyname='app_user_update_own'
  ) then
    create policy app_user_update_own on public.app_user for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

  -- user_preferences
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_preferences' and policyname='prefs_select_own'
  ) then
    create policy prefs_select_own on public.user_preferences for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_preferences' and policyname='prefs_insert_own'
  ) then
    create policy prefs_insert_own on public.user_preferences for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_preferences' and policyname='prefs_update_own'
  ) then
    create policy prefs_update_own on public.user_preferences for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

  -- user_subscriptions
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_subscriptions' and policyname='subs_select_own'
  ) then
    create policy subs_select_own on public.user_subscriptions for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_subscriptions' and policyname='subs_insert_own'
  ) then
    create policy subs_insert_own on public.user_subscriptions for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_subscriptions' and policyname='subs_update_own'
  ) then
    create policy subs_update_own on public.user_subscriptions for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

  -- user_interactions (insert + update; no delete)
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_interactions' and policyname='interactions_select_own'
  ) then
    create policy interactions_select_own on public.user_interactions for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_interactions' and policyname='interactions_insert_own'
  ) then
    create policy interactions_insert_own on public.user_interactions for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_interactions' and policyname='interactions_update_own'
  ) then
    create policy interactions_update_own on public.user_interactions for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

-- user_settings (insert + update; no delete)
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_settings' and policyname='settings_select_own'
  ) then
    create policy settings_select_own on public.user_settings
      for select using (public.is_me(user_id));
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_settings' and policyname='settings_insert_own'
  ) then
    create policy settings_insert_own on public.user_settings
      for insert with check (public.is_me(user_id));
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_settings' and policyname='settings_update_own'
  ) then
    create policy settings_update_own on public.user_settings
      for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

  -- user_follows (soft delete via is_deleted)
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_follows' and policyname='follows_select_own'
  ) then
    create policy follows_select_own on public.user_follows for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_follows' and policyname='follows_insert_own'
  ) then
    create policy follows_insert_own on public.user_follows for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_follows' and policyname='follows_update_own'
  ) then
    create policy follows_update_own on public.user_follows for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

  -- user_alert_rules
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_alert_rules' and policyname='alerts_select_own'
  ) then
    create policy alerts_select_own on public.user_alert_rules for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_alert_rules' and policyname='alerts_insert_own'
  ) then
    create policy alerts_insert_own on public.user_alert_rules for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_alert_rules' and policyname='alerts_update_own'
  ) then
    create policy alerts_update_own on public.user_alert_rules for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

  -- user_notifications
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_notifications' and policyname='notify_select_own'
  ) then
    create policy notify_select_own on public.user_notifications for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_notifications' and policyname='notify_insert_own'
  ) then
    create policy notify_insert_own on public.user_notifications for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_notifications' and policyname='notify_update_own'
  ) then
    create policy notify_update_own on public.user_notifications for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

  -- user_agent_state
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_agent_state' and policyname='agent_select_own'
  ) then
    create policy agent_select_own on public.user_agent_state for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_agent_state' and policyname='agent_insert_own'
  ) then
    create policy agent_insert_own on public.user_agent_state for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_agent_state' and policyname='agent_update_own'
  ) then
    create policy agent_update_own on public.user_agent_state for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

-- taste profile
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_taste_profile' and policyname='taste_select_own'
  ) then
    create policy taste_select_own on public.user_taste_profile for select using (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_taste_profile' and policyname='taste_insert_own'
  ) then
    create policy taste_insert_own on public.user_taste_profile for insert with check (public.is_me(user_id));
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_taste_profile' and policyname='taste_update_own'
  ) then
    create policy taste_update_own on public.user_taste_profile for update using (public.is_me(user_id)) with check (public.is_me(user_id));
  end if;

end
$$ language plpgsql;


-- ========== 3) Seed defaults on first app_user row ==========
create or replace function public.seed_user_defaults()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.user_preferences (user_id) values (new.user_id)
    on conflict (user_id) do nothing;

  insert into public.user_notifications (user_id) values (new.user_id)
    on conflict (user_id) do nothing;

  insert into public.user_agent_state (user_id) values (new.user_id)
    on conflict (user_id) do nothing;

  insert into public.user_settings (user_id) values (new.user_id)
    on conflict (user_id) do nothing;

  return new;
end $$;

drop trigger if exists on_app_user_created on public.app_user;
create trigger on_app_user_created
after insert on public.app_user
for each row execute procedure public.seed_user_defaults();