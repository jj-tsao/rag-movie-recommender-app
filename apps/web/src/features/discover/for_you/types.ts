export interface DiscoverCardData {
  id?: string;
  mediaId: string;
  title: string;
  releaseYear?: number;
  posterUrl?: string;
  backdropUrl?: string;
  trailerKey?: string;
  genres: string[];
  providers: string[];
  imdbRating?: number | null;
  rottenTomatoesRating?: number | null;
  whyMarkdown?: string;
  whyText?: string;
  whySource?: "cache" | "llm";
  isWhyLoading: boolean;
  isRatingsLoading: boolean;
}
