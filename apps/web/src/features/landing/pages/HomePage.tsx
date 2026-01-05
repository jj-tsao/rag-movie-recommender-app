import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { getAccessToken } from "@/features/discover/for_you/api";
import { hasTasteProfile } from "@/features/taste_profile/api";
import { getExploreRedirectFlag } from "@/utils/exploreRedirect";
import LandingPage from "./LandingPage";

type HomeState = "checking" | "landing";

export default function HomePage() {
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [state, setState] = useState<HomeState>("checking");

  useEffect(() => {
    let cancelled = false;

    if (loading) {
      return () => {
        cancelled = true;
      };
    }

    if (!user) {
      if (getExploreRedirectFlag()) {
        navigate("/discover/explore", { replace: true });
        return () => {
          cancelled = true;
        };
      }
      setState("landing");
      return () => {
        cancelled = true;
      };
    }

    const checkProfile = async () => {
      setState("checking");
      try {
        const token = await getAccessToken();
        if (cancelled) return;
        if (!token) {
          setState("landing");
          return;
        }

        const profileExists = await hasTasteProfile(token);
        if (cancelled) return;
        if (profileExists) {
          navigate("/discover/for-you", { replace: true });
          return;
        }

        if (getExploreRedirectFlag()) {
          navigate("/discover/explore", { replace: true });
          return;
        }

        setState("landing");
      } catch (error) {
        void error;
        if (!cancelled) {
          if (getExploreRedirectFlag()) {
            navigate("/discover/explore", { replace: true });
            return;
          }
          setState("landing");
        }
      }
    };

    void checkProfile();

    return () => {
      cancelled = true;
    };
  }, [loading, user?.id, navigate]);

  if (state === "checking") {
    return null;
  }

  return <LandingPage />;
}
