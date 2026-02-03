import { BASE_URL } from "@/api";
import { getResponseErrorMessage } from "@/lib/errors";
import { getSupabaseAccessToken } from "@/lib/session";
import { supabase } from "@/lib/supabase";
import { getSessionId } from "@/utils/session";
import type { Json, TablesInsert } from "@/types/supabase";

export async function upsertUserPreferences(payload: {
  genres: string[];
  keywords: string[];
}): Promise<void> {
  const token = await getSupabaseAccessToken();
  if (!token) {
    throw new Error("Not signed in");
  }

  const response = await fetch(`${BASE_URL}/v2/users/me/settings/preferences`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      genres_include: payload.genres,
      keywords_include: payload.keywords,
    }),
  });

  if (!response.ok) {
    throw new Error(getResponseErrorMessage(response, "Failed to save preferences"));
  }
}

// ---------- Taste Onboarding → user_interactions ----------
export type RatingValue = "love" | "like" | "dislike" | "dismiss";

const DEFAULT_INTERACTION_SOURCE = "taste_onboarding";
const REACTION_EVENT_TYPE = "rec_reaction";
const VALID_REACTIONS = new Set<Exclude<RatingValue, "dismiss">>([
  "love",
  "like",
  "dislike",
]);

// Canonical event names match DB check constraint exactly; map only weights.
const EVENT_WEIGHT: Record<string, number> = {
  love: 2.0,
  like: 1.0,
  dislike: -1.5,
  dismiss: 0.0,
  trailer_view: 0.35,
};

type UserInteractionInsert = TablesInsert<"user_interactions"> & { title: string };

async function upsertInteractionRow(row: UserInteractionInsert, source: string) {
  // Always migrate legacy rows to set the concrete source column
  const updatePayload = {
    event_type: row.event_type,
    weight: row.weight,
    context_json: row.context_json,
    occurred_at: row.occurred_at,
    source,
    title: row.title,
  } satisfies Partial<UserInteractionInsert>;

  // 1) Update rows that already have matching source in the column
  {
    const { data, error } = await supabase
      .from("user_interactions")
      .update(updatePayload)
      .eq("user_id", row.user_id)
      .eq("media_id", row.media_id)
      .eq("media_type", row.media_type)
      .eq("source", source)
      .select("interaction_id");
    if (error) throw new Error(error.message);
    if ((data?.length ?? 0) > 0) return;
  }

  // 2) Update legacy rows that stored source in context_json
  {
    const { data, error } = await supabase
      .from("user_interactions")
      .update(updatePayload)
      .eq("user_id", row.user_id)
      .eq("media_id", row.media_id)
      .eq("media_type", row.media_type)
      .eq("context_json->>source", source)
      .select("interaction_id");
    if (error) throw new Error(error.message);
    if ((data?.length ?? 0) > 0) return;
  }

  // 3) Update the most recent legacy row with unknown source (if any)
  {
    const { data: legacy, error: legacyErr } = await supabase
      .from("user_interactions")
      .select("interaction_id")
      .eq("user_id", row.user_id)
      .eq("media_id", row.media_id)
      .eq("media_type", row.media_type)
      .eq("source", "unknown")
      .order("occurred_at", { ascending: false })
      .limit(1);
    if (legacyErr) throw new Error(legacyErr.message);
    if (legacy && legacy.length > 0) {
      const id = legacy[0].interaction_id as number;
      const { error: updErr } = await supabase
        .from("user_interactions")
        .update(updatePayload)
        .eq("interaction_id", id);
      if (updErr) throw new Error(updErr.message);
      return;
    }
  }

  // 4) No existing row matched: use upsert on the unique key to avoid conflicts
  const { error: upsertErr } = await supabase
    .from("user_interactions")
    .upsert(row, { onConflict: "user_id, media_id, media_type, source" });
  if (upsertErr) {
    // Fallback: if ON CONFLICT isn't supported or RLS interferes, try a targeted update
    const { error: retryUpdErr } = await supabase
      .from("user_interactions")
      .update(updatePayload)
      .eq("user_id", row.user_id)
      .eq("media_id", row.media_id)
      .eq("media_type", row.media_type)
      .eq("source", source);
    if (retryUpdErr) throw new Error(upsertErr.message);
  }
}

export function canonicalizeTag(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_{2,}/g, "_");
}

type RecReaction = Exclude<RatingValue, "dismiss">;

type LogRecReactionArgs = {
  mediaId: number | string;
  title: string;
  reaction: RecReaction;
  source?: string;
  mediaType?: "movie" | "tv";
  position?: number | null;
  queryId?: string | null;
};

type InteractionApiPayload = {
  media_type: "movie" | "tv";
  media_id: number;
  title: string;
  event_type: typeof REACTION_EVENT_TYPE;
  reaction: RecReaction;
  source: string;
  position?: number;
  session_id: string;
  query_id?: string;
};

export async function logUserRecReaction({
  mediaId,
  title,
  reaction,
  source,
  mediaType = "movie",
  position,
  queryId,
}: LogRecReactionArgs): Promise<void> {
  if (!VALID_REACTIONS.has(reaction)) {
    throw new Error("Invalid reaction");
  }

  const numericId = Number(mediaId);
  if (!Number.isFinite(numericId)) {
    throw new Error("Invalid media_id");
  }

  const token = await getSupabaseAccessToken();
  if (!token) {
    throw new Error("Not signed in");
  }

  const sessionId = getSessionId();
  const normalizedQueryId =
    typeof queryId === "string" && queryId.trim().length > 0 ? queryId.trim() : null;

  const normalizedPosition =
    typeof position === "number" && Number.isFinite(position) && position > 0
      ? Math.max(1, Math.trunc(position))
      : null;

  const payload: InteractionApiPayload = {
    media_type: mediaType,
    media_id: numericId,
    title,
    event_type: REACTION_EVENT_TYPE,
    reaction,
    source: source ?? DEFAULT_INTERACTION_SOURCE,
    session_id: sessionId,
    ...(normalizedPosition ? { position: normalizedPosition } : {}),
    ...(normalizedQueryId ? { query_id: normalizedQueryId } : {}),
  };

  const response = await fetch(`${BASE_URL}/v2/interactions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(getResponseErrorMessage(response, "Failed to log reaction"));
  }
}

// Upsert a single interaction on each rating click.
export async function upsertUserInteraction(
  item: {
    media_id: number | string;
    title: string;
    vibes?: string[];
    rating?: RatingValue;
    eventType?: string;
    weightOverride?: number;
  },
  options?: {
    source?: string;
    mediaType?: "movie" | "tv";
  },
) {
  const { data: auth } = await supabase.auth.getUser();
  const user = auth?.user;
  if (!user) throw new Error("Not signed in");

  const mediaId = Number(item.media_id);
  if (!Number.isFinite(mediaId)) throw new Error("Invalid media_id");

  const eventType = item.eventType ?? item.rating ?? "feedback";
  const weight = item.weightOverride ?? EVENT_WEIGHT[item.rating ?? eventType] ?? 0;
  const supabaseSource = options?.source ?? DEFAULT_INTERACTION_SOURCE;
  const context: Json = {
    tags: (item.vibes ?? []).map(canonicalizeTag),
    source: supabaseSource,
  };
  const mediaType = options?.mediaType ?? "movie";
  const row: UserInteractionInsert = {
    user_id: user.id,
    media_id: mediaId,
    media_type: mediaType,
    event_type: eventType,
    weight,
    context_json: context,
    occurred_at: new Date().toISOString(),
    source: supabaseSource,
    title: item.title,
  };

  await upsertInteractionRow(row, supabaseSource);
}

// ---------- Streaming providers (user_subscriptions) ----------

export async function getActiveSubscriptionIds(): Promise<number[]> {
  const { data: auth } = await supabase.auth.getUser();
  const user = auth?.user;
  if (!user) throw new Error("Not signed in");

  const { data, error } = await supabase
    .from("user_subscriptions")
    .select("provider_id, active")
    .eq("user_id", user.id);
  if (error) throw new Error(error.message);

  return (data ?? [])
    .filter((r) => r.active === true)
    .map((r) => Number(r.provider_id))
    .filter((n) => Number.isFinite(n));
}

export async function upsertUserSubscriptions(providerIds: number[]): Promise<void> {
  const { data: auth } = await supabase.auth.getUser();
  const user = auth?.user;
  if (!user) throw new Error("Not signed in");

  const { data: existing, error: existingErr } = await supabase
    .from("user_subscriptions")
    .select("provider_id, active")
    .eq("user_id", user.id);
  if (existingErr) throw new Error(existingErr.message);

  const now = new Date().toISOString();
  const selected = new Set<number>(providerIds.map((n) => Number(n)));

  // Split into two operations to keep types precise and avoid `any` casts.
  const toActivate: TablesInsert<"user_subscriptions">[] = Array.from(selected).map((pid) => ({
    user_id: user.id,
    provider_id: pid,
    active: true,
    updated_at: now,
  }));

  const toDeactivate: number[] = (existing ?? [])
    .filter((r) => r.active === true && !selected.has(Number(r.provider_id)))
    .map((r) => Number(r.provider_id));

  if (toActivate.length > 0) {
    const { error } = await supabase
      .from("user_subscriptions")
      .upsert(toActivate, { onConflict: "user_id, provider_id" });
    if (error) throw new Error(error.message);
  }

  if (toDeactivate.length > 0) {
    const { error } = await supabase
      .from("user_subscriptions")
      .update({ active: false, updated_at: now })
      .eq("user_id", user.id)
      .in("provider_id", toDeactivate);
    if (error) throw new Error(error.message);
  }
}

// ---------- User settings: provider filter mode ----------
export type ProviderFilterMode = "ALL" | "SELECTED";

export async function setProviderFilterMode(mode: ProviderFilterMode): Promise<void> {
  const { data: auth } = await supabase.auth.getUser();
  const user = auth?.user;
  if (!user) throw new Error("Not signed in");

  const payload: TablesInsert<"user_settings"> = {
    user_id: user.id,
    provider_filter_mode: mode,
  };

  const { error } = await supabase
    .from("user_settings")
    .upsert(payload, { onConflict: "user_id" });
  if (error) throw new Error(error.message);
}
