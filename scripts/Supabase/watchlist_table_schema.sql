begin;

-- Enum for status
do $$
begin
  if not exists (select 1 from pg_type where typname = 'watch_status') then
    create type watch_status as enum ('want','watched');
  end if;
end $$;

-- Table
create table public.user_watchlist (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  media_type    text not null check (media_type in ('movie','tv')),
  media_id      bigint not null,                                 -- TMDB id
  status        watch_status not null default 'want',
  rating        int check (rating between 1 and 10),             -- nullable
  notes         text,                                            -- nullable, short

  -- Denormalized render fields (optional but useful for fast cards)
  title         text,
  release_year  int,
  poster_url    text,
  backdrop_url  text,
  trailer_url   text,
  genres        text[],
  imdb_rating  float,
  rt_rating    bigint,
  why_summary   text,
  source        text,                                            

  -- Lifecycle
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz,                                     -- soft delete
  deleted_reason text,

  -- Convenience flag (derived)
  is_active      boolean generated always as (deleted_at is null) stored
);

-- Updated_at trigger (using existing tg_set_update_at function)
drop trigger if exists user_watchlist_updated_at on public.user_watchlist;
create trigger user_watchlist_updated_at
before update on public.user_watchlist
for each row execute procedure public.tg_set_updated_at();

-- Indexes
-- One ACTIVE row per (user, media)
create unique index user_watchlist_user_active_unique
  on public.user_watchlist(user_id, media_id, media_type)
  where deleted_at is null;

-- Speed common queries on active rows
create index user_watchlist_active_user_created_idx
  on public.user_watchlist(user_id, created_at desc)
  where deleted_at is null;

-- General lookup by user (includes removed for history)
create index user_watchlist_user_idx
  on public.user_watchlist(user_id, created_at desc);

-- Soft-delete RPC
create or replace function public.soft_delete_watchlist_row(p_id uuid, p_user_id uuid)
returns setof public.user_watchlist
language plpgsql security definer as $$
begin
  update public.user_watchlist
     set deleted_at = now(),
         deleted_reason = 'user_removed',
         updated_at = now()
   where id = p_id and user_id = p_user_id
   returning *;
end;
$$;

revoke all on function public.soft_delete_watchlist_row(uuid, uuid) from public;
grant execute on function public.soft_delete_watchlist_row(uuid, uuid) to anon, authenticated;

-- RLS
alter table public.user_watchlist enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_watchlist' and policyname='user_watchlist_select_own'
  ) then
    create policy user_watchlist_select_own
    on public.user_watchlist
    for select
    using (public.is_me(user_id));
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_watchlist' and policyname='user_watchlist_insert_own'
  ) then
    create policy user_watchlist_insert_own
    on public.user_watchlist
    for insert
    with check (public.is_me(user_id));
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='user_watchlist' and policyname='user_watchlist_update_own'
  ) then
    create policy user_watchlist_update_own
    on public.user_watchlist
    for update
    using (public.is_me(user_id))
    with check (public.is_me(user_id));
  end if;
end $$;

commit;
