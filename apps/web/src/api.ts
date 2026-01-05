import type { InteractiveRequestPayload } from "./types/types";
import { getSupabaseAccessToken } from "./lib/session";

export const BASE_URL = import.meta.env.VITE_BACKEND_URL;

export async function streamChatResponse(
  request: InteractiveRequestPayload,
  onChunk: (text: string) => void
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const token = await getSupabaseAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}/recommendations/interactive`, {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });

  if (!response.body) {
    throw new Error("No response body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    onChunk(chunk);
  }
}

export async function logFinalRecs({
  queryId,
  finalRecs,
}: {
  queryId: string;
  finalRecs: { media_id: number; why: string }[];
}) {
  const token = await getSupabaseAccessToken();
  const res = await fetch(`${BASE_URL}/recommendations/log/final_recs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      query_id: queryId,
      final_recs: finalRecs,
    }),
  });

  if (!res.ok) {
    console.warn("Failed to log final recommendations");
  }
}

export async function rebuildTasteProfile(): Promise<void> {
  const token = await getSupabaseAccessToken();
  if (!token) {
    throw new Error("Not signed in");
  }

  const res = await fetch(`${BASE_URL}/v2/users/me/taste_profile/rebuild`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Failed to rebuild taste profile");
  }
}
