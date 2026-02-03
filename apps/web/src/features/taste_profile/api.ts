import { BASE_URL } from "@/api";
import { getResponseErrorMessage } from "@/lib/errors";

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
    const error: TasteProfileHttpError = new Error(
      getResponseErrorMessage(response, `Taste profile check failed (${response.status})`)
    );
    error.status = response.status;
    throw error;
  }

  return true;
}
