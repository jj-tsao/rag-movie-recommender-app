import { BASE_URL } from "@/api";
import { getResponseErrorMessage } from "@/lib/errors";
import { getSupabaseAccessToken } from "@/lib/session";
import { consumeSseStream, parseSseFrame, safeJsonParse } from "@/lib/streaming";
import { normalizeTomatoScore, toMediaId, toOptionalNumber } from "../utils/parsing";

export interface DiscoverInitialItem {
  id?: string;
  media_id: number | string;
  title: string;
  release_year?: number;
  poster_url?: string | null;
  backdrop_url?: string | null;
  trailer_key?: string | null;
  genres?: string[];
  providers?: string[];
  why_md?: string | null;
  imdb_rating?: number | string | null;
  rotten_tomatoes_rating?: number | string | null;
  why_source?: "cache" | "llm";
}

export interface DiscoverInitialResponse {
  query_id: string;
  stream_url?: string | null;
  items: DiscoverInitialItem[];
}

export interface DiscoverRequestOptions {
  mediaType?: "movie" | "tv";
  page?: number;
  pageSize?: number;
  includeWhy?: boolean;
  sessionId: string;
  queryId: string;
  providerIds?: number[];
  genres?: string[];
}

export type DiscoverStreamEvent =
  | { type: "started"; data: Record<string, unknown> | null }
  | { type: "progress"; data: Record<string, unknown> | null }
  | {
      type: "why_delta";
      data: {
        media_id: string;
        imdb_rating?: number | null;
        rotten_tomatoes_rating?: number | null;
        why_you_might_enjoy_it?: string;
      };
    }
  | { type: "done"; data: Record<string, unknown> | null }
  | { type: "error"; data: Record<string, unknown> | null };

export async function getAccessToken(): Promise<string | null> {
  return getSupabaseAccessToken();
}

export async function fetchDiscoverInitial(
  token: string,
  {
    mediaType = "movie",
    page = 1,
    pageSize = 12,
    includeWhy = false,
    sessionId,
    queryId,
    providerIds,
    genres,
  }: DiscoverRequestOptions,
): Promise<DiscoverInitialResponse> {
  const queryFilters: { providers?: number[]; genres?: string[] } = {};
  if (providerIds && providerIds.length > 0) {
    queryFilters.providers = providerIds;
  }
  if (genres && genres.length > 0) {
    queryFilters.genres = genres;
  }

  const response = await fetch(`${BASE_URL}/discovery/for-you`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      media_type: mediaType,
      page,
      page_size: pageSize,
      include_llm_why: includeWhy,
      session_id: sessionId,
      query_id: queryId,
      query_filters: queryFilters,
    }),
  });

  if (!response.ok) {
    throw new Error(
      getResponseErrorMessage(response, `Discover request failed (${response.status})`)
    );
  }

  const payload = (await response.json()) as DiscoverInitialResponse;
  if (!payload || !payload.query_id || !Array.isArray(payload.items)) {
    throw new Error("Unexpected response from /discovery/for-you");
  }
  return payload;
}

export async function streamDiscoverWhy({
  token,
  streamUrl,
  signal,
  onEvent,
}: {
  token: string;
  streamUrl: string;
  signal: AbortSignal;
  onEvent: (event: DiscoverStreamEvent) => void;
}): Promise<void> {
  const url = streamUrl.startsWith("http") ? streamUrl : `${BASE_URL}${streamUrl}`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "text/event-stream",
      Authorization: `Bearer ${token}`,
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(
      getResponseErrorMessage(response, `Stream failed (${response.status})`)
    );
  }

  const body = response.body;
  if (!body) {
    throw new Error("Stream response missing body");
  }

  await consumeSseStream(body, parseSseEvent, onEvent);
}

export async function logDiscoverFinalRecs({
  queryId,
  mediaType,
  finalRecs,
}: {
  queryId: string;
  mediaType: "movie" | "tv";
  finalRecs: {
    media_id: number;
    why: string;
    imdb_rating?: number | null;
    rt_rating?: number | null;
    why_source: "cache" | "llm";
  }[];
}): Promise<void> {
  const token = await getSupabaseAccessToken();
  const response = await fetch(`${BASE_URL}/discovery/telemetry/final_recs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      query_id: queryId,
      media_type: mediaType,
      final_recs: finalRecs,
      endpoint: "discovery/for-you",
    }),
  });

  if (!response.ok) {
    console.warn("Failed to log discovery final recs");
  }
}

function parseSseEvent(raw: string): DiscoverStreamEvent | null {
  const frame = parseSseFrame(raw);
  if (!frame) return null;

  const json = frame.data ? safeJsonParse<Record<string, unknown>>(frame.data) : null;
  switch (frame.eventType) {
    case "why_delta": {
      const delta = json as {
        media_id?: number | string;
        imdb_rating?: unknown;
        rotten_tomatoes_rating?: unknown;
        why_you_might_enjoy_it?: unknown;
      };
      const mediaId = toMediaId(delta?.media_id);
      if (!delta || !mediaId) {
        return null;
      }
      return {
        type: "why_delta",
        data: {
          media_id: mediaId,
          imdb_rating: toOptionalNumber(delta.imdb_rating),
          rotten_tomatoes_rating: normalizeTomatoScore(delta.rotten_tomatoes_rating),
          why_you_might_enjoy_it:
            typeof delta.why_you_might_enjoy_it === "string"
              ? delta.why_you_might_enjoy_it
              : undefined,
        },
      };
    }
    case "started":
      return { type: "started", data: json };
    case "progress":
      return { type: "progress", data: json };
    case "done":
      return { type: "done", data: json };
    case "error":
      return { type: "error", data: json };
    default:
      return null;
  }
}

