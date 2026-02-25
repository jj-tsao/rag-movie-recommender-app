import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import MovieCard from "@/components/MovieCard";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/useToast";
import DiscoverGridSkeleton from "@/features/discover/for_you/components/DiscoverGridSkeleton";
import type { DiscoverCardData } from "@/features/discover/for_you/types";
import {
  getStreamingServiceOptions,
  mapStreamingServiceNamesToIds,
} from "@/data/streamingServices";
import { WATCH_PROVIDERS } from "@/data/watchProviders";
import {
  logUserRecReaction,
  type RatingValue,
} from "@/features/taste_onboarding/api";
import type { WatchlistStatus } from "@/features/watchlist/api";
import { getSessionId } from "@/utils/session";
import { getDeviceInfo } from "@/utils/detectDevice";
import { setExploreRedirectFlag } from "@/utils/exploreRedirect";
import { DEFAULT_YEAR_RANGE } from "@/utils/yearRange";
import {
  getAccessToken,
  logExploreFinalRecs,
  mapToRatings,
  rerunExplore,
  streamExplore,
  streamExploreWhy,
  type ExploreStreamEvent,
  type ExploreWhyEvent,
  type ActiveSpecEnvelope,
} from "../api";
import { toMediaId, toNumericMediaId, toStringArray } from "../../utils/parsing";
import { ExploreSearchForm } from "../components/ExploreSearchForm";
import { ExploreFilterBar } from "../components/ExploreFilterBar";
import { useExploreWatchlist } from "../hooks/useExploreWatchlist";
import { EXPLORE_COPY } from "../copy";

type ExploreRating = Exclude<RatingValue, "dismiss">;
type PageState =
  | "idle"
  | "loading"
  | "recs"
  | "chat"
  | "error"
  | "unauthorized";

const HERO_HELPER_ID = "explore-helper";
const WATCHLIST_SOURCE = "discovery_explore";
const PROVIDER_NAME_BY_ID = new Map<number, string>(
  getStreamingServiceOptions()
    .filter((opt) => typeof opt.id === "number")
    .map((opt) => [opt.id as number, opt.name])
);

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

function excludeGenresFromActiveSpec(
  envelope: ActiveSpecEnvelope | null | undefined
): string[] {
  if (!envelope) return [];
  const chipGenres = (envelope.chips ?? [])
    .filter((c) => c.key === "exclude_genres" && typeof c.value === "string")
    .map((c) => c.value as string);
  if (chipGenres.length > 0) return chipGenres;
  return envelope.active_spec?.exclude_genres ?? [];
}

export default function ExplorePage() {
  const location = useLocation();
  const { toast } = useToast();
  const [query, setQuery] = useState("");
  const [pageState, setPageState] = useState<PageState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [intro, setIntro] = useState("");
  const [nextSteps, setNextSteps] = useState<string | null>(null);
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
  const [selectedProviders, setSelectedProviders] = useState<string[]>([]);
  const [selectedYearRange, setSelectedYearRange] = useState<[number, number] | null>(null);
  const [excludedGenres, setExcludedGenres] = useState<string[]>([]);
  const [, setFiltersReady] = useState(false);
  const queryIdRef = useRef<string | null>(null);
  const loggedQueryIdRef = useRef<string | null>(null);
  const autoSubmitRef = useRef<string | null>(null);
  const exploreAbortRef = useRef<AbortController | null>(null);
  const whyAbortRef = useRef<AbortController | null>(null);

  const {
    watchlistState,
    setWatchlistState,
    loadWatchlistState,
    handleWatchlistAdd,
    handleWatchlistStatus,
    handleWatchlistRemove,
  } = useExploreWatchlist({ source: WATCHLIST_SOURCE });

  const deviceInfo = useMemo(() => getDeviceInfo(), []);
  const selectedProviderIds = useMemo(
    () => mapStreamingServiceNamesToIds(selectedProviders),
    [selectedProviders]
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
    pageState === "loading" || isExploreStreaming;

  const handleWhyStreamEvent = useCallback((event: ExploreWhyEvent) => {
    if (event.type === "started") {
      setIsWhyStreaming(true);
      return;
    }
    if (event.type === "why_delta") {
      const mediaId = toMediaId(event.data.media_id);
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

  const startWhyStream = useCallback(
    async (whyUrl: string | null | undefined, token: string) => {
      whyAbortRef.current?.abort();
      whyAbortRef.current = null;

      if (!whyUrl) {
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
          streamUrl: whyUrl,
          signal: controller.signal,
          onEvent: handleWhyStreamEvent,
        });
        if (!controller.signal.aborted) {
          setCards((prev) => finalizeWhyLoading(prev));
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setErrorMessage(
            toErrorMessage(error, EXPLORE_COPY.error.streamFailed)
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

      if (event.type === "next_steps") {
        if (event.data.query_id && event.data.query_id !== streamQueryId) return;
        setNextSteps(event.data.text);
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

        setSelectedProviders(providersFromResponse);
        const providerIdsFromResponse =
          mapStreamingServiceNamesToIds(providersFromResponse);
        activeProviderIdsRef.current = providerIdsFromResponse;
        const yearRangeFromResponse = yearRangeFromActiveSpec(
          event.data.active_spec
        );
        setSelectedYearRange(yearRangeFromResponse);
        activeYearRangeRef.current = yearRangeFromResponse;
        setExcludedGenres(excludeGenresFromActiveSpec(event.data.active_spec));
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
          const mediaId = toMediaId(item.media_id);
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
            genres: toStringArray(item.genres),
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
        void startWhyStream(event.data.why_url ?? null, token);
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
        const errorId =
          event.data &&
          typeof event.data === "object" &&
          "error_id" in event.data &&
          typeof (event.data as { error_id?: string }).error_id === "string"
            ? (event.data as { error_id: string }).error_id
            : null;
        setErrorMessage(errorId ? `${message} (Ref ${errorId})` : message);
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

      setQuery("");
      setExploreRedirectFlag();
      exploreAbortRef.current?.abort();
      exploreAbortRef.current = null;
      whyAbortRef.current?.abort();
      whyAbortRef.current = null;
      setPageState("loading");
      window.scrollTo({ top: 0 });
      setErrorMessage(null);
      setIntro("");
      setNextSteps(null);
      setChatMessage("");
      setCards({});
      setOrder([]);

      setFeedbackById({});
      setPendingFeedback({});
      setIsExploreStreaming(false);
      setIsWhyStreaming(false);
      setIsAwaitingRecs(false);
      setHasRecsResponse(false);
      setWatchlistState({});
      setExcludedGenres([]);
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
        setErrorMessage(EXPLORE_COPY.error.unauthorized);
        return;
      }

      const providerIds = overrideProviders ?? selectedProviderIds;
      const yearRange =
        overrideYearRange === undefined ? selectedYearRange : overrideYearRange;

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
            toErrorMessage(error, EXPLORE_COPY.error.fetchFailed)
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
      selectedYearRange,
      setWatchlistState,
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
          source: "vibe_query",
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

      window.scrollTo({ top: 0 });
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
          setErrorMessage(EXPLORE_COPY.error.unauthorized);
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
          const mediaId = toMediaId(item.media_id);
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
            genres: toStringArray(item.genres),
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
        void startWhyStream(response.why_url, token);
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
          description: toErrorMessage(error, EXPLORE_COPY.error.refreshFailed),
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
      setWatchlistState,
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

      const yearRange = selectedYearRange;
      void rerunWithPatch({
        sessionId,
        queryId,
        patch: {
          providers: providers.length > 0 ? providers : null,
          year_range: yearRange ?? null,
        },
      });
    },
    [rerunWithPatch, selectedYearRange]
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
      queryIdRef.current = null;
      loggedQueryIdRef.current = null;
      lastSessionIdRef.current = null;
      autoSubmitRef.current = null;
    };
  }, []);

  // Log final recommendations after why streaming completes
  useEffect(() => {
    // Only log when why streaming has finished and we have recs
    if (isWhyStreaming) return;
    if (!hasRecsResponse) return;
    const queryId = queryIdRef.current;
    if (!queryId) return;
    if (loggedQueryIdRef.current === queryId) return;

    const finalRecs = orderedCards
      .map((card) => {
        const mediaId = toNumericMediaId(card.mediaId);
        if (mediaId === null) return null;
        const why = (card.whyMarkdown ?? card.whyText ?? "").trim();
        if (!why) return null;
        const whySource: "cache" | "llm" = card.whySource === "cache" ? "cache" : "llm";
        const imdbRating =
          typeof card.imdbRating === "number" && Number.isFinite(card.imdbRating)
            ? card.imdbRating
            : null;
        const rtRating =
          typeof card.rottenTomatoesRating === "number" &&
          Number.isFinite(card.rottenTomatoesRating)
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
          entry
        ): entry is {
          media_id: number;
          why: string;
          imdb_rating: number | null;
          rt_rating: number | null;
          why_source: "cache" | "llm";
        } => entry !== null
      );

    if (finalRecs.length === 0) return;

    loggedQueryIdRef.current = queryId;
    void logExploreFinalRecs({
      queryId,
      mediaType: "movie",
      finalRecs,
    }).catch((error) => {
      console.warn("Failed to log explore final recommendations", error);
    });
  }, [orderedCards, isWhyStreaming, hasRecsResponse]);

  return (
    <main className={`min-h-[100dvh] ${hasSearched ? "pb-44" : "pb-12"}`}>
      {hasSearched ? null : (
        <section className="relative flex min-h-[70vh] flex-col items-center justify-center px-4 text-center">
          <div className="max-w-4xl space-y-8">
            <div className="space-y-3">
              <h1 className="font-display text-3xl font-bold leading-tight text-foreground sm:text-4xl animate-fade-up">
                {EXPLORE_COPY.hero.heading}
              </h1>
              <p className="text-base text-muted-foreground sm:text-lg animate-fade-up delay-100">
                {EXPLORE_COPY.hero.subheading}
              </p>
            </div>
            <div className="mx-auto max-w-2xl animate-fade-up delay-200">
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
                {EXPLORE_COPY.error.signInPrompt}
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
                {EXPLORE_COPY.error.somethingWrong}
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
            <div className="relative border-l-2 border-l-gold/60 pl-4 py-1 animate-fade-in">
              <div className="prose prose-invert prose-sm max-w-none text-base leading-relaxed text-zinc-200">
                <ReactMarkdown>
                  {chatMessage || EXPLORE_COPY.chat.fallback}
                </ReactMarkdown>
              </div>
            </div>
          ) : null}

          {pageState === "loading" ? (
            <div className="space-y-4">
              <div className="relative rounded-2xl border border-gold/20 bg-background/60 p-6 shadow-lg backdrop-blur-sm card-grain">
                <p className="flex items-center gap-0.5 text-base font-medium text-foreground">
                  <span>{EXPLORE_COPY.loading.curatingHeading}</span>
                  <span className="flex">
                    <span className="animate-[pulse_1.4s_ease-in-out_infinite]">.</span>
                    <span className="animate-[pulse_1.4s_ease-in-out_0.2s_infinite]">.</span>
                    <span className="animate-[pulse_1.4s_ease-in-out_0.4s_infinite]">.</span>
                  </span>
                </p>
                <p className="text-sm text-muted-foreground">
                  {EXPLORE_COPY.loading.curatingBody}
                </p>
              </div>
            </div>
          ) : null}

          {pageState === "recs" ? (
            <div className="space-y-4">
              {intro ? (
                <div className="relative border-l-2 border-l-gold/60 pl-4 py-1 animate-fade-in">
                  <div className="prose prose-invert prose-sm max-w-none text-base leading-relaxed text-zinc-200">
                    <ReactMarkdown>{intro}</ReactMarkdown>
                  </div>
                </div>
              ) : null}

              {orderedCards.length > 0 ? (
                <div className="flex flex-col gap-4 animate-fade-in">
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

              {nextSteps && orderedCards.length > 0 ? (
                <div className="relative border-l-2 border-l-gold/60 pl-4 py-1 animate-fade-in">
                  <div className="prose prose-invert prose-sm max-w-none text-base leading-relaxed text-zinc-200">
                    <ReactMarkdown>{nextSteps}</ReactMarkdown>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          {pageState === "recs" &&
          !isAwaitingRecs &&
          hasRecsResponse &&
          orderedCards.length === 0 ? (
            <div className="rounded-2xl border border-border bg-muted/10 p-6 text-center text-base text-muted-foreground">
              {EXPLORE_COPY.empty.noPicks}
            </div>
          ) : null}
        </section>
      ) : null}

      {hasSearched ? (
        <div className="fixed bottom-0 left-0 right-0 z-40">
          {/* Gradient fade instead of hard border */}
          <div className="pointer-events-none h-12 bg-gradient-to-t from-background to-transparent" />
          <div className="bg-background/80 backdrop-blur-xl">
            <div className="mx-auto max-w-5xl px-4 pb-6 pt-2">
              <ExploreSearchForm
                value={query}
                onChange={setQuery}
                onSubmit={handleSubmit}
                disabled={isBusy}
                showExamples={false}
                compact
                footer={
                  <ExploreFilterBar
                    selectedProviders={selectedProviders}
                    onProviderApply={handleProviderFilterApply}
                    selectedYearRange={selectedYearRange}
                    onYearApply={handleYearFilterApply}
                    excludedGenres={excludedGenres}
                    compact
                  />
                }
              />
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}