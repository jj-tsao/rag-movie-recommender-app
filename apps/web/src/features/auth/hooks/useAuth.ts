import { useEffect, useState } from "react";
import type { Session, User, AuthChangeEvent } from "@supabase/supabase-js";
import type { TablesInsert } from "@/types/supabase";
import { getAppUser, getCurrentSession, onAuthStateChange, upsertAppUser } from "../api";

type AuthState = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  lastEvent: AuthChangeEvent | null;
};

export function useAuth() {
  const [state, setState] = useState<AuthState>({ user: null, session: null, loading: true, lastEvent: null });

  async function refresh() {
    const session = await getCurrentSession();
    setState((s) => ({ ...s, session, user: session?.user ?? null, loading: false }));
  }

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

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!state.user || state.loading) return;
      try {
        const existing = await getAppUser(state.user.id);
        if (cancelled) return;
        if (!existing) {
          const cleanEmail =
            typeof state.user.email === "string" && state.user.email.trim().length > 0
              ? state.user.email.trim()
              : null;
          const payload: TablesInsert<"app_user"> = {
            user_id: state.user.id,
            email: (cleanEmail ?? null) as unknown as string,
          };
          const displayName = state.user.user_metadata?.display_name;
          if (typeof displayName === "string" && displayName.trim().length > 0) {
            payload.display_name = displayName.trim();
          }
          await upsertAppUser(payload);
        }
      } catch (error) {
        console.warn("Failed to ensure app_user profile", error);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [state.user?.id, state.user?.email, state.user?.user_metadata, state.loading]);

  // On first authenticated load, if we have a pending display name from sign up,
  // upsert the app_user profile and clear the pending value.
  useEffect(() => {
    (async () => {
      if (!state.user || state.loading) return;
      try {
        const pending = localStorage.getItem("pendingDisplayName");
        if (!pending) return;
        const existing = await getAppUser(state.user.id);
        if (!existing || !existing.display_name) {
          const cleanEmail =
            typeof state.user.email === "string" && state.user.email.trim().length > 0
              ? state.user.email.trim()
              : null;
          await upsertAppUser({
            user_id: state.user.id,
            email: (cleanEmail ?? null) as unknown as string,
            display_name: pending,
          });
        }
        try {
          localStorage.setItem(`profileDisplayName:${state.user.id}`, pending);
        } catch (e) {
          void e; // no-op
        }
        localStorage.removeItem("pendingDisplayName");
      } catch (e) {
        void e; // no-op
      }
    })();
  }, [state.user?.id, state.user, state.loading]);

  return state;
}
