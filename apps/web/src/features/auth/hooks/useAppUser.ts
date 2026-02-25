import { useQuery } from "@tanstack/react-query";
import { getAppUser } from "../api";

export function useAppUser(userId: string | undefined | null) {
  return useQuery({
    queryKey: ["app_user", userId],
    queryFn: () => getAppUser(userId!),
    enabled: !!userId,
    staleTime: 5 * 60 * 1000,
  });
}
