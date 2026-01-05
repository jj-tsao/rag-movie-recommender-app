import { useEffect, useState, useRef, useMemo, useCallback } from "react";
import type { FilterSettings } from "../types/types";
import { streamChatResponse, logFinalRecs } from "../api";
import { getSessionId } from "../utils/session";
import { getDeviceInfo } from "../utils/detectDevice";
import ReactMarkdown from "react-markdown";
import MovieCard from "./MovieCard";
import { parseMarkdown } from "../utils/parseMarkdown";
import type { ParsedMovie } from "../utils/parseMarkdown";
import { getProviderIdByName } from "@/data/watchProviders";
import { useToast } from "@/components/ui/useToast";
import {
  createWatchlistItem,
  deleteWatchlistItem,
  lookupWatchlistKeys,
  updateWatchlist,
  type WatchlistStatus,
} from "@/features/watchlist/api";

type WatchlistUiState = {
  state: "loading" | "not_added" | "in_list";
  status: WatchlistStatus | null;
  rating: number | null;
  id: string | null;
  busy: boolean;
};

const WATCHLIST_SOURCE = "query_recommendations";

function toNumericMediaId(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value))
    return Math.trunc(value);
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return Math.trunc(parsed);
  }
  return null;
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const message = error.message?.trim();
    if (message) return message;
  }
  return fallback;
}

interface Props {
  question: string;
  filters: FilterSettings;
  onDoneStreaming?: () => void;
  onStreamingStatusChange?: (isStreaming: boolean) => void;
}

export default function ChatBox({
  question,
  filters,
  onDoneStreaming,
  onStreamingStatusChange,
}: Props) {
  const { toast } = useToast();
  const [intro, setIntro] = useState("");
  const [outro, setOutro] = useState("");
  const [cards, setCards] = useState<ParsedMovie[]>([]);
  const [chatResponse, setChatResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [watchlistState, setWatchlistState] = useState<
    Record<string, WatchlistUiState>
  >({});
  const [activeRatingPrompt, setActiveRatingPrompt] = useState<string | null>(
    null
  );

  const queryIdRef = useRef(`${getSessionId()}_${Date.now()}`);
  const onDoneStreamingRef = useRef(onDoneStreaming);
  const onStreamingStatusChangeRef = useRef(onStreamingStatusChange);
  const currentCardsRef = useRef<ParsedMovie[]>([]);
  const introCapturedRef = useRef(false);
  const finalBufferRef = useRef("");
  const hasStartedRef = useRef(false); // ✅ Prevent duplicate stream calls

  const deviceInfo = useMemo(() => getDeviceInfo(), []);

  useEffect(() => {
    onDoneStreamingRef.current = onDoneStreaming;
    onStreamingStatusChangeRef.current = onStreamingStatusChange;
  }, [onDoneStreaming, onStreamingStatusChange]);

  const filtersRef = useRef(filters);
  const questionRef = useRef(question);

  const openRatingPrompt = useCallback((id: string) => {
    setActiveRatingPrompt(id);
  }, []);

  const closeRatingPrompt = useCallback((id?: string) => {
    setActiveRatingPrompt((current) => {
      if (!current) return current;
      if (!id || current === id) return null;
      return current;
    });
  }, []);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  useEffect(() => {
    questionRef.current = question;
  }, [question]);

  useEffect(() => {
    if (!question.trim()) return;
    if (hasStartedRef.current) return;
    hasStartedRef.current = true;

    setIntro("");
    setOutro("");
    setCards([]);
    setChatResponse("");
    setLoading(true);
    currentCardsRef.current = [];
    introCapturedRef.current = false;
    let localBuffer = "";
    let mode: "unknown" | "recommendation" | "chat" = "unknown";

    onStreamingStatusChangeRef.current?.(true);

    const filterSnapshot = filtersRef.current;
    const providerIds = filterSnapshot.providers
      .map((name) => getProviderIdByName(name))
      .filter((id): id is number => typeof id === "number");

    streamChatResponse(
      {
        query_text: questionRef.current,
        media_type: filterSnapshot.media_type,
        history: [],
        query_filters: {
          genres: filterSnapshot.genres,
          providers: providerIds,
          year_range: filterSnapshot.year_range,
        },
        session_id: getSessionId(),
        query_id: queryIdRef.current,
        device_info: deviceInfo,
      },
      (chunk: string) => {
        localBuffer += chunk;
        finalBufferRef.current = localBuffer;

        if (mode === "unknown") {
          const match = localBuffer.match(/\[\[MODE:(recommendation|chat)\]\]/);
          if (match) {
            mode = match[1] as "recommendation" | "chat";
            localBuffer = localBuffer.replace(match[0], "");
          } else {
            return;
          }
        }

        if (mode === "chat") {
          // Ignore all chunks until tag is detected
          if (!introCapturedRef.current) {
            // Start streaming cleanly after [[MODE:chat]] tag
            const tagIndex = localBuffer.indexOf("[[MODE:chat]]");
            if (tagIndex !== -1) {
              const afterTag = localBuffer.slice(
                tagIndex + "[[MODE:chat]]".length
              );
              setChatResponse(afterTag);
              introCapturedRef.current = true;
            }
          } else {
            setChatResponse((prev) => prev + chunk);
          }
          return;
        }

        if (!introCapturedRef.current) {
          const endIdx = localBuffer.indexOf("<!-- END_INTRO -->");
          if (endIdx !== -1) {
            const introText = localBuffer
              .slice(0, endIdx)
              .replace(/\[\[.*?\]\]/g, "")
              .trim();
            setIntro((prev) => (prev ? prev : introText));
            localBuffer = localBuffer.slice(
              endIdx + "<!-- END_INTRO -->".length
            );
            introCapturedRef.current = true;
          } else {
            return;
          }
        }

        if (!localBuffer.includes("<!-- END_MOVIE -->")) return;

        const movieBlocks = localBuffer.split(/<!--\s*END_MOVIE\s*-->/g);
        if (movieBlocks.length > 1) {
          const completed = movieBlocks.slice(0, -1);
          localBuffer = movieBlocks[movieBlocks.length - 1];

          const newCards = parseMarkdown(
            completed.join("<!-- END_MOVIE -->")
          ).filter(
            (movie) =>
              movie &&
              !currentCardsRef.current.some((c) => c.title === movie.title) &&
              movie.why.length > 60 &&
              movie.why.split(/[.!?]/).filter(Boolean).length >= 2
          );

          if (newCards.length > 0) {
            currentCardsRef.current = [...currentCardsRef.current, ...newCards];
            setCards([...currentCardsRef.current]);
          }
        }
      }
    ).finally(() => {
      const potentialOutro = finalBufferRef.current.trim();
      if (
        !potentialOutro.includes("###") &&
        !potentialOutro.includes("WHY_YOU_MIGHT_ENJOY_IT") &&
        potentialOutro.length > 50
      ) {
        setOutro(potentialOutro);
      }

      if (currentCardsRef.current.length > 0) {
        logFinalRecs({
          queryId: queryIdRef.current,
          finalRecs: currentCardsRef.current.map((movie) => ({
            media_id: movie.mediaId,
            why: movie.why,
          })),
        });
      }

      setLoading(false);
      onStreamingStatusChangeRef.current?.(false);
      onDoneStreamingRef.current?.();
    });
  }, [question, deviceInfo]);

  useEffect(() => {
    if (cards.length === 0) {
      setWatchlistState({});
      setActiveRatingPrompt(null);
      return;
    }

    const numericIds = Array.from(
      new Set(
        cards
          .map((card) => toNumericMediaId(card.mediaId))
          .filter((id): id is number => id !== null && id > 0)
      )
    );

    const keys = new Set(numericIds.map((id) => String(id)));

    setActiveRatingPrompt((current) =>
      current && !keys.has(current) ? null : current
    );

    setWatchlistState((prev) => {
      const next: Record<string, WatchlistUiState> = {};
      keys.forEach((key) => {
        const existing = prev[key];
        if (existing) {
          next[key] = existing;
        } else {
          next[key] = {
            state: "loading",
            status: null,
            rating: null,
            id: null,
            busy: false,
          };
        }
      });
      return next;
    });

    if (numericIds.length === 0) return;

    let cancelled = false;
    lookupWatchlistKeys(
      numericIds.map((media_id) => ({
        media_id,
        media_type: filtersRef.current.media_type,
      }))
    )
      .then((results) => {
        if (cancelled) return;
        const map = new Map(results.map((res) => [String(res.media_id), res]));
        setWatchlistState(() => {
          const next: Record<string, WatchlistUiState> = {};
          keys.forEach((key) => {
            const match = map.get(key);
            if (match && match.exists && match.id) {
              next[key] = {
                state: "in_list",
                status: match.status ?? "want",
                rating: match.rating ?? null,
                id: match.id,
                busy: false,
              };
            } else {
              next[key] = {
                state: "not_added",
                status: null,
                rating: null,
                id: null,
                busy: false,
              };
            }
          });
          return next;
        });
      })
      .catch((error) => {
        console.warn("Watchlist lookup failed", error);
        if (cancelled) return;
        setWatchlistState((prev) => {
          const next: Record<string, WatchlistUiState> = {};
          keys.forEach((key) => {
            const existing = prev[key];
            if (existing && existing.state === "in_list") {
              next[key] = { ...existing, busy: false };
            } else {
              next[key] = {
                state: "not_added",
                status: null,
                rating: null,
                id: null,
                busy: false,
              };
            }
          });
          return next;
        });
      });

    return () => {
      cancelled = true;
    };
  }, [cards]);

  useEffect(() => {
    if (!activeRatingPrompt) return;
    const entry = watchlistState[activeRatingPrompt];
    if (!entry || entry.state !== "in_list") {
      setActiveRatingPrompt(null);
    }
  }, [activeRatingPrompt, watchlistState]);

  const handleWatchlistAdd = useCallback(
    async (movie: ParsedMovie) => {
      const numericId = toNumericMediaId(movie.mediaId);
      if (numericId === null || numericId <= 0) {
        toast({
          title: "Unable to add",
          description: "We couldn't identify this title just yet.",
          variant: "destructive",
        });
        return;
      }
      const key = String(numericId);
      const mediaType = filtersRef.current.media_type ?? "movie";

      setWatchlistState((prev) => ({
        ...prev,
        [key]: {
          state: "in_list",
          status: "want",
          rating: prev[key]?.rating ?? null,
          id: prev[key]?.id ?? null,
          busy: true,
        },
      }));

      try {
        const result = await createWatchlistItem({
          media_id: numericId,
          media_type: mediaType,
          status: "want",
          title: movie.title,
          poster_url: movie.posterUrl || null,
          backdrop_url: movie.backdropUrl || null,
          trailer_url: movie.trailerKey
            ? `https://www.youtube.com/watch?v=${movie.trailerKey}`
            : null,
          release_year: null,
          genres: movie.genres.length > 0 ? movie.genres : null,
          imdb_rating: Number.isFinite(movie.imdbRating)
            ? movie.imdbRating
            : null,
          rt_rating: Number.isFinite(movie.rottenTomatoesRating)
            ? movie.rottenTomatoesRating
            : null,
          why_summary: movie.why ?? null,
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
    [toast]
  );

  const handleWatchlistStatus = useCallback(
    async (movie: ParsedMovie, nextStatus: WatchlistStatus) => {
      const numericId = toNumericMediaId(movie.mediaId);
      if (numericId === null || numericId <= 0) return;
      const key = String(numericId);
      const entry = watchlistState[key];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id)
        return;
      const previousStatus = entry.status ?? "want";
      if (previousStatus === nextStatus) return;
      const snapshot = { ...entry };

      setWatchlistState((prev) => ({
        ...prev,
        [key]: {
          ...entry,
          state: "in_list",
          status: nextStatus,
          busy: true,
        },
      }));

      if (nextStatus !== "watched") {
        closeRatingPrompt(key);
      }

      try {
        const result = await updateWatchlist(entry.id, { status: nextStatus });
        const updatedStatus = result.status ?? nextStatus;
        const updatedRating = result.rating ?? entry.rating ?? null;
        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            state: "in_list",
            status: updatedStatus,
            rating: updatedRating,
            id: result.id,
            busy: false,
          },
        }));
        if (updatedStatus === "watched" && updatedRating === null) {
          openRatingPrompt(key);
        } else {
          closeRatingPrompt(key);
        }
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
    [watchlistState, closeRatingPrompt, openRatingPrompt, toast]
  );

  const handleWatchlistRating = useCallback(
    async (movie: ParsedMovie, ratingValue: number) => {
      const numericId = toNumericMediaId(movie.mediaId);
      if (numericId === null || numericId <= 0) return;
      const key = String(numericId);
      const entry = watchlistState[key];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id) {
        return;
      }
      if (
        !Number.isFinite(ratingValue) ||
        ratingValue < 1 ||
        ratingValue > 10
      ) {
        return;
      }
      const normalized = Math.min(10, Math.max(1, Math.round(ratingValue)));
      const snapshot = { ...entry };

      setWatchlistState((prev) => ({
        ...prev,
        [key]: {
          ...entry,
          rating: normalized,
          busy: true,
        },
      }));

      closeRatingPrompt(key);

      try {
        const result = await updateWatchlist(entry.id, { rating: normalized });
        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            state: "in_list",
            status: result.status ?? entry.status,
            rating: result.rating ?? normalized,
            id: result.id,
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
          title: "Could not save rating",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [watchlistState, closeRatingPrompt, toast]
  );

  const handleWatchlistRatingSkip = useCallback(
    (movie: ParsedMovie) => {
      const numericId = toNumericMediaId(movie.mediaId);
      if (numericId === null || numericId <= 0) return;
      closeRatingPrompt(String(numericId));
    },
    [closeRatingPrompt]
  );

  const handleWatchlistRatingClear = useCallback(
    async (movie: ParsedMovie) => {
      const numericId = toNumericMediaId(movie.mediaId);
      if (numericId === null || numericId <= 0) return;
      const key = String(numericId);
      const entry = watchlistState[key];
      if (
        !entry ||
        entry.state !== "in_list" ||
        entry.busy ||
        !entry.id ||
        entry.rating === null
      ) {
        closeRatingPrompt(key);
        return;
      }
      const snapshot = { ...entry };

      setWatchlistState((prev) => ({
        ...prev,
        [key]: {
          ...entry,
          rating: null,
          busy: true,
        },
      }));

      closeRatingPrompt(key);

      try {
        const result = await updateWatchlist(entry.id, { rating: null });
        setWatchlistState((prev) => ({
          ...prev,
          [key]: {
            state: "in_list",
            status: result.status ?? entry.status,
            rating: result.rating ?? null,
            id: result.id,
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
          title: "Could not clear rating",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [watchlistState, closeRatingPrompt, toast]
  );

  const handleWatchlistRemove = useCallback(
    async (movie: ParsedMovie) => {
      const numericId = toNumericMediaId(movie.mediaId);
      if (numericId === null || numericId <= 0) return;
      const key = String(numericId);
      const entry = watchlistState[key];
      if (!entry || entry.state !== "in_list" || entry.busy || !entry.id)
        return;

      setWatchlistState((prev) => ({
        ...prev,
        [key]: {
          state: "not_added",
          status: null,
          rating: null,
          id: entry.id,
          busy: true,
        },
      }));
      closeRatingPrompt(key);

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
          [key]: entry,
        }));
        toast({
          title: "Could not remove from watchlist",
          description: toErrorMessage(error, "Please try again soon."),
          variant: "destructive",
        });
      }
    },
    [watchlistState, closeRatingPrompt, toast]
  );

  return (
    <div className="space-y-4">
      {chatResponse ? (
        <div className="prose prose-invert max-w-none">
          <ReactMarkdown>{chatResponse}</ReactMarkdown>
        </div>
      ) : (
        <>
          {intro && (
            <div className="prose prose-invert max-w-none min-h-[6rem]">
              <ReactMarkdown>{"✨  " + intro}</ReactMarkdown>
            </div>
          )}

          {cards.length > 0 && (
            <div className="space-y-6">
              {cards.map((movie, i) => {
                const numericId = toNumericMediaId(movie.mediaId);
                const key =
                  numericId !== null && numericId > 0
                    ? String(numericId)
                    : null;
                const entry = key ? watchlistState[key] : undefined;
                const watchlistProps = key
                  ? {
                      state: entry?.state ?? "loading",
                      status: entry?.status ?? null,
                      rating: entry?.rating ?? null,
                      busy: entry?.busy ?? false,
                      onAdd: () => handleWatchlistAdd(movie),
                      onSelectStatus: (status: WatchlistStatus) =>
                        handleWatchlistStatus(movie, status),
                      onRemove: () => handleWatchlistRemove(movie),
                      showRatingPrompt: activeRatingPrompt === key,
                      onRatingSelect: (value: number) =>
                        handleWatchlistRating(movie, value),
                      onRatingSkip: () => handleWatchlistRatingSkip(movie),
                      onRatingPromptOpen: () =>
                        openRatingPrompt(key),
                      onRatingClear: () => handleWatchlistRatingClear(movie),
                    }
                  : undefined;

                return (
                  <MovieCard
                    key={movie.title + i}
                    layout="wide"
                    movie={{
                      ...movie,
                      whyText: movie.why,
                    }}
                    watchlist={watchlistProps}
                  />
                );
              })}
            </div>
          )}

          {outro && (
            <div className="prose prose-invert max-w-none min-h-[6rem]">
              <ReactMarkdown>{outro}</ReactMarkdown>
            </div>
          )}
        </>
      )}

      {loading && (
        <div className="text-sm text-zinc-400">
          Curating your recommendations...
        </div>
      )}
    </div>
  );
}
