import { useState } from "react";
import { useNavigate } from "react-router-dom";
import GenresStep from "../components/GenresStep";
import RateSeedMoviesStep from "../components/RateSeedMoviesStep";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { upsertUserPreferences } from "../api";
import { useToast } from "@/components/ui/useToast";

export default function TasteOnboardingPage() {
  const { user, loading } = useAuth();
  const { toast } = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<"genres" | "rate">("genres");
  const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
  const [selectedVibes, setSelectedVibes] = useState<string[]>([]);
  const navigate = useNavigate();

  function goToDiscover(firstRun = false) {
    navigate(firstRun ? "/discover/for-you?first_run=1" : "/discover/for-you");
  }

  async function handleGenresSubmit({
    genres,
    vibeTags,
  }: {
    genres: string[];
    vibeTags: string[];
  }) {
    if (!user) {
      toast({
        title: "Sign In",
        description: "Please sign in to build your taste profile.",
      });
      return;
    }
    try {
      setSubmitting(true);
      await upsertUserPreferences({
        genres,
        keywords: vibeTags,
      });
      toast({
        title: "Saved",
        description:
          "Preferences updated. Next, we’ll ask you to rate a few titles.",
      });
      setSelectedGenres(genres);
      setSelectedVibes(vibeTags);
      setStep("rate");
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Something went wrong";
      toast({
        title: "Failed to save",
        description: message,
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return null;

  if (step === "genres") {
    return (
      <GenresStep
        onSubmit={handleGenresSubmit}
        submitting={submitting}
        initialGenres={selectedGenres}
        initialVibes={selectedVibes}
      />
    );
  }

  if (step === "rate") {
    return (
      <RateSeedMoviesStep
        genres={selectedGenres}
        onBack={() => setStep("genres")}
        onFinish={(ratings) => {
          console.log("Collected ratings:", ratings);
          goToDiscover(true);
        }}
      />
    );
  }

  return null;
}
