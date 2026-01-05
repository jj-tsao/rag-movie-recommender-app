import { useCallback, useEffect, useMemo, useState } from "react";
import MovieCard from "@/components/MovieCard";
import { useToast } from "@/components/ui/useToast";
import {
  deleteWatchlistItem,
  fetchWatchlist,
  updateWatchlist,
  type WatchlistListItem,
  type WatchlistStatus,
} from "@/features/watchlist/api";

type WatchlistEntry = {
  id: string;
  mediaId: string;
  title: string;
  releaseYear?: number;
  posterUrl?: string;
  backdropUrl?: string;
  trailerKey?: string;
  genres: string[];
  status: WatchlistStatus;
  rating: number | null;
  imdbRating: number | null;
  rtRating: number | null;
  whySummary: string | null;
};

type WatchlistControlState = {
  state: "in_list";
  status: WatchlistStatus;
  rating: number | null;
  busy: boolean;
};

const PAGE_SIZE = 100;

export default function WatchlistPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<Record<string, WatchlistEntry>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [controls, setControls] = useState<Record<string, WatchlistControlState>>({});
  const [activePrompt, setActivePrompt] = useState<string | null>(null);
  const { toast } = useToast();

  const loadWatchlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchWatchlist({ page: 1, pageSize: PAGE_SIZE });
      const mapped: Record<string, WatchlistEntry> = {};
      const controlMap: Record<string, WatchlistControlState> = {};
      const newOrder: string[] = [];

      response.items.forEach((item) => {
        const mappedItem = toWatchlistEntry(item);
        mapped[mappedItem.id] = mappedItem;
        newOrder.push(mappedItem.id);
        controlMap[mappedItem.id] = {
          state: "in_list",
          status: mappedItem.status,
          rating: mappedItem.rating,
          busy: false,
        };
      });

      setItems(mapped);
      setOrder(newOrder);
      setControls(controlMap);
    } catch (err) {
      setError(toErrorMessage(err, "Failed to load your watchlist."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWatchlist();
  }, [loadWatchlist]);

  const openRatingPrompt = useCallback((id: string) => {
    setActivePrompt(id);
  }, []);

  const closeRatingPrompt = useCallback((id?: string) => {
    setActivePrompt((current) => {
      if (!current) return current;
      if (!id || current === id) return null;
      return current;
    });
  }, []);

  const toWatchItems = useMemo(() => {
    const result: WatchlistEntry[] = [];
    for (const id of order) {
      const entry = items[id];
      if (!entry) continue;
      if (entry.status !== "watched") {
        result.push(entry);
      }
    }
    return result;
  }, [items, order]);

  const watchedItems = useMemo(() => {
    const result: WatchlistEntry[] = [];
    for (const id of order) {
      const entry = items[id];
      if (!entry) continue;
      if (entry.status === "watched") {
        result.push(entry);
      }
    }
    return result;
  }, [items, order]);

  const handleStatusChange = useCallback(
    async (entry: WatchlistEntry, nextStatus: WatchlistStatus) => {
      const prevStatus = entry.status;
      if (prevStatus === nextStatus) return;

      setControls((prev) => ({
        ...prev,
        [entry.id]: {
          state: "in_list",
          status: nextStatus,
          rating: prev[entry.id]?.rating ?? entry.rating,
          busy: true,
        },
      }));

      setItems((prev) => {
        const current = prev[entry.id];
        if (!current) return prev;
        return {
          ...prev,
          [entry.id]: {
            ...current,
            status: nextStatus,
          },
        };
      });

      if (nextStatus !== "watched") {
        closeRatingPrompt(entry.id);
      }

      try {
        const result = await updateWatchlist(entry.id, { status: nextStatus });
        const updatedStatus = result.status ?? nextStatus;
        const updatedRating = result.rating ?? null;

        setItems((prev) => {
          const current = prev[entry.id];
          if (!current) return prev;
          return {
            ...prev,
            [entry.id]: {
              ...current,
              status: updatedStatus,
              rating: updatedRating,
            },
          };
        });

        setControls((prev) => ({
          ...prev,
          [entry.id]: {
            state: "in_list",
            status: updatedStatus,
            rating: updatedRating,
            busy: false,
          },
        }));

        if (updatedStatus === "watched" && updatedRating === null) {
          openRatingPrompt(entry.id);
        } else {
          closeRatingPrompt(entry.id);
        }
      } catch (err) {
        setItems((prev) => {
          const current = prev[entry.id];
          if (!current) return prev;
          return {
            ...prev,
            [entry.id]: {
              ...current,
              status: prevStatus,
            },
          };
        });
        setControls((prev) => ({
          ...prev,
          [entry.id]: {
            state: "in_list",
            status: prevStatus,
            rating: prev[entry.id]?.rating ?? entry.rating,
            busy: false,
          },
        }));
        toast({
          title: "Could not update watchlist",
          description: toErrorMessage(err, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [closeRatingPrompt, openRatingPrompt, toast],
  );

  const handleRating = useCallback(
    async (entry: WatchlistEntry, ratingValue: number) => {
      if (!Number.isFinite(ratingValue) || ratingValue < 1 || ratingValue > 10) {
        return;
      }
      const normalized = Math.min(10, Math.max(1, Math.round(ratingValue)));
      const previousRating = entry.rating;

      setControls((prev) => ({
        ...prev,
        [entry.id]: {
          state: "in_list",
          status: prev[entry.id]?.status ?? entry.status,
          rating: normalized,
          busy: true,
        },
      }));

      setItems((prev) => {
        const current = prev[entry.id];
        if (!current) return prev;
        return {
          ...prev,
          [entry.id]: {
            ...current,
            rating: normalized,
          },
        };
      });

      closeRatingPrompt(entry.id);

      try {
        const result = await updateWatchlist(entry.id, { rating: normalized });
        setItems((prev) => {
          const current = prev[entry.id];
          if (!current) return prev;
          return {
            ...prev,
            [entry.id]: {
              ...current,
              status: result.status ?? current.status,
              rating: result.rating ?? normalized,
            },
          };
        });
        setControls((prev) => ({
          ...prev,
          [entry.id]: {
            state: "in_list",
            status: prev[entry.id]?.status ?? entry.status,
            rating: result.rating ?? normalized,
            busy: false,
          },
        }));
      } catch (err) {
        setItems((prev) => {
          const current = prev[entry.id];
          if (!current) return prev;
          return {
            ...prev,
            [entry.id]: {
              ...current,
              rating: previousRating,
            },
          };
        });
        setControls((prev) => ({
          ...prev,
          [entry.id]: {
            state: "in_list",
            status: prev[entry.id]?.status ?? entry.status,
            rating: previousRating,
            busy: false,
          },
        }));
        toast({
          title: "Could not save rating",
          description: toErrorMessage(err, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [closeRatingPrompt, toast],
  );

  const handleRatingSkip = useCallback(
    (entry: WatchlistEntry) => {
      closeRatingPrompt(entry.id);
    },
    [closeRatingPrompt],
  );

  const handleRatingPromptOpen = useCallback(
    (entry: WatchlistEntry) => {
      openRatingPrompt(entry.id);
    },
    [openRatingPrompt],
  );

  const handleRatingClear = useCallback(
    async (entry: WatchlistEntry) => {
      const previousEntry = items[entry.id];
      const previousControl = controls[entry.id];
      if (!previousEntry || !previousControl || previousControl.rating === null) {
        closeRatingPrompt(entry.id);
        return;
      }

      setControls((prev) => {
        const existing = prev[entry.id];
        if (!existing) return prev;
        return {
          ...prev,
          [entry.id]: {
            ...existing,
            rating: null,
            busy: true,
          },
        };
      });

      setItems((prev) => {
        const existing = prev[entry.id];
        if (!existing) return prev;
        return {
          ...prev,
          [entry.id]: {
            ...existing,
            rating: null,
          },
        };
      });

      closeRatingPrompt(entry.id);

      try {
        const result = await updateWatchlist(entry.id, { rating: null });
        setItems((prev) => {
          const existing = prev[entry.id];
          if (!existing) return prev;
          return {
            ...prev,
            [entry.id]: {
              ...existing,
              status: result.status ?? existing.status,
              rating: result.rating ?? null,
            },
          };
        });
        setControls((prev) => {
          const existing = prev[entry.id];
          if (!existing) return prev;
          return {
            ...prev,
            [entry.id]: {
              ...existing,
              status: result.status ?? existing.status,
              rating: result.rating ?? null,
              busy: false,
            },
          };
        });
      } catch (err) {
        setItems((prev) => ({
          ...prev,
          [entry.id]: previousEntry,
        }));
        setControls((prev) => ({
          ...prev,
          [entry.id]: {
            ...previousControl,
            busy: false,
          },
        }));
        toast({
          title: "Could not clear rating",
          description: toErrorMessage(err, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [closeRatingPrompt, controls, items, toast],
  );

  const handleRemove = useCallback(
    async (entry: WatchlistEntry) => {
      const previousEntry = items[entry.id];
      const previousControl = controls[entry.id];
      const index = order.findIndex((value) => value === entry.id);

      setControls((prev) => ({
        ...prev,
        [entry.id]: {
          state: "in_list",
          status: prev[entry.id]?.status ?? entry.status,
          rating: prev[entry.id]?.rating ?? entry.rating,
          busy: true,
        },
      }));

      setItems((prev) => {
        if (!(entry.id in prev)) return prev;
        const next = { ...prev };
        delete next[entry.id];
        return next;
      });
      setOrder((prev) => prev.filter((value) => value !== entry.id));
      closeRatingPrompt(entry.id);

      try {
        await deleteWatchlistItem(entry.id);
        setControls((prev) => {
          const next = { ...prev };
          delete next[entry.id];
          return next;
        });
      } catch (err) {
        if (previousEntry) {
          setItems((prev) => ({
            ...prev,
            [entry.id]: previousEntry,
          }));
        }
        setOrder((prev) => {
          const next = [...prev];
          const insertAt = index >= 0 ? Math.min(index, next.length) : next.length;
          next.splice(insertAt, 0, entry.id);
          return next;
        });
        setControls((prev) => ({
          ...prev,
          [entry.id]: {
            state: "in_list",
            status: previousControl?.status ?? entry.status,
            rating: previousControl?.rating ?? entry.rating,
            busy: false,
          },
        }));
        toast({
          title: "Could not remove from watchlist",
          description: toErrorMessage(err, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [closeRatingPrompt, controls, items, order, toast],
  );

  const hasItems = toWatchItems.length > 0 || watchedItems.length > 0;

  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 pb-24 pt-10">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">Your Watchlist</h1>
        <p className="text-sm text-muted-foreground">
          Keep track of what you want to watch and what you have already seen.
        </p>
      </header>

      {loading ? (
        <WatchlistLoading />
      ) : error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-6 text-sm text-destructive">
          {error}
          <div className="mt-4 text-left">
            <button
              type="button"
              onClick={() => void loadWatchlist()}
              className="rounded-md border border-destructive/40 px-3 py-1.5 text-destructive transition hover:bg-destructive/10"
            >
              Try again
            </button>
          </div>
        </div>
      ) : hasItems ? (
        <div className="flex flex-col gap-10">
          <WatchlistGroup
            title="To Watch"
            emptyMessage="Save movies or shows you want to see. They'll appear here."
            items={toWatchItems}
            controls={controls}
            activePrompt={activePrompt}
            onStatusChange={handleStatusChange}
            onRemove={handleRemove}
            onRating={handleRating}
            onRatingSkip={handleRatingSkip}
            onRatingPromptOpen={handleRatingPromptOpen}
            onRatingClear={handleRatingClear}
          />
          <WatchlistGroup
            title="Watched"
            emptyMessage="Mark items as watched to keep track of what you've finished."
            items={watchedItems}
            controls={controls}
            activePrompt={activePrompt}
            onStatusChange={handleStatusChange}
            onRemove={handleRemove}
            onRating={handleRating}
            onRatingSkip={handleRatingSkip}
            onRatingPromptOpen={handleRatingPromptOpen}
            onRatingClear={handleRatingClear}
          />
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-background/60 px-6 py-12 text-center text-sm text-muted-foreground">
          Your watchlist is empty. Start browsing and add titles you want to watch.
        </div>
      )}
    </section>
  );
}

function WatchlistGroup({
  title,
  emptyMessage,
  items,
  controls,
  activePrompt,
  onStatusChange,
  onRemove: handleRemove,
  onRating,
  onRatingSkip,
  onRatingPromptOpen,
  onRatingClear,
}: {
  title: string;
  emptyMessage: string;
  items: WatchlistEntry[];
  controls: Record<string, WatchlistControlState>;
  activePrompt: string | null;
  onStatusChange: (entry: WatchlistEntry, status: WatchlistStatus) => void;
  onRemove: (entry: WatchlistEntry) => void;
  onRating: (entry: WatchlistEntry, rating: number) => void;
  onRatingSkip: (entry: WatchlistEntry) => void;
  onRatingPromptOpen: (entry: WatchlistEntry) => void;
  onRatingClear: (entry: WatchlistEntry) => void;
}) {
  if (items.length === 0) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold text-foreground">
          {title} (0)
        </h2>
        <p className="rounded-lg border border-dashed border-border bg-background/50 px-4 py-6 text-sm text-muted-foreground">
          {emptyMessage}
        </p>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold text-foreground">
        {title} ({items.length})
      </h2>
      <div className="flex flex-col gap-6">
        {items.map((entry) => {
          const control = controls[entry.id] ?? {
            state: "in_list" as const,
            status: entry.status,
            rating: entry.rating,
            busy: false,
          };

          return (
            <MovieCard
              key={entry.id}
              layout="wide"
              movie={{
                title: entry.title,
                releaseYear: entry.releaseYear,
                posterUrl: entry.posterUrl,
                backdropUrl: entry.backdropUrl,
                trailerKey: entry.trailerKey,
                genres: entry.genres,
                providers: [],
                imdbRating: entry.imdbRating ?? undefined,
                rottenTomatoesRating: entry.rtRating ?? undefined,
                whyText: entry.whySummary ?? undefined,
              }}
              watchlist={{
                state: control.state,
                status: control.status,
                rating: control.rating,
                busy: control.busy,
                onAdd: () => {},
                onSelectStatus: (status) => onStatusChange(entry, status),
                onRemove: () => handleRemove(entry),
                showRatingPrompt: activePrompt === entry.id,
                onRatingSelect: (value) => onRating(entry, value),
                onRatingSkip: () => onRatingSkip(entry),
                onRatingPromptOpen: () => onRatingPromptOpen(entry),
                onRatingClear: () => onRatingClear(entry),
              }}
            />
          );
        })}
      </div>
    </section>
  );
}

function WatchlistLoading() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          key={index}
          className="h-32 animate-pulse rounded-xl bg-gradient-to-r from-muted/40 via-muted/20 to-muted/40"
        />
      ))}
    </div>
  );
}

function toWatchlistEntry(item: WatchlistListItem): WatchlistEntry {
  const mediaId = String(item.media_id);
  return {
    id: item.id,
    mediaId,
    title: typeof item.title === "string" && item.title.trim().length > 0 ? item.title : "Untitled",
    releaseYear: toOptionalNumber(item.release_year),
    posterUrl: typeof item.poster_url === "string" ? item.poster_url : undefined,
    backdropUrl: typeof item.backdrop_url === "string" ? item.backdrop_url : undefined,
    trailerKey: extractTrailerKey((item as { trailer_url?: unknown }).trailer_url),
    genres: Array.isArray(item.genres)
      ? item.genres.filter((genre): genre is string => typeof genre === "string" && genre.trim().length > 0)
      : [],
    status: item.status,
    rating: item.rating ?? null,
    imdbRating: toOptionalNumber(item.imdb_rating) ?? null,
    rtRating: toOptionalNumber(item.rt_rating) ?? null,
    whySummary: typeof item.why_summary === "string" ? item.why_summary : null,
  };
}

function toOptionalNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function extractTrailerKey(value: unknown): string | undefined {
  if (typeof value !== "string" || value.trim().length === 0) return undefined;
  try {
    const url = new URL(value.trim());
    if (url.hostname.includes("youtu.be")) {
      const key = url.pathname.replace(/^\//, "");
      return key ? key : undefined;
    }
    if (url.hostname.includes("youtube.com")) {
      const v = url.searchParams.get("v");
      if (v && v.trim()) return v.trim();
      const segments = url.pathname.split("/").filter(Boolean);
      if (segments.length > 0) {
        const last = segments[segments.length - 1];
        return last || undefined;
      }
    }
    return undefined;
  } catch (error) {
    void error;
    return undefined;
  }
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const message = error.message?.trim();
    if (message) return message;
  }
  return fallback;
}
