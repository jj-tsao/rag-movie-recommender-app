import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import MovieCard from "@/components/MovieCard";
import { useToast } from "@/components/ui/useToast";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { setExploreRedirectFlag } from "@/utils/exploreRedirect";
import {
  logUserRecReaction,
  type RatingValue,
} from "@/features/taste_onboarding/api";
import {
  createWatchlistItem,
  deleteWatchlistItem,
  lookupWatchlistKeys,
  updateWatchlist,
  type WatchlistStatus,
} from "@/features/watchlist/api";
import { TEASER_TITLES } from "../data/teaser_titles";
import { EXAMPLE_CHIPS } from "../data/example_chips";

type TeaserSource = (typeof TEASER_TITLES.smart_thoughtful)[number];
type TeaserPool = ReadonlyArray<TeaserSource>;
type TeaserRating = Exclude<RatingValue, "dismiss">;

interface TeaserMovie {
  mediaId: number;
  title: string;
  releaseYear?: number;
  posterUrl?: string;
  backdropUrl?: string;
  genres: string[];
  trailerKey?: string;
  whyText?: string;
  imdbRating?: number;
  rottenTomatoesRating?: number;
}

type TeaserWatchlistEntry = {
  state: "loading" | "not_added" | "in_list";
  status: WatchlistStatus | null;
  rating: number | null;
  id: string | null;
  busy: boolean;
};

function pickRandom<T>(items: ReadonlyArray<T>): T | undefined {
  if (!items.length) return undefined;
  const index = Math.floor(Math.random() * items.length);
  return items[index];
}

const WATCHLIST_SOURCE = "landing_teaser_section";
const FEEDBACK_SOURCE = "landing_teaser_section";

export default function LandingPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [vibe, setVibe] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showAllChips, setShowAllChips] = useState(false);
  const [watchlistState, setWatchlistState] = useState<
    Record<string, TeaserWatchlistEntry>
  >({});
  const [feedbackById, setFeedbackById] = useState<
    Record<string, TeaserRating>
  >({});
  const [pendingFeedback, setPendingFeedback] = useState<
    Record<string, boolean>
  >({});

  const handleBuildTaste = () => {
    const target = user ? "/taste" : "/taste?first_run=1";
    navigate(target);
  };

  function submitQuery(text?: string) {
    const q = (text ?? vibe).trim() || "Hard-boiled investigative crime drama";
    setSubmitting(true);
    setExploreRedirectFlag();
    navigate(`/discover/explore?q=${encodeURIComponent(q)}`);
  }

  const handleExploreSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitQuery();
  };

  const visibleChips = useMemo(
    () => (showAllChips ? EXAMPLE_CHIPS : EXAMPLE_CHIPS.slice(0, 4)),
    [showAllChips]
  );
  const teaserMovies = useMemo<TeaserMovie[]>(() => {
    const pools: TeaserPool[] = [
      TEASER_TITLES.smart_thoughtful,
      TEASER_TITLES["comfort_feel-good"],
      TEASER_TITLES.kinetic_spectacle,
    ];
    return pools
      .map((pool) => pickRandom(pool))
      .filter((movie): movie is TeaserSource =>
        Boolean(
          movie &&
            typeof movie.media_id === "number" &&
            Number.isFinite(movie.media_id)
        )
      )
      .map((movie) => ({
        mediaId: movie.media_id,
        title: movie.title,
        releaseYear: movie.release_year,
        posterUrl: movie.poster_url,
        backdropUrl: movie.backdrop_url,
        genres: movie.genres,
        trailerKey: movie.trailer_key,
        whyText: movie.why_you_might_enjoy_it,
        imdbRating:
          typeof movie.imdb_rating === "number" && Number.isFinite(movie.imdb_rating)
            ? movie.imdb_rating
            : undefined,
        rottenTomatoesRating:
          typeof movie.rotten_tomatoes_rating === "number" && Number.isFinite(movie.rotten_tomatoes_rating)
            ? movie.rotten_tomatoes_rating
            : undefined,
      }));
  }, []);

  useEffect(() => {
    if (teaserMovies.length === 0) {
      setWatchlistState({});
      return;
    }

    const fallback: Record<string, TeaserWatchlistEntry> = {};
    const loading: Record<string, TeaserWatchlistEntry> = {};
    for (const movie of teaserMovies) {
      const key = String(movie.mediaId);
      fallback[key] = {
        state: "not_added",
        status: null,
        rating: null,
        id: null,
        busy: false,
      };
      loading[key] = {
        state: "loading",
        status: null,
        rating: null,
        id: null,
        busy: false,
      };
    }

    if (!user) {
      setWatchlistState(fallback);
      return;
    }

    const keys = teaserMovies.map((movie) => ({
      media_id: movie.mediaId,
      media_type: "movie" as const,
    }));

    if (keys.length === 0) {
      setWatchlistState(fallback);
      return;
    }

    setWatchlistState(loading);

    let cancelled = false;

    void (async () => {
      try {
        const results = await lookupWatchlistKeys(keys);
        if (cancelled) return;

        const resultMap = new Map<number, (typeof results)[number]>();
        for (const entry of results) {
          resultMap.set(entry.media_id, entry);
        }

        setWatchlistState((prev) => {
          const next: Record<string, TeaserWatchlistEntry> = { ...prev };
          for (const movie of teaserMovies) {
            const key = String(movie.mediaId);
            const match = resultMap.get(movie.mediaId);
            next[key] =
              match && match.exists && match.id
                ? {
                    state: "in_list",
                    status: match.status ?? "want",
                    rating: match.rating ?? null,
                    id: match.id,
                    busy: false,
                  }
                : {
                    state: "not_added",
                    status: null,
                    rating: null,
                    id: null,
                    busy: false,
                  };
          }
          return next;
        });
      } catch (error) {
        if (cancelled) return;
        console.warn("Failed to fetch teaser watchlist state", error);
        setWatchlistState(fallback);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [teaserMovies, user]);

  const handleWatchlistAdd = useCallback(
    async (movie: TeaserMovie) => {
      const key = String(movie.mediaId);
      const entry = watchlistState[key];
      if (
        entry &&
        (entry.state === "loading" || entry.state === "in_list" || entry.busy)
      ) {
        return;
      }

      setWatchlistState((prev) => ({
        ...prev,
        [key]: {
          state: "in_list",
          status: "want",
          rating: entry?.rating ?? null,
          id: entry?.id ?? null,
          busy: true,
        },
      }));

      try {
        const result = await createWatchlistItem({
          media_id: movie.mediaId,
          media_type: "movie",
          status: "want",
          title: movie.title,
          poster_url: movie.posterUrl ?? null,
          backdrop_url: movie.backdropUrl ?? null,
          trailer_url: movie.trailerKey
            ? `https://www.youtube.com/watch?v=${movie.trailerKey}`
            : null,
          release_year: movie.releaseYear ?? null,
          genres: movie.genres.length > 0 ? movie.genres : null,
          imdb_rating:
            typeof movie.imdbRating === "number" ? movie.imdbRating : null,
          rt_rating:
            typeof movie.rottenTomatoesRating === "number"
              ? movie.rottenTomatoesRating
              : null,
          why_summary: movie.whyText ?? null,
          source: WATCHLIST_SOURCE,
        });

        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            state: "in_list",
            status: result.status ?? "want",
            rating: result.rating ?? null,
            id: result.id,
            busy: false,
          },
        }));
      } catch (error) {
        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            state: "not_added",
            status: null,
            rating: null,
            id: null,
            busy: false,
          },
        }));
        toast({
          title: "Could not add to watchlist",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [toast, watchlistState]
  );

  const handleWatchlistStatus = useCallback(
    async (movie: TeaserMovie, nextStatus: WatchlistStatus) => {
      const key = String(movie.mediaId);
      const entry = watchlistState[key];
      if (
        !entry ||
        entry.state !== "in_list" ||
        entry.busy ||
        !entry.id ||
        entry.status === nextStatus
      ) {
        return;
      }

      const snapshot: TeaserWatchlistEntry = { ...entry };

      setWatchlistState((prev) => ({
        ...prev,
        [key]: {
          ...prev[key],
          state: "in_list",
          status: nextStatus,
          busy: true,
        },
      }));

      try {
        const result = await updateWatchlist(entry.id, { status: nextStatus });
        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            state: "in_list",
            status: result.status ?? nextStatus,
            rating: result.rating ?? snapshot.rating ?? null,
            id: result.id ?? entry.id,
            busy: false,
          },
        }));
      } catch (error) {
        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            ...snapshot,
            busy: false,
          },
        }));
        toast({
          title: "Could not update watchlist",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [toast, watchlistState]
  );

  const handleWatchlistRemove = useCallback(
    async (movie: TeaserMovie) => {
      const key = String(movie.mediaId);
      const entry = watchlistState[key];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) {
        return;
      }

      const snapshot: TeaserWatchlistEntry = { ...entry };

      setWatchlistState((prev) => ({
        ...prev,
        [key]: {
          state: "not_added",
          status: null,
          rating: null,
          id: null,
          busy: true,
        },
      }));

      try {
        await deleteWatchlistItem(entry.id);
        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            state: "not_added",
            status: null,
            rating: null,
            id: null,
            busy: false,
          },
        }));
      } catch (error) {
        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            ...snapshot,
            busy: false,
          },
        }));
        toast({
          title: "Could not remove from watchlist",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [toast, watchlistState]
  );

  const handleFeedback = useCallback(
    async (movie: TeaserMovie, rating: TeaserRating) => {
      const key = String(movie.mediaId);
      const previous = feedbackById[key];
      if (previous === rating) return;

      setFeedbackById((prev) => ({ ...prev, [key]: rating }));
      setPendingFeedback((prev) => ({ ...prev, [key]: true }));

      try {
        await logUserRecReaction({
          mediaId: movie.mediaId,
          title: movie.title,
          reaction: rating,
          source: FEEDBACK_SOURCE,
        });
      } catch (error) {
        setFeedbackById((prev) => {
          const next = { ...prev };
          if (previous) {
            next[key] = previous;
          } else {
            delete next[key];
          }
          return next;
        });
        toast({
          title: "Feedback not saved",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      } finally {
        setPendingFeedback((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }
    },
    [feedbackById, toast]
  );

  return (
    <main className="mx-auto flex min-h-[70vh] w-full max-w-7xl flex-col items-center gap-10 px-4 pb-16 pt-10 text-center sm:px-6 sm:pt-12">
      {/* HERO */}
      <section className="w-full max-w-7xl px-0">
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-6">
          <div className="space-y-4">
            <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-4xl">
              Find your next watch. Personalized to your taste.
            </h1>
            <p className="text-base text-muted-foreground sm:text-lg">
              Reelix is your personal AI curator. It learns your taste and
              brings you films you’ll actually love.
            </p>
          </div>

          <div className="w-full max-w-2xl space-y-3">
            <form onSubmit={handleExploreSubmit} role="search" className="w-full">
              <label className="sr-only" htmlFor="landing-vibe-input">
                Explore
              </label>
              <div className="flex w-full items-center gap-2 rounded-full border border-border/70 bg-background/90 px-4 py-3 shadow-inner transition focus-within:border-primary focus-within:ring-1 focus-within:ring-primary">
                <input
                  id="landing-vibe-input"
                  type="text"
                  value={vibe}
                  onChange={(e) => setVibe(e.target.value)}
                  placeholder="Describe a vibe or tap an example to jumpstart your picks."
                  className="w-full bg-transparent text-base text-foreground placeholder:text-muted-foreground focus:outline-none"
                  aria-label="Explore by vibe"
                  autoComplete="off"
                  disabled={submitting}
                  autoFocus
                />
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-muted/40 text-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"
                  aria-label="Submit search"
                  title="Find recommendations"
                >
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M21 21l-4.3-4.3M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              </div>
            </form>

            <div
              className="flex flex-wrap items-center justify-center gap-2"
              aria-live="polite"
              id="landing-chip-list"
            >
              {visibleChips.map((text) => (
                <button
                  key={text}
                  type="button"
                  onClick={() => {
                    setVibe(text);
                    submitQuery(text);
                  }}
                  disabled={submitting}
                  className="inline-flex max-w-full items-center rounded-full border border-border/70 bg-background/80 px-3 py-1.5 text-xs text-foreground transition-transform duration-150 hover:-translate-y-0.5 hover:border-primary/70 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"
                  aria-label={`Try: ${text}`}
                  title={text}
                >
                  <span className="truncate">{text}</span>
                </button>
              ))}

              {EXAMPLE_CHIPS.length > 4 ? (
                <button
                  type="button"
                  onClick={() => setShowAllChips((s) => !s)}
                  className="inline-flex items-center rounded-full border border-border/70 bg-background/80 px-3 py-1.5 text-xs text-muted-foreground transition hover:border-primary/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  aria-expanded={showAllChips}
                  aria-controls="landing-chip-list"
                >
                  {showAllChips ? "Show less" : "More..."}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      {/* RECOMMENDATION TEASER */}
      <section className="w-full max-w-7xl space-y-6 px-0 text-left">
        <div className="text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Here’s how recommendations look.
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Each pick comes with a short note on why it matches your taste and
            vibe.
          </p>
        </div>
        <div className="flex flex-col gap-4">
          {teaserMovies.map((movie) => {
            const key = String(movie.mediaId);
            const watchlistEntry = watchlistState[key];
            return (
              <MovieCard
                key={key}
                movie={movie}
                feedback={{
                  value: feedbackById[key],
                  disabled: pendingFeedback[key] ?? false,
                  onChange: (value) => handleFeedback(movie, value),
                }}
                watchlist={{
                  state: watchlistEntry?.state ?? "not_added",
                  status: watchlistEntry?.status ?? null,
                  rating: watchlistEntry?.rating ?? null,
                  busy: watchlistEntry?.busy ?? false,
                  onAdd: () => handleWatchlistAdd(movie),
                  onSelectStatus: (status: WatchlistStatus) =>
                    handleWatchlistStatus(movie, status),
                  onRemove: () => handleWatchlistRemove(movie),
                }}
                layout="wide"
              />
            );
          })}
        </div>
        <div className="mt-12 w-full self-stretch rounded-3xl bg-background/90 p-8 text-center shadow-[0_18px_40px_rgba(0,0,0,0.35)] backdrop-blur sm:p-10">
          <div className="flex flex-col items-center gap-6">
            <div className="flex flex-col items-center gap-3">
              <p className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
                Ready to build your own feed?
              </p>
              <button
                type="button"
                onClick={handleBuildTaste}
                className="inline-flex items-center justify-center rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                Personalize my feed
              </button>
              <span className="text-xs text-muted-foreground">
                Takes under a minute. Get a personal feed instantly.
              </span>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const message = error.message?.trim();
    if (message) {
      return message;
    }
  }
  return fallback;
}
