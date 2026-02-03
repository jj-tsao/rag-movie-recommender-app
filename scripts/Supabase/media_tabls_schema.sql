-- == TMDB ↔ IMDb ID mapping ==
create table if not exists media_ids (
  media_type   text not null,   -- 'movie' | 'tv'
  tmdb_id      bigint not null,
  imdb_id.     text,            -- e.g. 'tt0068646'
  release_date timestamptz,     -- for recency check

  primary key (media_type, tmdb_id)
);

create index if not exists idx_media_ids_imdb_id
  on media_ids(imdb_id);


-- == Ratings, votes, award info from external sources ==
create table if not exists media_ratings (
  media_type       text   not null,   -- 'movie' | 'tv'
  tmdb_id          bigint not null,
  imdb_id          text,
  release_date     timestamptz,

  -- IMDb data (from imdb_ratings_raw)
  imdb_rating      numeric(3,1),   -- e.g. 9.2
  imdb_votes       integer,        -- e.g. 2182094

  -- Rotten Tomatoes (from OMDb)
  rt_score         integer,   -- 0–100; 5,2 gives flexibility

  omdb_last_checked  timestamptz,    -- when RT was last queried
  omdb_status        text,           -- 'ok' | 'not_found' | 'error' | null

  -- Extra signals we might use from OMDb
  metascore        integer,        -- Metacritic 0–100
  awards_summary   text,           -- e.g. 'Won 3 Oscars. 31 wins & 31 nominations total'

  updated_at       timestamptz default now(),
  qdrant_synced_at timestamptz,

  primary key (media_type, tmdb_id)
);

-- Foreign key to keep ratings aligned with known titles
alter table media_ratings
  add constraint media_ratings_media_fk
  foreign key (media_type, tmdb_id)
  references media_ids (media_type, tmdb_id)
  on delete cascade;

-- Indexes for common lookups / joins
create index if not exists idx_media_ratings_imdb_id
  on media_ratings(imdb_id);

create index if not exists idx_media_ratings_updated_at
  on media_ratings(updated_at);

-- Optional: if you ever filter by status a lot (e.g. 'ok' vs 'not_found')
create index if not exists idx_media_ratings_omdb_status
  on media_ratings(omdb_status);


-- == Raw IMDb ratings sync table (direct mirror of title.ratings.tsv.gz) ==
create table if not exists imdb_ratings_raw (
  tconst         text primary key,  -- IMDb title ID, e.g. 'tt0068646'
  average_rating  numeric(3,1),      -- e.g. 9.2
  num_votes       integer            -- e.g. 2182094
);

-- General performance indexese
create index if not exists idx_imdb_ratings_num_votes
  on imdb_ratings_raw(num_votes);

create index if not exists idx_imdb_ratings_avg_rating
  on imdb_ratings_raw(average_rating);
