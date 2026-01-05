import { BASE_URL } from "@/api";
import { getSupabaseAccessToken } from "@/lib/session";

export type WatchlistStatus = "want" | "watched";

export interface WatchlistLookupKey {
  media_id: number;
  media_type?: "movie" | "tv";
}

export interface WatchlistLookupResult extends WatchlistLookupKey {
  id: string | null;
  exists: boolean;
  status: WatchlistStatus | null;
  rating: number | null;
}

export interface WatchlistCreateInput extends WatchlistLookupKey {
  status?: WatchlistStatus;
  title?: string | null;
  poster_url?: string | null;
  backdrop_url?: string | null;
  release_year?: number | null;
  genres?: string[] | null;
  trailer_url?: string | null;
  imdb_rating?: number | null;
  rt_rating?: number | null;
  why_summary?: string | null;
  source?: string | null;
}

export interface WatchlistItemResponse {
  id: string;
  media_id: number;
  media_type: string;
  status: WatchlistStatus;
  rating?: number | null;
}

export interface WatchlistListItem extends WatchlistItemResponse {
  notes?: string | null;
  title?: string | null;
  poster_url?: string | null;
  backdrop_url?: string | null;
  trailer_url?: string | null;
  release_year?: number | null;
  genres?: string[] | null;
  imdb_rating?: number | null;
  rt_rating?: number | null;
  why_summary?: string | null;
  source?: string | null;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string | null;
}

export interface WatchlistListResponse {
  items: WatchlistListItem[];
  page: number;
  page_size: number;
  total: number;
}

export async function lookupWatchlistKeys(keys: WatchlistLookupKey[]): Promise<WatchlistLookupResult[]> {
  if (keys.length === 0) {
    return [];
  }

  const token = await getSupabaseAccessToken();
  if (!token) {
    throw new Error("Sign in to manage your watchlist.");
  }

  const response = await fetch(`${BASE_URL}/v2/users/me/watchlist/keys/lookup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      keys: keys.map(({ media_id, media_type = "movie" }) => ({
        media_id,
        media_type,
      })),
    }),
  });

  if (!response.ok) {
    const message = await safeReadText(response);
    throw new Error(message || "Failed to check watchlist state.");
  }

  return (await response.json()) as WatchlistLookupResult[];
}

export async function createWatchlistItem(payload: WatchlistCreateInput): Promise<WatchlistItemResponse> {
  const token = await getSupabaseAccessToken();
  if (!token) {
    throw new Error("Sign in to manage your watchlist.");
  }

  const response = await fetch(`${BASE_URL}/v2/users/me/watchlist`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      ...payload,
      media_type: payload.media_type ?? "movie",
      status: payload.status ?? "want",
    }),
  });

  if (!response.ok) {
    const message = await safeReadText(response);
    throw new Error(message || "Could not add to watchlist.");
  }

  return (await response.json()) as WatchlistItemResponse;
}

export interface WatchlistUpdatePayload {
  status?: WatchlistStatus;
  rating?: number | null;
  notes?: string | null;
}

export async function fetchWatchlist({
  page = 1,
  pageSize = 100,
  status,
}: {
  page?: number;
  pageSize?: number;
  status?: WatchlistStatus;
} = {}): Promise<WatchlistListResponse> {
  const token = await getSupabaseAccessToken();
  if (!token) {
    throw new Error("Sign in to view your watchlist.");
  }

  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (status) {
    params.set("status", status);
  }

  const response = await fetch(`${BASE_URL}/v2/users/me/watchlist?${params.toString()}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const message = await safeReadText(response);
    throw new Error(message || `Failed to load watchlist (${response.status})`);
  }

  return (await response.json()) as WatchlistListResponse;
}

export async function updateWatchlist(id: string, payload: WatchlistUpdatePayload): Promise<WatchlistItemResponse> {
  const body: Record<string, unknown> = {};
  if (payload.status !== undefined) body.status = payload.status;
  if (payload.rating !== undefined) body.rating = payload.rating;
  if (payload.notes !== undefined) body.notes = payload.notes;
  if (Object.keys(body).length === 0) {
    throw new Error("Nothing to update.");
  }

  const token = await getSupabaseAccessToken();
  if (!token) {
    throw new Error("Sign in to manage your watchlist.");
  }

  const response = await fetch(`${BASE_URL}/v2/users/me/watchlist/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const message = await safeReadText(response);
    throw new Error(message || "Could not update watchlist.");
  }

  return (await response.json()) as WatchlistItemResponse;
}

export async function deleteWatchlistItem(id: string): Promise<void> {
  const token = await getSupabaseAccessToken();
  if (!token) {
    throw new Error("Sign in to manage your watchlist.");
  }

  const response = await fetch(`${BASE_URL}/v2/users/me/watchlist/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const message = await safeReadText(response);
    throw new Error(message || "Could not remove from watchlist.");
  }
}

async function safeReadText(response: Response): Promise<string | null> {
  try {
    return await response.text();
  } catch (error) {
    void error;
    return null;
  }
}
