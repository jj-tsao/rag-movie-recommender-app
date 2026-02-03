import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import MovieCard from "@/components/MovieCard";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/useToast";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { getSessionId } from "@/utils/session";
import { mapStreamingServiceNamesToIds } from "@/data/streamingServices";
import GenreFilterChip from "../components/GenreFilterChip";
import type { DiscoverCardData } from "../types";
import {
  fetchDiscoverInitial,
  getAccessToken,
  logDiscoverFinalRecs,
  normalizeTomatoScore,
  streamDiscoverWhy,
  type DiscoverStreamEvent,
} from "../api";
import DiscoverGridSkeleton from "../components/DiscoverGridSkeleton";
import StreamStatusBar, { type StreamStatusState } from "../components/StreamStatusBar";
import StreamingServiceFilterChip from "../components/StreamingServiceFilterChip";
import {
  logUserRecReaction,
  upsertUserInteraction,
  type RatingValue,
} from "@/features/taste_onboarding/api";
import { rebuildTasteProfile } from "@/api";
import { hasTasteProfile, type TasteProfileHttpError } from "@/features/taste_profile/api";
import {
  createWatchlistItem,
  deleteWatchlistItem,
  lookupWatchlistKeys,
  updateWatchlist,
  type WatchlistStatus,
} from "@/features/watchlist/api";

type DiscoverRating = Exclude<RatingValue, "dismiss">;

function toDiscoverCard(item: {
  id?: string;
  media_id: number | string;
  title: string;
  release_year?: number | string | null;
  poster_url?: string | null;
  backdrop_url?: string | null;
  trailer_key?: string | null;
  genres?: unknown;
  providers?: unknown;
  why_md?: unknown;
  imdb_rating?: unknown;
  rotten_tomatoes_rating?: unknown;
  why_source?: unknown;
}): DiscoverCardData {
  const mediaId = normalizeMediaId(item.media_id);
  const whyMarkdown = toWhyMarkdown(item.why_md);
  const imdbRating = toOptionalRating(item.imdb_rating);
  const rottenTomatoesRating = normalizeTomatoScore(item.rotten_tomatoes_rating);
  const whySource = normalizeWhySource(item.why_source);
  const isCached = whySource === "cache";
  return {
    id: item.id,
    mediaId,
    title: item.title,
    releaseYear: toOptionalNumber(item.release_year),
    posterUrl: typeof item.poster_url === "string" ? item.poster_url : undefined,
    backdropUrl: typeof item.backdrop_url === "string" ? item.backdrop_url : undefined,
    trailerKey: typeof item.trailer_key === "string" ? item.trailer_key : undefined,
    genres: toStringArray(item.genres),
    providers: toStringArray(item.providers),
    imdbRating,
    rottenTomatoesRating,
    whyMarkdown,
    whyText: undefined,
    whySource,
    isWhyLoading: !whyMarkdown && !isCached,
    isRatingsLoading: !(isCached || imdbRating !== null || rottenTomatoesRating !== null),
  };
}

function normalizeMediaId(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.trim() !== "") {
    return value.trim();
  }
  return "";
}

function toNumericMediaId(value: string): number | null {
  if (!value) return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.trunc(numeric);
}

function toOptionalNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((entry) => {
      if (typeof entry === "string") return entry;
      if (entry && typeof entry === "object") {
        if ("name" in entry && typeof (entry as { name: unknown }).name === "string") {
          return (entry as { name: string }).name;
        }
        if ("provider" in entry && typeof (entry as { provider: unknown }).provider === "string") {
          return (entry as { provider: string }).provider;
        }
      }
      return null;
    })
    .filter((entry): entry is string => Boolean(entry));
}

function toOptionalRating(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.round(value * 10) / 10;
  }
  if (typeof value === "string") {
    const cleaned = value.trim().replace(/[^0-9.]/g, "");
    if (cleaned) {
      const parsed = Number(cleaned);
      if (Number.isFinite(parsed)) {
        return Math.round(parsed * 10) / 10;
      }
    }
  }
  return null;
}

function toWhyMarkdown(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function normalizeWhySource(value: unknown): "cache" | "llm" {
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "cache" || normalized === "llm") {
      return normalized;
    }
  }
  return "llm";
}

type CardMap = Record<string, DiscoverCardData>;

type PageState = "idle" | "loading" | "ready" | "error" | "unauthorized" | "missingTasteProfile";

type StreamPhase = StreamStatusState["status"];

type WatchlistButtonState = "loading" | "not_added" | "in_list";

interface WatchlistUiState {
  state: WatchlistButtonState;
  status: WatchlistStatus | null;
  rating: number | null;
  id: string | null;
  busy: boolean;
}

function isSameWatchlistEntry(a: WatchlistUiState | undefined, b: WatchlistUiState): boolean {
  if (!a) return false;
  return (
    a.state === b.state &&
    a.status === b.status &&
    a.rating === b.rating &&
    a.id === b.id &&
    a.busy === b.busy
  );
}

const RATING_COUNT_KEY = "rating_count";
const PENDING_REBUILD_KEY = "pending_rebuild";
const LAST_REBUILD_KEY = "last_rebuild_at";
const MIN_RATINGS_FOR_REBUILD = 2;
const REBUILD_DELAY_MS = 10_000;
const REBUILD_COOLDOWN_MS = 2 * 60 * 1000;
const WATCHLIST_SOURCE = "discover_for_you";
const DISCOVER_MEDIA_TYPE = "movie" as const;
const LOOKUP_TRIGGER_SIZE = 12;
const LOOKUP_MAX_BATCH = 20;
const LOOKUP_DEBOUNCE_MS = 300;

function parseStoredNumber(value: string | null): number | null {
  if (typeof value !== "string") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function isTruthyString(value: string | null): boolean {
  return value === "true" || value === "1";
}

class DiscoverRebuildController {
  private ratingTimer: ReturnType<typeof setTimeout> | null = null;
  private cooldownTimer: ReturnType<typeof setTimeout> | null = null;
  private ratingCount = 0;
  private pendingRebuild = false;
  private lastRebuildAt: number | null = null;
  private rebuildInFlight = false;
  private hydrated = false;

  hydrate() {
    if (typeof window === "undefined" || this.hydrated) return;

    const storedCount = parseStoredNumber(window.localStorage.getItem(RATING_COUNT_KEY));
    this.ratingCount = storedCount && storedCount > 0 ? Math.floor(storedCount) : 0;
    window.localStorage.setItem(RATING_COUNT_KEY, String(this.ratingCount));

    this.pendingRebuild = isTruthyString(window.localStorage.getItem(PENDING_REBUILD_KEY));

    const storedLast = parseStoredNumber(window.localStorage.getItem(LAST_REBUILD_KEY));
    this.lastRebuildAt = storedLast && storedLast > 0 ? storedLast : null;

    this.hydrated = true;
    this.resumeCooldown();
  }

  registerRating() {
    if (typeof window === "undefined") return;
    this.ratingCount += 1;
    window.localStorage.setItem(RATING_COUNT_KEY, String(this.ratingCount));
    this.startRatingTimer();
  }

  dispose() {
    if (this.ratingTimer) {
      clearTimeout(this.ratingTimer);
      this.ratingTimer = null;
    }
    if (this.cooldownTimer) {
      clearTimeout(this.cooldownTimer);
      this.cooldownTimer = null;
    }
  }

  private startRatingTimer() {
    if (typeof window === "undefined") return;
    if (this.ratingTimer) {
      clearTimeout(this.ratingTimer);
    }
    this.ratingTimer = setTimeout(() => {
      this.ratingTimer = null;
      if (this.ratingCount >= MIN_RATINGS_FOR_REBUILD) {
        void this.tryRebuild();
      }
    }, REBUILD_DELAY_MS);
  }

  private clearRatingTimer() {
    if (this.ratingTimer) {
      clearTimeout(this.ratingTimer);
      this.ratingTimer = null;
    }
  }

  private resumeCooldown() {
    if (typeof window === "undefined") return;
    if (this.cooldownTimer) {
      clearTimeout(this.cooldownTimer);
      this.cooldownTimer = null;
    }
    if (this.lastRebuildAt === null) {
      if (this.pendingRebuild && this.ratingCount >= MIN_RATINGS_FOR_REBUILD && !this.rebuildInFlight) {
        void this.tryRebuild();
      }
      return;
    }
    const remaining = REBUILD_COOLDOWN_MS - (Date.now() - this.lastRebuildAt);
    if (remaining <= 0) {
      if (this.pendingRebuild && !this.rebuildInFlight) {
        void this.tryRebuild();
      }
      return;
    }
    this.cooldownTimer = setTimeout(() => {
      this.cooldownTimer = null;
      if (this.pendingRebuild && !this.rebuildInFlight) {
        void this.tryRebuild();
      }
    }, remaining);
  }

  private async tryRebuild() {
    if (this.rebuildInFlight) return;
    if (typeof window === "undefined") return;
    if (this.ratingCount < MIN_RATINGS_FOR_REBUILD && !this.pendingRebuild) return;

    const now = Date.now();
    if (this.lastRebuildAt !== null && now - this.lastRebuildAt < REBUILD_COOLDOWN_MS) {
      if (!this.pendingRebuild) {
        this.pendingRebuild = true;
        window.localStorage.setItem(PENDING_REBUILD_KEY, "true");
      }
      this.resumeCooldown();
      return;
    }

    this.rebuildInFlight = true;

    try {
      await rebuildTasteProfile();
      this.ratingCount = 0;
      window.localStorage.setItem(RATING_COUNT_KEY, "0");
      this.pendingRebuild = false;
      window.localStorage.removeItem(PENDING_REBUILD_KEY);
      this.clearRatingTimer();
    } catch (error) {
      console.warn("Failed to rebuild taste profile from discover feed", error);
      this.pendingRebuild = true;
      window.localStorage.setItem(PENDING_REBUILD_KEY, "true");
    } finally {
      this.lastRebuildAt = now;
      window.localStorage.setItem(LAST_REBUILD_KEY, String(now));
      this.rebuildInFlight = false;
      this.resumeCooldown();
    }
  }
}

export default function ForYouPage() {
  const [pageState, setPageState] = useState<PageState>("idle");
  const [cards, setCards] = useState<CardMap>({});
  const [order, setOrder] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [streamState, setStreamState] = useState<StreamStatusState>({ status: "idle" });
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [feedbackById, setFeedbackById] = useState<Partial<Record<string, DiscoverRating>>>({});
  const [pendingFeedback, setPendingFeedback] = useState<Partial<Record<string, boolean>>>({});
  const [watchlistState, setWatchlistState] = useState<Record<string, WatchlistUiState>>({});
  const [activeRatingPrompt, setActiveRatingPrompt] = useState<string | null>(null);
  const [selectedProviders, setSelectedProviders] = useState<string[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
  const queryIdRef = useRef<string | null>(null);
  const loggedQueryIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lookupQueueRef = useRef<Set<string>>(new Set());
  const lookupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { toast } = useToast();
  const { user } = useAuth();
  const navigate = useNavigate();
  const rebuildControllerRef = useRef<DiscoverRebuildController | null>(null);

  if (!rebuildControllerRef.current) {
    rebuildControllerRef.current = new DiscoverRebuildController();
  }

  const rebuildController = rebuildControllerRef.current;

  useEffect(() => {
    rebuildController.hydrate();
    return () => {
      rebuildController.dispose();
    };
  }, [rebuildController]);

  useEffect(() => {
    return () => {
      if (lookupTimerRef.current) {
        clearTimeout(lookupTimerRef.current);
        lookupTimerRef.current = null;
      }
      lookupQueueRef.current.clear();
    };
  }, []);

  const orderedCards = useMemo(
    () => order.map((id) => cards[id]).filter((card): card is DiscoverCardData => Boolean(card)),
    [order, cards],
  );

  const selectedProviderIds = useMemo(
    () => mapStreamingServiceNamesToIds(selectedProviders),
    [selectedProviders],
  );
  const selectedGenresForQuery = useMemo(() => [...selectedGenres], [selectedGenres]);

  const flushLookupQueue = useCallback(async () => {
    if (lookupTimerRef.current) {
      clearTimeout(lookupTimerRef.current);
      lookupTimerRef.current = null;
    }

    const queue = lookupQueueRef.current;
    if (queue.size === 0) {
      return;
    }

    const batchIds: string[] = [];
    for (const id of queue) {
      batchIds.push(id);
      queue.delete(id);
      if (batchIds.length >= LOOKUP_MAX_BATCH) {
        break;
      }
    }

    if (batchIds.length === 0) {
      return;
    }

    const mapped = batchIds
      .map((id) => {
        const numericId = toNumericMediaId(id);
        if (numericId === null) return null;
        return { mediaId: id, numericId };
      })
      .filter((entry): entry is { mediaId: string; numericId: number } => entry !== null);

    if (mapped.length === 0) {
      if (queue.size > 0) {
        lookupTimerRef.current = setTimeout(() => {
          void flushLookupQueue();
        }, LOOKUP_DEBOUNCE_MS);
      }
      return;
    }

    const keys = mapped.map(({ numericId }) => ({
      media_id: numericId,
      media_type: "movie" as const,
    }));

    try {
      const results = await lookupWatchlistKeys(keys);
      const resultMap = new Map<number, (typeof results)[number]>();
      for (const result of results) {
        resultMap.set(result.media_id, result);
      }

      setWatchlistState((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const { mediaId, numericId } of mapped) {
          const current = next[mediaId];
          if (!current) continue;
          const match = resultMap.get(numericId);
          const entry: WatchlistUiState =
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
          if (!isSameWatchlistEntry(current, entry)) {
            next[mediaId] = entry;
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    } catch (error) {
      console.warn("Watchlist lookup failed", error);
      setWatchlistState((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const { mediaId } of mapped) {
          const current = next[mediaId];
          if (!current) continue;
          const entry: WatchlistUiState = {
            state: "not_added",
            status: null,
            rating: null,
            id: null,
            busy: false,
          };
          if (!isSameWatchlistEntry(current, entry)) {
            next[mediaId] = entry;
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    } finally {
      if (queue.size > 0) {
        lookupTimerRef.current = setTimeout(() => {
          void flushLookupQueue();
        }, LOOKUP_DEBOUNCE_MS);
      }
    }
  }, [lookupWatchlistKeys]);

  const enqueueWatchlistLookup = useCallback(
    (ids: string[]) => {
      if (ids.length === 0) return;
      const queue = lookupQueueRef.current;
      let added = false;
      ids.forEach((id) => {
        if (!id) return;
        if (!queue.has(id)) {
          queue.add(id);
          added = true;
        }
      });
      if (!added) return;
      if (queue.size >= LOOKUP_TRIGGER_SIZE) {
        void flushLookupQueue();
        return;
      }
      if (lookupTimerRef.current) {
        clearTimeout(lookupTimerRef.current);
      }
      lookupTimerRef.current = setTimeout(() => {
        void flushLookupQueue();
      }, LOOKUP_DEBOUNCE_MS);
    },
    [flushLookupQueue],
  );

  const ensureWatchlistEntries = useCallback(
    (ids: string[]) => {
      if (ids.length === 0) return;
      const unique = Array.from(new Set(ids.filter((id): id is string => Boolean(id))));
      if (unique.length === 0) return;

      setWatchlistState((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const id of unique) {
          if (next[id]) continue;
          next[id] = {
            state: "loading",
            status: null,
            rating: null,
            id: null,
            busy: false,
          };
          changed = true;
        }
        return changed ? next : prev;
      });

      enqueueWatchlistLookup(unique);
    },
    [enqueueWatchlistLookup],
  );

  const openRatingPrompt = useCallback((mediaId: string) => {
    if (!mediaId) return;
    setActiveRatingPrompt(mediaId);
  }, []);

  const closeRatingPrompt = useCallback((mediaId?: string) => {
    setActiveRatingPrompt((current) => {
      if (!current) return current;
      if (!mediaId || current === mediaId) {
        return null;
      }
      return current;
    });
  }, []);

  useEffect(() => {
    if (order.length === 0) return;
    const missing: string[] = [];
    for (const id of order) {
      if (!id) continue;
      if (!watchlistState[id]) {
        missing.push(id);
      }
    }
    if (missing.length > 0) {
      ensureWatchlistEntries(missing);
    }
  }, [order, watchlistState, ensureWatchlistEntries]);

  useEffect(() => {
    if (!activeRatingPrompt) return;
    const entry = watchlistState[activeRatingPrompt];
    if (!entry) {
      closeRatingPrompt(activeRatingPrompt);
      return;
    }
    if (entry.state !== "in_list") {
      closeRatingPrompt(activeRatingPrompt);
      return;
    }
    if (entry.status !== "watched" && entry.rating === null) {
      closeRatingPrompt(activeRatingPrompt);
      return;
    }
  }, [activeRatingPrompt, watchlistState, closeRatingPrompt]);

  const handleStreamEvent = useCallback((event: DiscoverStreamEvent) => {
    if (event.type === "started") {
      setStreamState({ status: "streaming", message: "Streaming reasons…" });
      return;
    }
    if (event.type === "progress") {
      const message = typeof event.data?.message === "string" ? event.data.message : "Still thinking…";
      setStreamState((prev) => ({
        status: prev.status === "idle" ? "streaming" : prev.status,
        message,
      }));
      return;
    }
    if (event.type === "why_delta") {
      const mediaId = normalizeMediaId(event.data.media_id);
      if (!mediaId) return;
      setCards((prev) => {
        const next = { ...prev };
        const existing = next[mediaId];
        if (!existing) return prev;
        next[mediaId] = {
          ...existing,
          imdbRating:
            event.data.imdb_rating !== undefined ? event.data.imdb_rating ?? null : existing.imdbRating,
          rottenTomatoesRating:
            event.data.rotten_tomatoes_rating !== undefined
              ? event.data.rotten_tomatoes_rating ?? null
              : existing.rottenTomatoesRating,
          whyMarkdown: event.data.why_you_might_enjoy_it ?? existing.whyMarkdown,
          whyText: event.data.why_you_might_enjoy_it ? undefined : existing.whyText,
          whySource: existing.whySource ?? "llm",
          isWhyLoading: event.data.why_you_might_enjoy_it ? false : existing.isWhyLoading,
          isRatingsLoading:
            event.data.imdb_rating !== undefined || event.data.rotten_tomatoes_rating !== undefined
              ? false
              : existing.isRatingsLoading,
        };
        return next;
      });
      return;
    }
    if (event.type === "done") {
      setStreamState({ status: "done", message: "Finished streaming" });
      setCards((prev) => finalizePending(prev));
      return;
    }
    if (event.type === "error") {
      const message = typeof event.data?.message === "string" ? event.data.message : "Stream error";
      const errorId = typeof event.data?.error_id === "string" ? event.data.error_id : null;
      setStreamState({ status: "error", message: errorId ? `${message} (Ref ${errorId})` : message });
      setCards((prev) => finalizePending(prev));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setPageState("loading");
      setErrorMessage(null);
      setStreamState({ status: "idle" });
      abortRef.current?.abort();
      lookupQueueRef.current.clear();
      if (lookupTimerRef.current) {
        clearTimeout(lookupTimerRef.current);
        lookupTimerRef.current = null;
      }
      setWatchlistState({});
      closeRatingPrompt();
      const sessionId = getSessionId();
      const queryId = `${sessionId}_${Date.now()}`;
      queryIdRef.current = queryId;
      loggedQueryIdRef.current = null;

      try {
        const token = await getAccessToken();
        if (!token) {
          if (!cancelled) {
            setPageState("unauthorized");
            setErrorMessage("Sign in to view your discovery feed.");
            setCards({});
            setOrder([]);
          }
          return;
        }

        let profileExists = false;
        try {
          profileExists = await hasTasteProfile(token);
        } catch (profileError) {
          if (cancelled) return;
          const status = (profileError as TasteProfileHttpError | undefined)?.status;
          if (status === 401 || status === 403) {
            setPageState("unauthorized");
            setErrorMessage("Sign in to view your discovery feed.");
            setCards({});
            setOrder([]);
            return;
          }
          throw profileError;
        }

        if (!profileExists) {
          if (!cancelled) {
            setCards({});
            setOrder([]);
            abortRef.current = null;
            setStreamState({ status: "idle" });
            setPageState("missingTasteProfile");
          }
          return;
        }

        const response = await fetchDiscoverInitial(token, {
          sessionId,
          queryId,
          mediaType: "movie",
          page: 1,
          pageSize: 12,
          includeWhy: false,
          providerIds: selectedProviderIds,
          genres: selectedGenresForQuery,
        });
        if (cancelled) return;

        const mapped: CardMap = {};
        response.items.forEach((item) => {
          const card = toDiscoverCard(item);
          if (!card.mediaId) return;
          mapped[card.mediaId] = card;
        });
        const newOrder = response.items
          .map((item) => normalizeMediaId(item.media_id))
          .filter((id): id is string => Boolean(id));
        setCards(mapped);
        setOrder(newOrder);
        ensureWatchlistEntries(newOrder);
        setPageState("ready");

        if (response.stream_url) {
          const controller = new AbortController();
          abortRef.current = controller;
          setStreamState({ status: "connecting", message: "Waiting for live insights…" });
          try {
            await streamDiscoverWhy({
              token,
              streamUrl: response.stream_url,
              signal: controller.signal,
              onEvent: handleStreamEvent,
            });
            if (!controller.signal.aborted) {
              setStreamState((prev) => (prev.status === "done" ? prev : { status: "done", message: "Stream complete" }));
              setCards((prev) => finalizePending(prev));
            }
          } catch (error) {
            if (controller.signal.aborted) {
              setStreamState({ status: "cancelled", message: "Stream cancelled" });
            } else {
              const message = error instanceof Error ? error.message : "Failed to stream insights";
              setStreamState({ status: "error", message });
            }
            setCards((prev) => finalizePending(prev));
          } finally {
            abortRef.current = null;
          }
        } else {
          setStreamState({ status: "done", message: "Loaded personalized picks from cache" });
          setCards((prev) => finalizePending(prev));
        }
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Failed to load discovery feed";
        setErrorMessage(message);
        setPageState("error");
      }
    };

    void load();

    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [refreshIndex, handleStreamEvent, ensureWatchlistEntries, selectedProviderIds, selectedGenresForQuery]);

  const streamPhase: StreamPhase = streamState.status;
  const canCancel = streamPhase === "connecting" || streamPhase === "streaming";

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handleRetry = useCallback(() => {
    setRefreshIndex((idx) => idx + 1);
  }, []);

  useEffect(() => {
    if (streamState.status !== "done") return;
    const queryId = queryIdRef.current;
    if (!queryId) return;
    if (loggedQueryIdRef.current === queryId) return;

    const finalRecs = orderedCards
      .map((card) => {
        const mediaId = toNumericMediaId(card.mediaId);
        if (mediaId === null) return null;
        const why = (card.whyMarkdown ?? card.whyText ?? "").trim();
        if (!why) return null;
        const whySource = normalizeWhySource(card.whySource);
        const imdbRating = typeof card.imdbRating === "number" && Number.isFinite(card.imdbRating) ? card.imdbRating : null;
        const rtRating =
          typeof card.rottenTomatoesRating === "number" && Number.isFinite(card.rottenTomatoesRating)
            ? Math.round(card.rottenTomatoesRating)
            : null;
        return {
          media_id: mediaId,
          why,
          imdb_rating: imdbRating,
          rt_rating: rtRating,
          why_source: whySource,
        };
      })
      .filter(
        (
          entry,
        ): entry is {
          media_id: number;
          why: string;
          imdb_rating: number | null;
          rt_rating: number | null;
          why_source: "cache" | "llm";
        } => entry !== null,
      );

    if (finalRecs.length === 0) return;

    loggedQueryIdRef.current = queryId;
    void logDiscoverFinalRecs({
      queryId,
      mediaType: DISCOVER_MEDIA_TYPE,
      finalRecs,
    }).catch((error) => {
      console.warn("Failed to log discovery final recommendations", error);
    });
  }, [orderedCards, streamState.status]);

  const handleFeedback = useCallback(
    async (card: DiscoverCardData, rating: DiscoverRating) => {
      if (!card.mediaId) return;
      const id = card.mediaId;
      const previous = feedbackById[id];
      if (previous === rating) return;

      setFeedbackById((prev) => ({ ...prev, [id]: rating }));
      setPendingFeedback((prev) => ({ ...prev, [id]: true }));

      const rankingIndex = order.findIndex((mediaId) => mediaId === id);
      const position = rankingIndex >= 0 ? rankingIndex + 1 : null;
      const queryId = queryIdRef.current;

      try {
        await logUserRecReaction({
          mediaId: card.mediaId,
          title: card.title,
          reaction: rating,
          source: "for_you_feed",
          mediaType: "movie",
          position,
          queryId,
        });
        rebuildController?.registerRating();
      } catch (error) {
        setFeedbackById((prev) => {
          const next = { ...prev };
          if (previous) {
            next[id] = previous;
          } else {
            delete next[id];
          }
          return next;
        });
        const message = error instanceof Error ? error.message : "Could not save feedback";
        toast({ title: "Feedback not saved", description: message, variant: "destructive" });
      } finally {
        setPendingFeedback((prev) => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }
    },
    [feedbackById, order, toast, rebuildController],
  );

  const handleTrailerClick = useCallback(
    (card: DiscoverCardData) => {
      if (!card.mediaId) return;
      void upsertUserInteraction(
        {
          media_id: card.mediaId,
          title: card.title,
          vibes: card.genres,
          eventType: "trailer_view",
          weightOverride: 0.35,
        },
        { source: "for_you_feed" },
      ).catch((error) => {
        const message = error instanceof Error ? error.message : "Could not log trailer view";
        toast({ title: "Logging failed", description: message, variant: "destructive" });
      });
    },
    [toast],
  );

  const handleWatchlistAdd = useCallback(
    async (card: DiscoverCardData) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (entry && (entry.state === "loading" || entry.state === "in_list" || entry.busy)) {
        return;
      }

      const numericId = toNumericMediaId(card.mediaId);
      if (numericId === null) {
        toast({
          title: "Unable to add",
          description: "We couldn't identify this title just yet.",
          variant: "destructive",
        });
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
          source: WATCHLIST_SOURCE,
        });
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: {
              state: "in_list",
              status: result.status ?? "want",
              rating: result.rating ?? null,
              id: result.id,
              busy: false,
            },
          };
        });
      } catch (error) {
        setWatchlistState((prev) => ({
          ...prev,
          [card.mediaId]: {
            state: "not_added",
            status: null,
            rating: null,
            id: null,
            busy: false,
          },
        }));
        toast({
          title: "Could not add to watchlist",
          description: toErrorMessage(error, "Please try again in a moment."),
          variant: "destructive",
        });
      }
    },
    [toast, watchlistState],
  );

  const handleWatchlistStatus = useCallback(
    async (card: DiscoverCardData, nextStatus: WatchlistStatus) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) {
        return;
      }
      const previousStatus = entry.status ?? "want";
      if (previousStatus === nextStatus) {
        return;
      }
      const snapshot: WatchlistUiState = { ...entry };
      const watchlistId = entry.id;

      if (nextStatus !== "watched") {
        closeRatingPrompt(card.mediaId);
      }

      setWatchlistState((prev) => {
        const existing = prev[card.mediaId];
        if (!existing) return prev;
        return {
          ...prev,
          [card.mediaId]: {
            ...existing,
            state: "in_list",
            status: nextStatus,
            rating: existing.rating ?? null,
            busy: true,
          },
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
            [card.mediaId]: {
              state: "in_list",
              status: updatedStatus,
              rating: updatedRating,
              id: result.id,
              busy: false,
            },
          };
        });
        if (updatedStatus === "watched" && (updatedRating === null || updatedRating === 0)) {
          openRatingPrompt(card.mediaId);
        } else {
          closeRatingPrompt(card.mediaId);
        }
      } catch (error) {
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: {
              ...snapshot,
              busy: false,
            },
          };
        });
        toast({
          title: "Could not update watchlist",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [toast, watchlistState, closeRatingPrompt, openRatingPrompt],
  );

  const handleWatchlistRating = useCallback(
    async (card: DiscoverCardData, ratingValue: number) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) {
        return;
      }
      if (!Number.isFinite(ratingValue) || ratingValue < 1 || ratingValue > 10) {
        return;
      }
      const normalized = Math.min(10, Math.max(1, Math.round(ratingValue)));
      const snapshot: WatchlistUiState = { ...entry };

      setWatchlistState((prev) => {
        const existing = prev[card.mediaId];
        if (!existing) return prev;
        return {
          ...prev,
          [card.mediaId]: {
            ...existing,
            rating: normalized,
            busy: true,
          },
        };
      });

      closeRatingPrompt(card.mediaId);

      try {
        const result = await updateWatchlist(entry.id, { rating: normalized });
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: {
              ...existing,
              status: result.status ?? existing.status,
              rating: result.rating ?? normalized,
              id: result.id,
              busy: false,
            },
          };
        });
      } catch (error) {
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: {
              ...existing,
              rating: snapshot.rating,
              busy: false,
            },
          };
        });
        toast({
          title: "Could not save rating",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [watchlistState, closeRatingPrompt, toast],
  );

  const handleWatchlistRatingSkip = useCallback(
    (card: DiscoverCardData) => {
      if (!card.mediaId) return;
      closeRatingPrompt(card.mediaId);
    },
    [closeRatingPrompt],
  );

  const handleWatchlistRatingClear = useCallback(
    async (card: DiscoverCardData) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) {
        closeRatingPrompt(card.mediaId);
        return;
      }
      if (entry.rating === null) {
        closeRatingPrompt(card.mediaId);
        return;
      }

      const snapshot = { ...entry };

      setWatchlistState((prev) => {
        const existing = prev[card.mediaId];
        if (!existing) return prev;
        return {
          ...prev,
          [card.mediaId]: {
            ...existing,
            rating: null,
            busy: true,
          },
        };
      });

      closeRatingPrompt(card.mediaId);

      try {
        const result = await updateWatchlist(entry.id, { rating: null });
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: {
              state: "in_list",
              status: result.status ?? existing.status,
              rating: result.rating ?? null,
              id: result.id,
              busy: false,
            },
          };
        });
      } catch (error) {
        setWatchlistState((prev) => ({
          ...prev,
          [card.mediaId]: snapshot,
        }));
        toast({
          title: "Could not clear rating",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [watchlistState, closeRatingPrompt, toast],
  );

  const handleWatchlistRemove = useCallback(
    async (card: DiscoverCardData) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) {
        return;
      }
      const snapshot: WatchlistUiState = { ...entry };

      closeRatingPrompt(card.mediaId);

      setWatchlistState((prev) => {
        const existing = prev[card.mediaId];
        if (!existing) return prev;
        return {
          ...prev,
          [card.mediaId]: {
            state: "not_added",
            status: null,
            rating: null,
            id: null,
            busy: true,
          },
        };
      });

      try {
        await deleteWatchlistItem(snapshot.id as string);
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: {
              state: "not_added",
              status: null,
              rating: null,
              id: null,
              busy: false,
            },
          };
        });
      } catch (error) {
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: {
              ...snapshot,
              busy: false,
            },
          };
        });
        toast({
          title: "Could not remove from watchlist",
          description: toErrorMessage(error, "Please try again in a moment."),
          variant: "destructive",
        });
      }
    },
    [toast, watchlistState],
  );

  const handleStartTasteOnboarding = useCallback(() => {
    const target = user ? "/taste" : "/taste?first_run=1";
    navigate(target);
  }, [navigate, user]);

  const handleProviderFilterApply = useCallback((providers: string[]) => {
    setSelectedProviders(providers);
  }, []);

  const handleGenreFilterApply = useCallback((genres: string[]) => {
    setSelectedGenres(genres);
  }, []);

  return (
    <section className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pb-24 pt-8">
      <header className="flex flex-col gap-2">
        <h1 className="font-display text-3xl font-bold leading-tight text-foreground sm:text-4xl">For You</h1>
        <p className="text-sm text-muted-foreground">
          Fresh picks tailored to your taste. Updated live as our agent reasons in real time.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <StreamingServiceFilterChip selected={selectedProviders} onApply={handleProviderFilterApply} />
        <GenreFilterChip selected={selectedGenres} onApply={handleGenreFilterApply} />
      </div>

      {pageState === "loading" && <DiscoverGridSkeleton count={12} />}

      {pageState === "unauthorized" && (
        <div className="rounded-xl border border-dashed border-border bg-background/60 p-8 text-center">
          <p className="mb-4 text-sm text-muted-foreground">{errorMessage ?? "Sign in to continue."}</p>
          <Button onClick={handleRetry} variant="outline">
            Retry
          </Button>
        </div>
      )}

      {pageState === "error" && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-6 text-sm text-destructive">
          {errorMessage}
          <div className="mt-4">
            <Button onClick={handleRetry} variant="ghost">
              Try again
            </Button>
          </div>
        </div>
      )}

      {pageState === "ready" && orderedCards.length === 0 && (
        <div className="rounded-xl border border-border bg-background/60 p-8 text-center text-sm text-muted-foreground">
          No recommendations available right now. Try refreshing in a moment.
        </div>
      )}

      {pageState === "missingTasteProfile" && (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-border bg-background/60 px-8 py-12 text-center">
          <h2 className="text-xl font-semibold text-foreground">Build your taste profile</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            Take a minute to share what you enjoy watching so we can personalize your discovery feed.
          </p>
          <div className="flex flex-col items-center gap-2">
            <Button className="rounded-full px-6" size="lg" onClick={handleStartTasteOnboarding}>
              Personalize my feed
            </Button>
            <span className="text-xs text-muted-foreground">Takes under a minute. No sign-up needed.</span>
          </div>
        </div>
      )}

      {orderedCards.length > 0 && (
        <div className="flex flex-col gap-4 animate-fade-in">
          {orderedCards.map((cardData) => {
            const { mediaId, ...movieCard } = cardData;
            const entry = mediaId ? watchlistState[mediaId] : undefined;
            const watchlistProps = mediaId
              ? {
                  state: entry?.state ?? "loading",
                  status: entry?.status ?? null,
                  rating: entry?.rating ?? null,
                  busy: entry?.busy ?? false,
                  onAdd: () => handleWatchlistAdd(cardData),
                  onSelectStatus: (status: WatchlistStatus) => handleWatchlistStatus(cardData, status),
                  onRemove: () => handleWatchlistRemove(cardData),
                  showRatingPrompt: activeRatingPrompt === mediaId,
                  onRatingSelect: (value: number) => handleWatchlistRating(cardData, value),
                  onRatingSkip: () => handleWatchlistRatingSkip(cardData),
                  onRatingPromptOpen: () => openRatingPrompt(mediaId),
                  onRatingClear: () => handleWatchlistRatingClear(cardData),
                }
              : undefined;

            return (
              <MovieCard
                key={mediaId}
                movie={{
                  ...movieCard,
                  imdbRating: movieCard.imdbRating ?? undefined,
                  rottenTomatoesRating: movieCard.rottenTomatoesRating ?? undefined,
                }}
                feedback={{
                  value: mediaId ? feedbackById[mediaId] : undefined,
                  disabled: mediaId ? pendingFeedback[mediaId] ?? false : false,
                  onChange: (value) => handleFeedback(cardData, value),
                }}
                watchlist={watchlistProps}
                onTrailerClick={() => handleTrailerClick(cardData)}
                layout="wide"
              />
            );
          })}
        </div>
      )}

      {pageState !== "missingTasteProfile" && (
        <StreamStatusBar state={streamState} onCancel={canCancel ? handleCancel : undefined} />
      )}
    </section>
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

function finalizePending(map: CardMap): CardMap {
  const next: CardMap = {};
  for (const [key, value] of Object.entries(map)) {
    next[key] = {
      ...value,
      isWhyLoading: false,
      isRatingsLoading: false,
    };
  }
  return next;
}
