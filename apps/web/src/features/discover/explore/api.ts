import { BASE_URL } from "@/api";
import { getResponseErrorMessage } from "@/lib/errors";
import { getSupabaseAccessToken } from "@/lib/session";
import type { DeviceInfo } from "@/types/types";
import { normalizeTomatoScore } from "../for_you/api";

export type ExploreMode = "CHAT" | "RECS";

export interface ExploreItem {
  id?: string;
  media_id: number | string;
  title: string;
  release_year?: number | string | null;
  genres?: unknown;
  imdb_rating?: number | string | null;
  rt_score?: number | string | null;
  poster_url?: string | null;
  backdrop_url?: string | null;
  trailer_key?: string | null;
}

export interface ExploreChatResponse {
  query_id: string;
  mode: "CHAT";
  message: string;
}

export interface ActiveSpecChip {
  group?: string;
  key: string;
  value: unknown;
  label?: string | null;
  editable?: boolean;
  hard?: boolean;
  source?: string;
}

export interface ActiveSpecEnvelope {
  spec_version?: number;
  active_spec?: {
    media_type?: string;
    providers?: number[];
    year_range?: number[];
    core_genres?: string[];
    exclude_genres?: string[];
    core_tone?: string[];
    key_themes?: string[];
    narrative_shape?: string[];
    sub_genres?: string[];
  } | null;
  chips?: ActiveSpecChip[];
  query_text?: string | null;
}

export interface ExploreRecsResponse {
  query_id: string;
  mode: "RECS";
  opening?: string | null;
  items: ExploreItem[];
  why_url?: string | null;
  active_spec?: ActiveSpecEnvelope | null;
}

export type ExploreResponse = ExploreChatResponse | ExploreRecsResponse;

export interface ExploreRequestOptions {
  token: string;
  queryText: string;
  sessionId: string;
  queryId: string;
  mediaType?: "movie" | "tv";
  deviceInfo?: DeviceInfo;
  queryFilters?: {
    genres?: string[];
    providers?: number[];
    year_range?: [number, number];
  };
}

export interface ExploreRerunPatch {
  providers?: string[] | null;
  year_range?: [number, number] | null;
}

export type ExploreWhyEvent =
  | { type: "started"; data: Record<string, unknown> | null }
  | {
      type: "why_delta";
      data: { media_id: string; why_you_might_enjoy_it?: string };
    }
  | { type: "done"; data: Record<string, unknown> | null }
  | { type: "error"; data: Record<string, unknown> | null };

export type ExploreStreamEvent =
  | { type: "started"; data: Record<string, unknown> | null }
  | {
      type: "opening";
      data: {
        query_id: string;
        opening_summary?: string | null;
        active_spec?: ActiveSpecEnvelope | null;
      };
    }
  | {
      type: "chat";
      data: { query_id: string; message?: string | null };
    }
  | {
      type: "recs";
      data: {
        query_id: string;
        items: ExploreItem[];
        why_url?: string | null;
        curator_opening?: string | null;
      };
    }
  | { type: "done"; data: Record<string, unknown> | null }
  | { type: "error"; data: Record<string, unknown> | null };

export interface ExploreStreamOptions extends ExploreRequestOptions {
  signal: AbortSignal;
  onEvent: (event: ExploreStreamEvent) => void;
}

export async function getAccessToken(): Promise<string | null> {
  return getSupabaseAccessToken();
}

export async function streamExplore({
  token,
  queryText,
  sessionId,
  queryId,
  mediaType = "movie",
  deviceInfo,
  queryFilters,
  signal,
  onEvent,
}: ExploreStreamOptions): Promise<void> {
  const response = await fetch(`${BASE_URL}/discovery/explore`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      media_type: mediaType,
      query_text: queryText,
      query_filters: queryFilters ?? {},
      session_id: sessionId,
      query_id: queryId,
      device_info: deviceInfo,
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(
      getResponseErrorMessage(response, `Explore request failed (${response.status})`)
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
      const parsed = parseExploreSseEvent(rawEvent);
      if (parsed) {
        onEvent(parsed);
      }
      sepIndex = buffer.indexOf("\n\n");
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    const parsed = parseExploreSseEvent(buffer.trimEnd());
    if (parsed) {
      onEvent(parsed);
    }
  }
}

export async function rerunExplore({
  token,
  sessionId,
  queryId,
  deviceInfo,
  patch,
}: {
  token: string;
  sessionId: string;
  queryId: string;
  deviceInfo?: DeviceInfo;
  patch: ExploreRerunPatch;
}): Promise<ExploreRecsResponse> {
  const response = await fetch(`${BASE_URL}/discovery/explore/rerun`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      session_id: sessionId,
      query_id: queryId,
      device_info: deviceInfo,
      patch,
    }),
  });

  if (!response.ok) {
    throw new Error(
      getResponseErrorMessage(response, `Explore rerun failed (${response.status})`)
    );
  }

  const payload = (await response.json()) as ExploreRecsResponse;
  if (!payload || payload.mode !== "RECS" || !Array.isArray(payload.items)) {
    throw new Error("Unexpected response from /discovery/explore/rerun");
  }

  return {
    query_id: payload.query_id,
    mode: "RECS",
    opening: payload.opening ?? "",
    items: payload.items,
    why_url:
      payload.why_url ??
      (payload as { stream_url?: string | null }).stream_url ??
      null,
    active_spec: payload.active_spec ?? null,
  };
}

export async function streamExploreWhy({
  token,
  streamUrl,
  signal,
  onEvent,
}: {
  token: string;
  streamUrl: string;
  signal: AbortSignal;
  onEvent: (event: ExploreWhyEvent) => void;
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
      getResponseErrorMessage(response, `Explore why stream failed (${response.status})`)
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

function parseSseFrame(raw: string): { eventType: string; data: string } | null {
  if (!raw || raw.startsWith(":")) {
    return null;
  }

  const lines = raw.split(/\r?\n/);
  let eventType = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line.trim()) continue;
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
      continue;
    }
  }

  return { eventType, data: dataLines.join("\n") };
}

function parseExploreSseEvent(raw: string): ExploreStreamEvent | null {
  const frame = parseSseFrame(raw);
  if (!frame) return null;

  const json = frame.data ? safeJsonParse<Record<string, unknown>>(frame.data) : null;

  switch (frame.eventType) {
    case "started":
      return { type: "started", data: json };
    case "opening": {
      const queryId = typeof json?.query_id === "string" ? json.query_id : null;
      if (!queryId) return null;
      const openingSummary =
        typeof json?.opening_summary === "string" ? json.opening_summary : null;
      const activeSpec =
        json && "active_spec" in json
          ? (json.active_spec as ActiveSpecEnvelope | null)
          : null;
      return {
        type: "opening",
        data: {
          query_id: queryId,
          opening_summary: openingSummary,
          active_spec: activeSpec,
        },
      };
    }
    case "chat": {
      const queryId = typeof json?.query_id === "string" ? json.query_id : null;
      if (!queryId) return null;
      const message = typeof json?.message === "string" ? json.message : "";
      return { type: "chat", data: { query_id: queryId, message } };
    }
    case "recs": {
      const queryId = typeof json?.query_id === "string" ? json.query_id : null;
      if (!queryId) return null;
      const items = Array.isArray(json?.items) ? (json.items as ExploreItem[]) : [];
      const whyUrl =
        typeof json?.why_url === "string"
          ? json.why_url
          : typeof json?.stream_url === "string"
            ? json.stream_url
            : null;
      const curatorOpening =
        typeof json?.curator_opening === "string" ? json.curator_opening : null;
      return {
        type: "recs",
        data: {
          query_id: queryId,
          items,
          why_url: whyUrl,
          curator_opening: curatorOpening,
        },
      };
    }
    case "done":
      return { type: "done", data: json };
    case "error":
      return { type: "error", data: json };
    default:
      return null;
  }
}

function parseSseEvent(raw: string): ExploreWhyEvent | null {
  const frame = parseSseFrame(raw);
  if (!frame) return null;

  const json = frame.data ? safeJsonParse<Record<string, unknown>>(frame.data) : null;

  switch (frame.eventType) {
    case "started":
      return { type: "started", data: json };
    case "why_delta": {
      const mediaId = toMediaId(json?.media_id);
      if (!mediaId) return null;
      const why =
        typeof json?.why_you_might_enjoy_it === "string"
          ? json.why_you_might_enjoy_it
          : undefined;
      return {
        type: "why_delta",
        data: { media_id: mediaId, why_you_might_enjoy_it: why },
      };
    }
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

function toMediaId(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "string" && value.trim() !== "") {
    return value.trim();
  }
  return null;
}

export function mapToRatings(item: ExploreItem): {
  imdbRating: number | null;
  rottenTomatoesRating: number | null;
  releaseYear?: number;
} {
  const imdbRating = toOptionalRating(item.imdb_rating);
  const rottenTomatoesRating = normalizeTomatoScore(item.rt_score);
  const releaseYear = toOptionalNumber(item.release_year);
  return { imdbRating, rottenTomatoesRating, releaseYear };
}

function toOptionalRating(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.round(value * 10) / 10;
  }
  if (typeof value === "string") {
    const cleaned = value.trim().replace(/[^0-9.]/g, "");
    if (!cleaned) return null;
    const parsed = Number(cleaned);
    if (Number.isFinite(parsed)) {
      return Math.round(parsed * 10) / 10;
    }
  }
  return null;
}

function toOptionalNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

export async function logExploreFinalRecs({
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
      endpoint: "discovery/explore",
    }),
  });

  if (!response.ok) {
    console.warn("Failed to log explore final recs");
  }
}
