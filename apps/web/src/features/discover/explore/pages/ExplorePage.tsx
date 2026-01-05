import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import MovieCard from "@/components/MovieCard";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/useToast";
import StreamingServiceFilterChip from "@/features/discover/for_you/components/StreamingServiceFilterChip";
import YearRangeFilterChip from "../components/YearRangeFilterChip";
import DiscoverGridSkeleton from "@/features/discover/for_you/components/DiscoverGridSkeleton";
import type { DiscoverCardData } from "@/features/discover/for_you/types";
import { EXAMPLE_CHIPS } from "@/features/landing/data/example_chips";
import {
  getStreamingServiceOptions,
  mapStreamingServiceNamesToIds,
} from "@/data/streamingServices";
import { WATCH_PROVIDERS } from "@/data/watchProviders";
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
import { getSessionId } from "@/utils/session";
import { getDeviceInfo } from "@/utils/detectDevice";
import { setExploreRedirectFlag } from "@/utils/exploreRedirect";
import {
  getAccessToken,
  mapToRatings,
  rerunExplore,
  streamExplore,
  streamExploreWhy,
  type ExploreStreamEvent,
  type ExploreWhyEvent,
  type ActiveSpecEnvelope,
} from "../api";

type ExploreRating = Exclude<RatingValue, "dismiss">;
type PageState =
  | "idle"
  | "loading"
  | "recs"
  | "chat"
  | "error"
  | "unauthorized";

type WatchlistButtonState = "loading" | "not_added" | "in_list";

interface WatchlistUiState {
  state: WatchlistButtonState;
  status: WatchlistStatus | null;
  rating: number | null;
  id: string | null;
  busy: boolean;
}

const HERO_HELPER_ID = "explore-helper";
const WATCHLIST_SOURCE = "discovery_explore";
const DEFAULT_YEAR_RANGE: [number, number] = [1970, 2025];
const PROVIDER_NAME_BY_ID = new Map<number, string>(
  getStreamingServiceOptions()
    .filter((opt) => typeof opt.id === "number")
    .map((opt) => [opt.id as number, opt.name])
);

function normalizeMediaId(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "string" && value.trim() !== "") {
    return value.trim();
  }
  return null;
}

function toGenres(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((entry) => {
      if (typeof entry === "string") return entry;
      if (
        entry &&
        typeof entry === "object" &&
        "name" in entry &&
        typeof (entry as { name: unknown }).name === "string"
      ) {
        return (entry as { name: string }).name;
      }
      return null;
    })
    .filter((entry): entry is string => Boolean(entry));
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const message = error.message?.trim();
    if (message) return message;
  }
  return fallback;
}

function finalizeWhyLoading(
  map: Record<string, DiscoverCardData>
): Record<string, DiscoverCardData> {
  const next = { ...map };
  let changed = false;
  for (const key of Object.keys(next)) {
    const card = next[key];
    if (card.isWhyLoading) {
      next[key] = { ...card, isWhyLoading: false };
      changed = true;
    }
  }
  return changed ? next : map;
}

function providerIdsToNames(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const ids = value.filter((id): id is number => typeof id === "number");
  const names: string[] = [];
  const fallbackMap = new Map<number, string>();
  WATCH_PROVIDERS.forEach((provider) => {
    fallbackMap.set(provider.provider_id, provider.provider_name);
  });
  ids.forEach((id) => {
    const name = PROVIDER_NAME_BY_ID.get(id) ?? fallbackMap.get(id);
    if (name) {
      names.push(name);
    }
  });
  return Array.from(new Set(names));
}

function providersFromActiveSpec(envelope: ActiveSpecEnvelope | null | undefined): string[] {
  if (!envelope) return [];
  const chip = envelope.chips?.find((c) => c.key === "providers");
  if (chip && Array.isArray(chip.value)) {
    const names = providerIdsToNames(chip.value);
    if (names.length > 0) return names;
  }
  const ids = envelope.active_spec?.providers ?? [];
  return providerIdsToNames(ids);
}

function yearRangeFromActiveSpec(
  envelope: ActiveSpecEnvelope | null | undefined
): [number, number] | null {
  if (!envelope) return null;
  const chip = envelope.chips?.find((c) => c.key === "year_range");
  const source = typeof chip?.source === "string" ? chip.source.toLowerCase() : null;
  if (chip && Array.isArray(chip.value)) {
    const nums = chip.value.filter((v): v is number => typeof v === "number");
    if (nums.length === 2 && source === "user") {
      const [a, b] = nums;
      const start = Math.max(DEFAULT_YEAR_RANGE[0], Math.min(a, b));
      const end = Math.min(DEFAULT_YEAR_RANGE[1], Math.max(a, b));
      return [start, end];
    }
    if (source === "system") {
      return null;
    }
  }
  if (source === "system") {
    return null;
  }
  const yr = envelope.active_spec?.year_range;
  if (Array.isArray(yr) && yr.length === 2 && source === "user") {
    const [a, b] = yr;
    const start = Math.max(DEFAULT_YEAR_RANGE[0], Math.min(a, b));
    const end = Math.min(DEFAULT_YEAR_RANGE[1], Math.max(a, b));
    return [start, end];
  }
  return null;
}

interface SearchFormProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value?: string) => void;
  disabled?: boolean;
  helperId?: string;
  autoFocus?: boolean;
  showExamples?: boolean;
}

function ExploreSearchForm({
  value,
  onChange,
  onSubmit,
  disabled,
  helperId,
  autoFocus,
  showExamples = false,
}: SearchFormProps) {
  const [showAllChips, setShowAllChips] = useState(false);
  const visibleChips = useMemo(
    () => (showAllChips ? EXAMPLE_CHIPS : EXAMPLE_CHIPS.slice(0, 4)),
    [showAllChips]
  );

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <div className="w-full space-y-3">
      <form
        onSubmit={handleSubmit}
        role="search"
        className="w-full"
        aria-describedby={helperId}
      >
        <label className="sr-only" htmlFor="explore-query-input">
          Describe what you want to watch
        </label>
        <div className="flex w-full items-center gap-2 rounded-full border border-border/70 bg-background/90 px-4 py-3 shadow-inner transition focus-within:border-primary focus-within:ring-1 focus-within:ring-primary">
          <input
            id="explore-query-input"
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Describe a vibe or tap an example to jumpstart your picks."
            className="w-full bg-transparent text-base text-foreground placeholder:text-muted-foreground focus:outline-none"
            aria-label="Explore by vibe"
            autoComplete="off"
            disabled={disabled}
            autoFocus={autoFocus}
          />
          <button
            type="submit"
            disabled={disabled}
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

      {showExamples ? (
        <>
          <div
            className="flex flex-wrap items-center justify-center gap-2"
            aria-live="polite"
            id="explore-chip-list"
          >
            {visibleChips.map((text) => (
              <button
                key={text}
                type="button"
                onClick={() => {
                  onChange(text);
                  onSubmit(text);
                }}
                disabled={disabled}
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
                onClick={() => setShowAllChips((v) => !v)}
                className="inline-flex items-center rounded-full border border-border/70 bg-background/80 px-3 py-1.5 text-xs text-muted-foreground transition hover:border-primary/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                aria-expanded={showAllChips}
                aria-controls="explore-chip-list"
              >
                {showAllChips ? "Show less" : "More..."}
              </button>
            ) : null}
          </div>

          {helperId ? (
            <span id={helperId} className="block text-xs text-muted-foreground text-center" />
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export default function ExplorePage() {
  const location = useLocation();
  const { toast } = useToast();
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [pageState, setPageState] = useState<PageState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [intro, setIntro] = useState("");
  const [chatMessage, setChatMessage] = useState("");
  const [cards, setCards] = useState<Record<string, DiscoverCardData>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [isExploreStreaming, setIsExploreStreaming] = useState(false);
  const [isWhyStreaming, setIsWhyStreaming] = useState(false);
  const [isAwaitingRecs, setIsAwaitingRecs] = useState(false);
  const [hasRecsResponse, setHasRecsResponse] = useState(false);
  const [feedbackById, setFeedbackById] = useState<
    Partial<Record<string, ExploreRating>>
  >({});
  const [pendingFeedback, setPendingFeedback] = useState<
    Record<string, boolean>
  >({});
  const [watchlistState, setWatchlistState] = useState<
    Record<string, WatchlistUiState>
  >({});
  const [selectedProviders, setSelectedProviders] = useState<string[]>([]);
  const [selectedYearRange, setSelectedYearRange] = useState<[number, number] | null>(null);
  const [filtersReady, setFiltersReady] = useState(false);
  const queryIdRef = useRef<string | null>(null);
  const autoSubmitRef = useRef<string | null>(null);
  const exploreAbortRef = useRef<AbortController | null>(null);
  const whyAbortRef = useRef<AbortController | null>(null);

  const deviceInfo = useMemo(() => getDeviceInfo(), []);
  const selectedProviderIds = useMemo(
    () => mapStreamingServiceNamesToIds(selectedProviders),
    [selectedProviders]
  );
  const selectedYearRangeForQuery = useMemo(
    () => (selectedYearRange ? [...selectedYearRange] as [number, number] : null),
    [selectedYearRange]
  );
  const activeProviderIdsRef = useRef<number[]>([]);
  const activeYearRangeRef = useRef<[number, number] | null>(null);
  const orderedCards = useMemo(
    () => order.map((id) => cards[id]).filter(Boolean),
    [order, cards]
  );
  const lastSessionIdRef = useRef<string | null>(null);
  const hasSearched = pageState !== "idle";
  const isBusy =
    pageState === "loading" || isExploreStreaming || isWhyStreaming;

  const handleWhyStreamEvent = useCallback((event: ExploreWhyEvent) => {
    if (event.type === "started") {
      setIsWhyStreaming(true);
      return;
    }
    if (event.type === "why_delta") {
      const mediaId = normalizeMediaId(event.data.media_id);
      if (!mediaId) return;
      setCards((prev) => {
        const existing = prev[mediaId];
        if (!existing) return prev;
        return {
          ...prev,
          [mediaId]: {
            ...existing,
            whyMarkdown:
              event.data.why_you_might_enjoy_it ?? existing.whyMarkdown,
            whyText: event.data.why_you_might_enjoy_it
              ? undefined
              : existing.whyText,
            isWhyLoading: false,
          },
        };
      });
      return;
    }
    if (event.type === "done") {
      setIsWhyStreaming(false);
      setCards((prev) => finalizeWhyLoading(prev));
      return;
    }
    if (event.type === "error") {
      setIsWhyStreaming(false);
      setCards((prev) => finalizeWhyLoading(prev));
    }
  }, []);

  const toNumericMediaId = useCallback((value: string): number | null => {
    if (!value) return null;
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return null;
    return Math.trunc(numeric);
  }, []);

  const loadWatchlistState = useCallback(
    async (ids: string[]) => {
      const unique = Array.from(new Set(ids.filter(Boolean)));
      if (unique.length === 0) return;

      setWatchlistState((prev) => {
        const next = { ...prev };
        let changed = false;
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

      const keys = unique
        .map((id) => toNumericMediaId(id))
        .filter((num): num is number => num !== null)
        .map((media_id) => ({ media_id, media_type: "movie" as const }));

      if (keys.length === 0) {
        setWatchlistState((prev) => {
          const next = { ...prev };
          unique.forEach((id) => {
            next[id] = {
              state: "not_added",
              status: null,
              rating: null,
              id: null,
              busy: false,
            };
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
          });
          return next;
        });
      } catch (error) {
        console.warn("Failed to load watchlist state", error);
        setWatchlistState((prev) => {
          const next = { ...prev };
          unique.forEach((id) => {
            next[id] = {
              state: "not_added",
              status: null,
              rating: null,
              id: null,
              busy: false,
            };
          });
          return next;
        });
      }
    },
    [toNumericMediaId]
  );

  const startWhyStream = useCallback(
    async (streamUrl: string | null | undefined, token: string) => {
      whyAbortRef.current?.abort();
      whyAbortRef.current = null;

      if (!streamUrl) {
        setCards((prev) => finalizeWhyLoading(prev));
        setIsWhyStreaming(false);
        return;
      }
      const controller = new AbortController();
      whyAbortRef.current = controller;
      setIsWhyStreaming(true);

      try {
        await streamExploreWhy({
          token,
          streamUrl,
          signal: controller.signal,
          onEvent: handleWhyStreamEvent,
        });
        if (!controller.signal.aborted) {
          setCards((prev) => finalizeWhyLoading(prev));
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setErrorMessage(
            toErrorMessage(error, "Could not finish streaming reasons.")
          );
          setCards((prev) => finalizeWhyLoading(prev));
        }
      } finally {
        if (whyAbortRef.current === controller) {
          whyAbortRef.current = null;
          setIsWhyStreaming(false);
        }
      }
    },
    [handleWhyStreamEvent]
  );

  const handleExploreEvent = useCallback(
    (
      event: ExploreStreamEvent,
      sessionId: string,
      token: string,
      streamQueryId: string
    ) => {
      if (queryIdRef.current && streamQueryId !== queryIdRef.current) {
        return;
      }

      const eventQueryId =
        event.data && typeof event.data === "object" && "query_id" in event.data
          ? (event.data as { query_id?: string }).query_id
          : null;

      if (eventQueryId && eventQueryId !== streamQueryId) {
        return;
      }

      if (event.type === "started") {
        setIsExploreStreaming(true);
        return;
      }

      if (event.type === "opening") {
        setPageState("recs");
        setIntro(event.data.opening_summary ?? "");
        const providersFromResponse = providersFromActiveSpec(
          event.data.active_spec
        );
        const openingQueryText =
          typeof event.data.active_spec?.query_text === "string"
            ? event.data.active_spec.query_text.trim()
            : "";
        if (openingQueryText) {
          setActiveQuery(openingQueryText);
        }
        setSelectedProviders(providersFromResponse);
        const providerIdsFromResponse =
          mapStreamingServiceNamesToIds(providersFromResponse);
        activeProviderIdsRef.current = providerIdsFromResponse;
        const yearRangeFromResponse = yearRangeFromActiveSpec(
          event.data.active_spec
        );
        setSelectedYearRange(yearRangeFromResponse);
        activeYearRangeRef.current = yearRangeFromResponse;
        lastSessionIdRef.current = sessionId;
        setFiltersReady(true);
        setIsAwaitingRecs(true);
        setHasRecsResponse(false);
        return;
      }

      if (event.type === "chat") {
        setChatMessage(event.data.message ?? "");
        setPageState("chat");
        setFiltersReady(false);
        setIsAwaitingRecs(false);
        setHasRecsResponse(false);
        setIsExploreStreaming(false);
        return;
      }

      if (event.type === "recs") {
        const mapped: Record<string, DiscoverCardData> = {};
        const newOrder: string[] = [];

        event.data.items.forEach((item) => {
          const mediaId = normalizeMediaId(item.media_id);
          if (!mediaId) return;
          const { imdbRating, rottenTomatoesRating, releaseYear } =
            mapToRatings(item);
          mapped[mediaId] = {
            id: item.id,
            mediaId,
            title: item.title,
            releaseYear,
            posterUrl: item.poster_url ?? undefined,
            backdropUrl: item.backdrop_url ?? undefined,
            trailerKey:
              typeof item.trailer_key === "string"
                ? item.trailer_key
                : undefined,
            genres: toGenres(item.genres),
            providers: [],
            imdbRating,
            rottenTomatoesRating,
            whyMarkdown: undefined,
            whyText: undefined,
            whySource: "llm",
            isWhyLoading: true,
            isRatingsLoading: false,
          };
          newOrder.push(mediaId);
        });

        setCards(mapped);
        setOrder(newOrder);
        if (event.data.curator_opening) {
          setIntro(event.data.curator_opening);
        }
        setPageState("recs");
        setIsAwaitingRecs(false);
        setHasRecsResponse(true);
        setIsExploreStreaming(false);
        void loadWatchlistState(newOrder);
        void startWhyStream(event.data.stream_url ?? null, token);
        return;
      }

      if (event.type === "done") {
        setIsExploreStreaming(false);
        setIsAwaitingRecs(false);
        return;
      }

      if (event.type === "error") {
        const message =
          event.data &&
          typeof event.data === "object" &&
          "message" in event.data &&
          typeof (event.data as { message?: string }).message === "string"
            ? (event.data as { message: string }).message
            : "Could not fetch recommendations right now.";
        setErrorMessage(message);
        setPageState("error");
        setIsExploreStreaming(false);
        setIsAwaitingRecs(false);
      }
    },
    [loadWatchlistState, startWhyStream]
  );

  const handleSubmit = useCallback(
    async (
      text?: string,
      overrideProviders?: number[],
      overrideYearRange?: [number, number] | null
    ) => {
      const value = (text ?? query).trim();
      if (!value) return;

      setExploreRedirectFlag();
      exploreAbortRef.current?.abort();
      exploreAbortRef.current = null;
      whyAbortRef.current?.abort();
      whyAbortRef.current = null;
      setPageState("loading");
      setErrorMessage(null);
      setIntro("");
      setChatMessage("");
      setCards({});
      setOrder([]);
      setActiveQuery(value);
      setFeedbackById({});
      setPendingFeedback({});
      setIsExploreStreaming(false);
      setIsWhyStreaming(false);
      setIsAwaitingRecs(false);
      setHasRecsResponse(false);
      setWatchlistState({});
      setFiltersReady(false);
      activeProviderIdsRef.current = [];
      activeYearRangeRef.current = null;
      lastSessionIdRef.current = null;

      const sessionId = getSessionId();
      const queryId = `${sessionId}_${Date.now()}`;
      queryIdRef.current = queryId;

      const token = await getAccessToken();
      if (!token) {
        setPageState("unauthorized");
        setErrorMessage("Sign in to explore recommendations tailored to you.");
        return;
      }

      const providerIds = overrideProviders ?? selectedProviderIds;
      const yearRange =
        overrideYearRange === undefined ? selectedYearRangeForQuery : overrideYearRange;

      const controller = new AbortController();
      exploreAbortRef.current = controller;
      setIsExploreStreaming(true);

      try {
        await streamExplore({
          token,
          queryText: value,
          sessionId,
          queryId,
          mediaType: "movie",
          deviceInfo,
          queryFilters: {
            providers: providerIds,
            ...(yearRange ? { year_range: yearRange } : {}),
          },
          signal: controller.signal,
          onEvent: (event) => handleExploreEvent(event, sessionId, token, queryId),
        });
      } catch (error) {
        if (!controller.signal.aborted) {
          setErrorMessage(
            toErrorMessage(error, "Could not fetch recommendations right now.")
          );
          setPageState("error");
        }
      } finally {
        if (exploreAbortRef.current === controller) {
          exploreAbortRef.current = null;
          setIsExploreStreaming(false);
        }
      }
    },
    [
      query,
      deviceInfo,
      handleExploreEvent,
      selectedProviderIds,
      selectedYearRangeForQuery,
    ]
  );

  const handleFeedback = useCallback(
    async (card: DiscoverCardData, rating: ExploreRating) => {
      if (!card.mediaId) return;
      const id = card.mediaId;
      const previous = feedbackById[id];
      if (previous === rating) return;

      setFeedbackById((prev) => ({ ...prev, [id]: rating }));
      setPendingFeedback((prev) => ({ ...prev, [id]: true }));

      const position = order.findIndex((value) => value === id);
      const ordinal = position >= 0 ? position + 1 : null;

      try {
        await logUserRecReaction({
          mediaId: card.mediaId,
          title: card.title,
          reaction: rating,
          source: "discovery_explore",
          mediaType: "movie",
          position: ordinal,
          queryId: queryIdRef.current,
        });
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
        toast({
          title: "Feedback not saved",
          description: toErrorMessage(error, "Please try again."),
          variant: "destructive",
        });
      } finally {
        setPendingFeedback((prev) => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }
    },
    [feedbackById, order, toast]
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
    [toast, watchlistState, toNumericMediaId]
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
      } catch (error) {
        setWatchlistState((prev) => {
          const existing = prev[card.mediaId];
          if (!existing) return prev;
          return {
            ...prev,
            [card.mediaId]: { ...snapshot, busy: false },
          };
        });
        toast({
          title: "Could not update watchlist",
          description: toErrorMessage(error, "Please try again in a moment."),
          variant: "destructive",
        });
      }
    },
    [toast, watchlistState]
  );

  const handleWatchlistRemove = useCallback(
    async (card: DiscoverCardData) => {
      if (!card.mediaId) return;
      const entry = watchlistState[card.mediaId];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) {
        return;
      }

      const snapshot: WatchlistUiState = { ...entry };
      setWatchlistState((prev) => {
        const existing = prev[card.mediaId];
        if (!existing) return prev;
        return {
          ...prev,
          [card.mediaId]: { ...existing, busy: true },
        };
      });

      try {
        await deleteWatchlistItem(entry.id);
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
            [card.mediaId]: snapshot,
          };
        });
        toast({
          title: "Could not remove from watchlist",
          description: toErrorMessage(error, "Please try again in a moment."),
          variant: "destructive",
        });
      }
    },
    [toast, watchlistState]
  );

  const rerunWithPatch = useCallback(
    async ({
      sessionId,
      queryId,
      patch,
    }: {
      sessionId: string;
      queryId: string;
      patch: { providers: string[] | null; year_range: [number, number] | null };
    }) => {
      const previousCards = cards;
      const previousOrder = order;
      const previousWatchlistState = watchlistState;
      const previousFeedback = feedbackById;
      const previousPendingFeedback = pendingFeedback;
      const previousAwaitingRecs = isAwaitingRecs;
      const previousHasRecs = hasRecsResponse;

      exploreAbortRef.current?.abort();
      exploreAbortRef.current = null;
      whyAbortRef.current?.abort();
      whyAbortRef.current = null;
      setIsExploreStreaming(false);
      setIsWhyStreaming(false);
      setIsAwaitingRecs(true);
      setHasRecsResponse(false);
      setPageState("recs");
      setCards({});
      setOrder([]);
      setFeedbackById({});
      setPendingFeedback({});
      setWatchlistState({});

      try {
        const token = await getAccessToken();
        if (!token) {
          setPageState("unauthorized");
          setErrorMessage("Sign in to explore recommendations tailored to you.");
          return;
        }

        const nextProviders = patch.providers ?? [];
        setSelectedProviders(nextProviders);
        activeProviderIdsRef.current = mapStreamingServiceNamesToIds(nextProviders);
        setSelectedYearRange(patch.year_range ?? null);
        activeYearRangeRef.current = patch.year_range ?? null;

        const response = await rerunExplore({
          token,
          sessionId,
          queryId,
          deviceInfo,
          patch,
        });

        const mapped: Record<string, DiscoverCardData> = {};
        const newOrder: string[] = [];

        response.items.forEach((item) => {
          const mediaId = normalizeMediaId(item.media_id);
          if (!mediaId) return;
          const { imdbRating, rottenTomatoesRating, releaseYear } = mapToRatings(item);
          mapped[mediaId] = {
            id: item.id,
            mediaId,
            title: item.title,
            releaseYear,
            posterUrl: item.poster_url ?? undefined,
            backdropUrl: item.backdrop_url ?? undefined,
            trailerKey: typeof item.trailer_key === "string" ? item.trailer_key : undefined,
            genres: toGenres(item.genres),
            providers: [],
            imdbRating,
            rottenTomatoesRating,
            whyMarkdown: undefined,
            whyText: undefined,
            whySource: "llm",
            isWhyLoading: true,
            isRatingsLoading: false,
          };
          newOrder.push(mediaId);
        });

        lastSessionIdRef.current = sessionId;
        setCards(mapped);
        setOrder(newOrder);
        setFeedbackById({});
        setPendingFeedback({});
        setWatchlistState({});
        setPageState("recs");
        setIsAwaitingRecs(false);
        setHasRecsResponse(true);
        void loadWatchlistState(newOrder);
        void startWhyStream(response.stream_url, token);
      } catch (error) {
        setCards(previousCards);
        setOrder(previousOrder);
        setWatchlistState(previousWatchlistState);
        setFeedbackById(previousFeedback);
        setPendingFeedback(previousPendingFeedback);
        setIsAwaitingRecs(previousAwaitingRecs);
        setHasRecsResponse(previousHasRecs);
        toast({
          title: "Could not refresh picks",
          description: toErrorMessage(
            error,
            "Please try adjusting your filters again."
          ),
          variant: "destructive",
        });
      }
    },
    [
      cards,
      order,
      watchlistState,
      feedbackById,
      pendingFeedback,
      isAwaitingRecs,
      hasRecsResponse,
      deviceInfo,
      loadWatchlistState,
      startWhyStream,
      toast,
    ]
  );

  const handleProviderFilterApply = useCallback(
    (providers: string[]) => {
      setSelectedProviders(providers);
      const nextProviderIds = mapStreamingServiceNamesToIds(providers);
      const currentProviders = activeProviderIdsRef.current;
      const sortedNext = [...nextProviderIds].sort((a, b) => a - b);
      const sortedCurrent = [...currentProviders].sort((a, b) => a - b);
      const hasChange =
        sortedNext.length !== sortedCurrent.length ||
        sortedNext.some((value, index) => value !== sortedCurrent[index]);
      if (!hasChange) return;

      const sessionId = lastSessionIdRef.current;
      const queryId = queryIdRef.current;
      if (!sessionId || !queryId) return;

      const yearRange = selectedYearRangeForQuery;
      void rerunWithPatch({
        sessionId,
        queryId,
        patch: {
          providers: providers.length > 0 ? providers : null,
          year_range: yearRange ?? null,
        },
      });
    },
    [rerunWithPatch, selectedYearRangeForQuery]
  );

  const handleYearFilterApply = useCallback(
    (range: [number, number] | null) => {
      setSelectedYearRange(range);
      const normalized =
        range && range.length === 2
          ? ([Math.min(range[0], range[1]), Math.max(range[0], range[1])] as [
              number,
              number,
            ])
          : null;
      const current = activeYearRangeRef.current;
      const hasChange =
        (normalized === null) !== (current === null) ||
        (normalized !== null &&
          current !== null &&
          (normalized[0] !== current[0] || normalized[1] !== current[1]));

      if (!hasChange) return;

      const sessionId = lastSessionIdRef.current;
      const queryId = queryIdRef.current;
      if (!sessionId || !queryId) return;

      void rerunWithPatch({
        sessionId,
        queryId,
        patch: {
          providers: selectedProviders.length > 0 ? selectedProviders : null,
          year_range: normalized ?? null,
        },
      });
    },
    [rerunWithPatch, selectedProviders]
  );

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const incoming = params.get("q")?.trim() ?? "";
    if (!incoming) return;
    setQuery(incoming);
    if (autoSubmitRef.current === incoming) return;
    autoSubmitRef.current = incoming;
    void handleSubmit(incoming);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key, location.search]);

  useEffect(() => {
    return () => {
      exploreAbortRef.current?.abort();
      whyAbortRef.current?.abort();
    };
  }, []);

  return (
    <main className="min-h-[100dvh] pb-12">
      {hasSearched ? (
        <div className="sticky top-[4.5rem] z-40 border-b border-border bg-background/90 backdrop-blur">
          <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-4">
            <ExploreSearchForm
              value={query}
              onChange={setQuery}
              onSubmit={handleSubmit}
              disabled={isBusy}
              showExamples={false}
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span aria-live="polite">
                {isWhyStreaming
                  ? "Streaming personalized reasons..."
                  : isExploreStreaming
                    ? "Shaping your recommendations..."
                    : pageState === "chat"
                      ? ""
                      : activeQuery
                        ? `Showing results for "${activeQuery}"`
                        : "Refine your vibe and resubmit."}
              </span>
              {pageState === "loading" ? (
                <span className="animate-pulse">Finding picks...</span>
              ) : null}
            </div>
            {filtersReady ? (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <StreamingServiceFilterChip
                  selected={selectedProviders}
                  onApply={handleProviderFilterApply}
                />
                <YearRangeFilterChip
                  value={selectedYearRange}
                  onApply={handleYearFilterApply}
                  min={DEFAULT_YEAR_RANGE[0]}
                  max={DEFAULT_YEAR_RANGE[1]}
                />
              </div>
            ) : null}
          </div>
        </div>
      ) : (
        <section className="flex min-h-[70vh] flex-col items-center justify-center px-4 text-center">
          <div className="max-w-4xl space-y-8">
            <div className="space-y-3">
              <h1 className="text-4xl font-semibold leading-tight text-foreground sm:text-4xl">
                Find your next watch. Personalized to your taste.
              </h1>
              <p className="text-base text-muted-foreground sm:text-lg">
                Reelix is your personal AI curator. It learns your taste and
                brings you films you'll actually love.
              </p>
            </div>
            <div className="mx-auto max-w-2xl">
              <ExploreSearchForm
                value={query}
                onChange={setQuery}
                onSubmit={handleSubmit}
                disabled={isBusy}
                helperId={HERO_HELPER_ID}
                autoFocus
                showExamples
              />
            </div>
          </div>
        </section>
      )}

      {hasSearched ? (
        <section className="mx-auto mt-8 flex max-w-6xl flex-col gap-6 px-4">
          {pageState === "unauthorized" ? (
            <div className="rounded-2xl border border-border bg-muted/20 p-6 text-center">
              <p className="text-base text-muted-foreground">
                Sign in to get personalized explore recommendations.
              </p>
              <div className="mt-3">
                <Button asChild variant="default">
                  <Link to="/auth/signin">Sign in</Link>
                </Button>
              </div>
            </div>
          ) : null}

          {pageState === "error" && errorMessage ? (
            <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-6">
              <p className="text-base font-semibold text-destructive">
                Something went wrong
              </p>
              <p className="mt-2 text-sm text-destructive/80">{errorMessage}</p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button onClick={() => handleSubmit()} disabled={isBusy}>
                  Try again
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => setQuery("")}
                  disabled={isBusy}
                >
                  Start over
                </Button>
              </div>
            </div>
          ) : null}

          {pageState === "chat" ? (
            <div className="rounded-2xl border border-border bg-muted/10 p-6 shadow-sm">
              <div className="prose prose-invert max-w-none text-base leading-relaxed text-foreground">
                <ReactMarkdown>
                  {chatMessage || "Here's what we found."}
                </ReactMarkdown>
              </div>
            </div>
          ) : null}

          {pageState === "loading" ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-border bg-muted/10 p-6 shadow-sm">
                <p className="text-base font-medium text-foreground">
                  Curating picks for you...
                </p>
                <p className="text-sm text-muted-foreground">
                  Hang tight while we tailor recommendations.
                </p>
              </div>
            </div>
          ) : null}

          {pageState === "recs" ? (
            <div className="space-y-4">
              {intro ? (
                <div className="rounded-2xl border border-border bg-muted/10 p-6 shadow-sm">
                  <div className="prose prose-invert max-w-none text-base leading-relaxed text-foreground">
                    <ReactMarkdown>{intro}</ReactMarkdown>
                  </div>
                </div>
              ) : null}

              {orderedCards.length > 0 ? (
                <div className="flex flex-col gap-4">
                  {orderedCards.map((card) => {
                    const feedbackValue = card.mediaId
                      ? feedbackById[card.mediaId]
                      : undefined;
                    const feedbackDisabled =
                      isBusy ||
                      Boolean(
                        card.mediaId ? pendingFeedback[card.mediaId] : false
                      );

                    return (
                      <MovieCard
                        key={card.mediaId}
                        movie={card}
                        layout="wide"
                        feedback={{
                          value: feedbackValue,
                          disabled: feedbackDisabled,
                          onChange: (value) => handleFeedback(card, value),
                        }}
                        watchlist={{
                          state: watchlistState[card.mediaId]?.state ?? "not_added",
                          status: watchlistState[card.mediaId]?.status ?? null,
                          rating: watchlistState[card.mediaId]?.rating ?? null,
                          busy: watchlistState[card.mediaId]?.busy ?? false,
                          onAdd: () => handleWatchlistAdd(card),
                          onSelectStatus: (status: WatchlistStatus) =>
                            handleWatchlistStatus(card, status),
                          onRemove: () => handleWatchlistRemove(card),
                        }}
                      />
                    );
                  })}
                </div>
              ) : isAwaitingRecs ? (
                <DiscoverGridSkeleton count={4} />
              ) : null}
            </div>
          ) : null}

          {pageState === "recs" &&
          !isAwaitingRecs &&
          hasRecsResponse &&
          orderedCards.length === 0 ? (
            <div className="rounded-2xl border border-border bg-muted/10 p-6 text-center text-muted-foreground">
              No picks yet. Try a different vibe.
            </div>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
