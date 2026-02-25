export const EXPLORE_COPY = {
  hero: {
    heading: "Find your next watch. Curated to your taste.",
    subheading:
      "Your personal AI curator. Reelix understands your taste and brings you films you'll genuinely love.",
  },
  status: {
    findingPicks: "Finding picks",
    curatingPicks: "Curating picks for you",
    hangTight: "Hang tight while we tailor recommendations.",
    streamingReasons: "Streaming personalized reasons...",
    shapingRecs: "Shaping your recommendations...",
    refineVibe: "Refine your vibe and resubmit.",
    showingResults: (query: string) => `Showing results for "${query}"`,
  },
  loading: {
    curatingHeading: "Curating picks for you",
    curatingBody: "Hang tight while we tailor recommendations.",
  },
  empty: {
    noPicks: "No picks yet. Try a different vibe.",
  },
  chat: {
    fallback: "Here's what we found.",
  },
  error: {
    unauthorized: "Sign in to explore recommendations tailored to you.",
    signInPrompt: "Sign in to get personalized explore recommendations.",
    somethingWrong: "Something went wrong",
    fetchFailed: "Could not fetch recommendations right now.",
    streamFailed: "Could not finish streaming reasons.",
    refreshFailed: "Please try adjusting your filters again.",
  },
} as const;