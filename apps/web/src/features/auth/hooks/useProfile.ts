import { useAppUser } from "./useAppUser";

export function useProfile(userId?: string | null) {
  const { data, isLoading } = useAppUser(userId);
  return { displayName: data?.display_name ?? null, loading: isLoading } as const;
}
