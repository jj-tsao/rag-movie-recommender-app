import { BASE_URL } from "@/api";

export interface TasteProfileHttpError extends Error {
  status?: number;
}

export async function hasTasteProfile(token: string): Promise<boolean> {
  const response = await fetch(`${BASE_URL}/v2/users/me/taste_profile`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status === 404) {
    return false;
  }

  if (response.status === 401 || response.status === 403) {
    const error: TasteProfileHttpError = new Error("Unauthorized");
    error.status = response.status;
    throw error;
  }

  if (!response.ok) {
    let detail: string | null = null;
    try {
      detail = await response.text();
    } catch (error) {
      void error;
    }
    const error: TasteProfileHttpError = new Error(detail || `Taste profile check failed (${response.status})`);
    error.status = response.status;
    throw error;
  }

  return true;
}
