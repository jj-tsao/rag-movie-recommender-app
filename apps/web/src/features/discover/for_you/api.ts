import { BASE_URL } from "@/api";
import { getResponseErrorMessage } from "@/lib/errors";
import { getSupabaseAccessToken } from "@/lib/session";

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

  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex = buffer.indexOf("\n\n");
    while (sepIndex !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      const parsed = parseSseEvent(rawEvent);
      if (parsed) {
        onEvent(parsed);
      }
      sepIndex = buffer.indexOf("\n\n");
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    const parsed = parseSseEvent(buffer.trimEnd());
    if (parsed) {
      onEvent(parsed);
    }
  }
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
  if (!raw || raw.startsWith(":")) {
    return null;
  }

  const lines = raw.split(/\r?\n/);
  let eventType = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line.trim()) continue;
    if (line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
      continue;
    }
  }

  const dataStr = dataLines.join("\n");
  const json = dataStr ? safeJsonParse<Record<string, unknown>>(dataStr) : null;
  switch (eventType) {
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

function safeJsonParse<T>(value: string): T | null {
  try {
    return JSON.parse(value) as T;
  } catch (error) {
    void error;
    return null;
  }
}

function toOptionalNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function toMediaId(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "string" && value.trim() !== "") {
    return value.trim();
  }
  return null;
}

export function normalizeTomatoScore(value: unknown): number | null {
  let parsed: number | null = null;

  if (typeof value === "string") {
    const cleaned = value.trim().replace(/[^0-9.]/g, "");
    if (cleaned) {
      const num = Number(cleaned);
      parsed = Number.isFinite(num) ? num : null;
    }
  }

  if (parsed === null) {
    parsed = toOptionalNumber(value);
  }

  if (parsed === null) return null;

  if (parsed <= 1) {
    const scaled = parsed * 100;
    if (!Number.isFinite(scaled)) return null;
    return Math.round(scaled * 10) / 10;
  }

  if (parsed > 1000) {
    return Math.round(parsed / 10);
  }

  return Math.round(parsed * 10) / 10;
}
