import { getSupabaseAccessToken } from "./lib/session";

export const BASE_URL = import.meta.env.VITE_BACKEND_URL;

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
