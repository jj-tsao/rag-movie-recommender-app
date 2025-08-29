import ChatBox from "./ChatBox";
import Filters from "./Filters";
import FloatingActionButton from "./FloatingActionButton";
import type { FilterSettings } from "../types/types";
import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronUp } from "lucide-react";

function ActiveFilterPill({
  label,
  onClear,
}: {
  label: string;
  onClear: () => void;
}) {
  return (
    <div className="inline-flex items-center bg-muted text-xs text-foreground px-2 h-6 rounded-full border border-border shadow-sm mr-2 mb-2">
      <span className="leading-none truncate">{label}</span>
      <button
        onClick={onClear}
        className="ml-1 text-muted-foreground hover:text-foreground leading-none"
        aria-label={`Remove ${label}`}
      >
        ✕
      </button>
    </div>
  );
}

export default function Home() {
  const [filters, setFilters] = useState<FilterSettings>({
    media_type: "movie",
    genres: [],
    providers: [],
    year_range: [1970, 2025],
  });

  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [submissionId, setSubmissionId] = useState(0);
  const [showFilters, setShowFilters] = useState(false);
  const [responseFinished, setResponseFinished] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputVisible, setInputVisible] = useState(true);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const inputPanelRef = useRef<HTMLDivElement | null>(null);
  const location = useLocation();

  const placeholderExamples = [
    "Like: 🚀 Mind-bending sci-fi with philosophical undertones and existential stakes",
    "Like: 🎥 Psychological thrillers that are character-driven, satirical, and thought-provoking",
    "Like: 💕 Heartwarming coming-of-age stories that explore friendship, growth, and family bonds",
    "Like: 🕵️‍♂️ Slow-burn crime dramas with a dark, gritty atmosphere and morally gray characters",
    "Like: 😆 Offbeat indie comedies with quirky charm and emotional depth",
    "Like: 🌷 Playful rom-coms with quirky characters, heartfelt moments, and a touch of melancholic realism",
    "Like: 🎵 Visually lush musical dramas that blend artistic ambition with emotional resonance",
  ];

  useEffect(() => {
    if (location.pathname === "/") {
      setQuestion("");
      setSubmittedQuestion("");
      setSubmissionId(0);
      setResponseFinished(false);
      setIsStreaming(false);
      setShowFilters(false);
      setFilters({
        media_type: "movie",
        genres: [],
        providers: [],
        year_range: [1970, 2025],
      });
    }
  }, [location.pathname]);

  useEffect(() => {
    setFilters((prev) => ({ ...prev, genres: [] }));
  }, [filters.media_type]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setInputVisible(entry.isIntersecting),
      { threshold: 0.1 }
    );
    if (inputPanelRef.current) observer.observe(inputPanelRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (question) return;
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % placeholderExamples.length);
    }, 6000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question]);

  const dynamicPlaceholder = `${placeholderExamples[placeholderIndex]}`;

  const handleSubmit = () => {
    if (isStreaming || !question.trim()) return;
    setSubmittedQuestion(question);
    setSubmissionId((id) => id + 1);
    setQuestion("");
    setResponseFinished(false);
    setShowFilters(false);
  };

  const showActiveFilters =
    !showFilters &&
    (filters.genres.length > 0 ||
      filters.providers.length > 0 ||
      filters.year_range[0] !== 1970 ||
      filters.year_range[1] !== 2025);

  return (
    <main className="pt-8 px-4 sm:px-6 lg:px-8 pb-6 flex flex-col gap-8 min-h-[100dvh]">
      <div ref={inputPanelRef} className="space-y-4 max-w-2xl mx-auto w-full">
        <h1 className="text-4xl font-semibold text-center leading-snug">
          Find the Reel.
          <br className="block sm:hidden" />
          <span className="hidden sm:inline"> </span>Feel the Story.
        </h1>
        <div className="text-sm text-center text-muted-foreground">
          Describe the vibe you're in — Reelix will find the perfect movie or
          show for you
        </div>

        <div className="relative">
          <Textarea
            className="text-sm px-3 py-2 bg-background text-foreground placeholder-transparent"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            rows={3}
            placeholder=" "
            disabled={isStreaming}
          />
          {!question && (
            <div
              key={placeholderIndex}
              className="absolute top-2.5 left-3 text-sm text-muted-foreground pointer-events-none animate-[fade-in-out_6s_ease-in-out]"
            >
              {dynamicPlaceholder}
            </div>
          )}
        </div>

        <Tabs
          value={filters.media_type}
          onValueChange={(val) =>
            setFilters((prev) => ({
              ...prev,
              media_type: val as "movie" | "tv",
            }))
          }
          defaultValue="movie"
        >
          <TabsList className="flex w-full bg-muted">
            <TabsTrigger
              value="movie"
              className="flex-1 text-center data-[state=active]:bg-primary data-[state=active]:text-white dark:data-[state=active]:bg-primary "
            >
              🎬 Movies
            </TabsTrigger>
            <TabsTrigger
              value="tv"
              className="flex-1 text-center data-[state=active]:bg-primary data-[state=active]:text-white dark:data-[state=active]:bg-primary "
            >
              📺 TV Shows
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <Collapsible open={showFilters} onOpenChange={setShowFilters}>
          <CollapsibleTrigger asChild>
            <Button
              variant="secondary"
              className="w-full justify-between flex text-muted-foreground"
            >
              Advanced Filters
              {showFilters ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-4">
            <Filters filters={filters} setFilters={setFilters} />
          </CollapsibleContent>
        </Collapsible>

        {showActiveFilters && (
          <div className="mt-2 flex flex-wrap items-center text-muted-foreground">
            {filters.providers.map((provider) => (
              <ActiveFilterPill
                key={provider}
                label={provider}
                onClear={() =>
                  setFilters((prev) => ({
                    ...prev,
                    providers: prev.providers.filter((p) => p !== provider),
                  }))
                }
              />
            ))}
            {filters.genres.map((genre) => (
              <ActiveFilterPill
                key={genre}
                label={genre}
                onClear={() =>
                  setFilters((prev) => ({
                    ...prev,
                    genres: prev.genres.filter((g) => g !== genre),
                  }))
                }
              />
            ))}

            {(filters.year_range[0] !== 1970 ||
              filters.year_range[1] !== 2025) && (
              <ActiveFilterPill
                label={`Year: ${filters.year_range[0]}–${filters.year_range[1]}`}
                onClear={() =>
                  setFilters((prev) => ({
                    ...prev,
                    year_range: [1970, 2025],
                  }))
                }
              />
            )}
            <Button
              variant="link"
              className="text-xs itemalgin underline mb-2 mr-2"
              onClick={() =>
                setFilters((prev) => ({
                  ...prev,
                  genres: [],
                  providers: [],
                  year_range: [1970, 2025],
                }))
              }
            >
              Clear All
            </Button>
          </div>
        )}

        <Button
          className="w-full"
          onClick={handleSubmit}
          disabled={isStreaming}
        >
          {isStreaming ? "Thinking..." : "Get Recommendations!"}
        </Button>
      </div>

      <div className="max-w-6xl mx-auto w-full px-2 sm:px-4 flex-1">
        {submittedQuestion && (
          <div className="rounded-xl bg-muted p-6 shadow-sm">
            <ChatBox
              key={submittedQuestion + submissionId}
              question={submittedQuestion}
              filters={filters}
              onDoneStreaming={() => setResponseFinished(true)}
              onStreamingStatusChange={setIsStreaming}
            />
          </div>
        )}
      </div>

      {responseFinished && !inputVisible && (
        <FloatingActionButton
          label="✨ New Recommendations"
          onClick={() =>
            inputPanelRef.current?.scrollIntoView({
              behavior: "smooth",
              block: "center",
            })
          }
        />
      )}
    </main>
  );
}
