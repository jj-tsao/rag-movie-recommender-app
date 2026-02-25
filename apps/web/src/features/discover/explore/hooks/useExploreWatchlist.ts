import { useCallback, useState } from "react";
import { useToast } from "@/components/ui/useToast";
import type { DiscoverCardData } from "@/features/discover/for_you/types";
import {
  createWatchlistItem,
  deleteWatchlistItem,
  lookupWatchlistKeys,
  updateWatchlist,
  type WatchlistStatus,
} from "@/features/watchlist/api";
import { toNumericMediaId } from "../../utils/parsing";

export type WatchlistButtonState = "loading" | "not_added" | "in_list";

export interface WatchlistUiState {
  state: WatchlistButtonState;
  status: WatchlistStatus | null;
  rating: number | null;
  id: string | null;
  busy: boolean;
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const message = error.message?.trim();
    if (message) return message;
  }
  return fallback;
}

export function useExploreWatchlist({ source }: { source: string }) {
  const { toast } = useToast();
  const [watchlistState, setWatchlistState] = useState<Record<string, WatchlistUiState>>({});

  const loadWatchlistState = useCallback(async (ids: string[]) => {
    const unique = Array.from(new Set(ids.filter(Boolean)));
    if (unique.length === 0) return;

    setWatchlistState((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const id of unique) {
        if (next[id]) continue;
        next[id] = { state: "loading", status: null, rating: null, id: null, busy: false };
        changed = true;
      }
      return changed ? next : prev;
    });

    const keys = unique
      .map((id) => toNumericMediaId(id))
      .filter((num): num is number => num !== null)
      .map((media_id) => ({ media_id, media_type: "movie" as const }));

    if (keys.length === 0) {
      setWatchlistState((prev) => {
        const next = { ...prev };
        unique.forEach((id) => {
          next[id] = { state: "not_added", status: null, rating: null, id: null, busy: false };
        });
        return next;
      });
      return;
    }

    try {
      const results = await lookupWatchlistKeys(keys);
      const map = new Map<number, (typeof results)[number]>();
      results.forEach((entry) => map.set(entry.media_id, entry));

      setWatchlistState((prev) => {
        const next = { ...prev };
        unique.forEach((id) => {
          const numeric = toNumericMediaId(id);
          const match = numeric !== null ? map.get(numeric) : undefined;
          next[id] =
            match && match.exists && match.id
              ? { state: "in_list", status: match.status ?? "want", rating: match.rating ?? null, id: match.id, busy: false }
              : { state: "not_added", status: null, rating: null, id: null, busy: false };
        });
        return next;
      });
    } catch (error) {
      console.warn("Failed to load watchlist state", error);
      setWatchlistState((prev) => {
        const next = { ...prev };
        unique.forEach((id) => {
          next[id] = { state: "not_added", status: null, rating: null, id: null, busy: false };
        });
        return next;
      });
    }
  }, []);

  const handleWatchlistAdd = useCallback(
    async (card: DiscoverCardData) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (entry && (entry.state === "loading" || entry.state === "in_list" || entry.busy)) {
        return;
      }

      const numericId = toNumericMediaId(card.mediaId);
      if (numericId === null) {
        toast({ title: "Unable to add", description: "We couldn't identify this title just yet.", variant: "destructive" });
        return;
      }

      setWatchlistState((prev) => ({
        ...prev,
        [card.mediaId]: {
          state: "in_list",
          status: "want",
          rating: entry?.rating ?? null,
          id: entry?.id ?? null,
          busy: true,
        },
      }));

      try {
        const result = await createWatchlistItem({
          media_id: numericId,
          media_type: "movie",
          status: "want",
          title: card.title,
          poster_url: card.posterUrl ?? null,
          backdrop_url: card.backdropUrl ?? null,
          trailer_url: card.trailerKey ? `https://www.youtube.com/watch?v=${card.trailerKey}` : null,
          release_year: card.releaseYear ?? null,
          genres: card.genres.length > 0 ? card.genres : null,
          imdb_rating: typeof card.imdbRating === "number" ? card.imdbRating : null,
          rt_rating: typeof card.rottenTomatoesRating === "number" ? card.rottenTomatoesRating : null,
          why_summary: card.whyMarkdown ?? card.whyText ?? null,
          source,
        });
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: { state: "in_list", status: result.status ?? "want", rating: result.rating ?? null, id: result.id, busy: false },
          };
        });
      } catch (error) {
        setWatchlistState((prev) => ({
          ...prev,
          [card.mediaId]: { state: "not_added", status: null, rating: null, id: null, busy: false },
        }));
        toast({ title: "Could not add to watchlist", description: toErrorMessage(error, "Please try again in a moment."), variant: "destructive" });
      }
    },
    [toast, watchlistState, source]
  );

  const handleWatchlistStatus = useCallback(
    async (card: DiscoverCardData, nextStatus: WatchlistStatus) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) return;
      const previousStatus = entry.status ?? "want";
      if (previousStatus === nextStatus) return;
      const snapshot: WatchlistUiState = { ...entry };
      const watchlistId = entry.id;

      setWatchlistState((prev) => {
        const existing = prev[card.mediaId];
        if (!existing) return prev;
        return {
          ...prev,
          [card.mediaId]: { ...existing, state: "in_list", status: nextStatus, rating: existing.rating ?? null, busy: true },
        };
      });

      try {
        const result = await updateWatchlist(watchlistId, { status: nextStatus });
        const updatedStatus = result.status ?? nextStatus;
        const updatedRating = result.rating ?? snapshot.rating ?? null;
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: { state: "in_list", status: updatedStatus, rating: updatedRating, id: result.id, busy: false },
          };
        });
      } catch (error) {
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return { ...prev, [card.mediaId]: { ...snapshot, busy: false } };
        });
        toast({ title: "Could not update watchlist", description: toErrorMessage(error, "Please try again in a moment."), variant: "destructive" });
      }
    },
    [toast, watchlistState]
  );

  const handleWatchlistRemove = useCallback(
    async (card: DiscoverCardData) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) return;
      const snapshot: WatchlistUiState = { ...entry };

      setWatchlistState((prev) => {
        const existing = prev[card.mediaId];
        if (!existing) return prev;
        return { ...prev, [card.mediaId]: { ...existing, busy: true } };
      });

      try {
        await deleteWatchlistItem(entry.id);
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: { state: "not_added", status: null, rating: null, id: null, busy: false },
          };
        });
      } catch (error) {
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return { ...prev, [card.mediaId]: snapshot };
        });
        toast({ title: "Could not remove from watchlist", description: toErrorMessage(error, "Please try again in a moment."), variant: "destructive" });
      }
    },
    [toast, watchlistState]
  );

  return {
    watchlistState,
    setWatchlistState,
    loadWatchlistState,
    handleWatchlistAdd,
    handleWatchlistStatus,
    handleWatchlistRemove,
  };
}