import type { ChatRequest } from "./types/types";

const BASE_URL = import.meta.env.VITE_BACKEND_URL;

export async function streamChatResponse(
  request: ChatRequest,
  onChunk: (text: string) => void
): Promise<void> {
  const response = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
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
  const res = await fetch(`${BASE_URL}/log/final_recs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
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
