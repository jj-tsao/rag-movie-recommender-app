import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Session, User, AuthChangeEvent } from "@supabase/supabase-js";
import type { TablesInsert } from "@/types/supabase";
import { getCurrentSession, onAuthStateChange, upsertAppUser } from "../api";
import { useAppUser } from "./useAppUser";

type AuthState = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  lastEvent: AuthChangeEvent | null;
};

export function useAuth() {
  const [state, setState] = useState<AuthState>({ user: null, session: null, loading: true, lastEvent: null });
  const queryClient = useQueryClient();

  async function refresh() {
    const session = await getCurrentSession();
    setState((s) => ({ ...s, session, user: session?.user ?? null, loading: false }));
  }

  // Effect 1: bootstrap session + listen for auth changes
  useEffect(() => {
    let mounted = true;
    (async () => {
      const session = await getCurrentSession();
      if (!mounted) return;
      setState((s) => ({ ...s, session, user: session?.user ?? null, loading: false }));
    })();
    const unsubscribe = onAuthStateChange((event) => {
      setState((s) => ({ ...s, lastEvent: event }));
      refresh();
    });
    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

  // Query app_user profile (deduplicated + cached via React Query)
  const userId = !state.loading ? state.user?.id : undefined;
  const { data: appUser, isSuccess: appUserReady } = useAppUser(userId);

  // Effect 2: ensure app_user profile exists + handle pending display name
  const didSync = useRef(false);
  useEffect(() => {
    if (!state.user || state.loading || !appUserReady || didSync.current) return;
    didSync.current = true;

    (async () => {
      try {
        const pending = localStorage.getItem("pendingDisplayName");

        if (!appUser || (!appUser.display_name && pending)) {
          const cleanEmail =
            typeof state.user!.email === "string" && state.user!.email.trim().length > 0
              ? state.user!.email.trim()
              : null;
          const payload: TablesInsert<"app_user"> = {
            user_id: state.user!.id,
            email: (cleanEmail ?? null) as unknown as string,
          };
          const displayName = pending || state.user!.user_metadata?.display_name;
          if (typeof displayName === "string" && displayName.trim().length > 0) {
            payload.display_name = displayName.trim();
          }
          await upsertAppUser(payload);
          queryClient.invalidateQueries({ queryKey: ["app_user", state.user!.id] });
        }

        if (pending) {
          try {
            localStorage.setItem(`profileDisplayName:${state.user!.id}`, pending);
          } catch {
            // no-op
          }
          localStorage.removeItem("pendingDisplayName");
        }
      } catch (error) {
        console.warn("Failed to ensure app_user profile", error);
      }
    })();
  }, [state.user?.id, state.loading, appUserReady, appUser]);

  // Reset sync guard when user changes
  useEffect(() => {
    didSync.current = false;
  }, [state.user?.id]);

  return state;
}
