import type { ParsedMovie } from "../utils/parseMarkdown";
import { hasAnyRating, hasValidScore } from "@/utils/checkScores";
import { Card, CardContent } from "@/components/ui/card";

interface Props {
  movie: ParsedMovie;
}

export default function MovieCard({ movie }: Props) {
  const hasRating = hasAnyRating(movie);
  return (
    <Card className="relative group overflow-hidden rounded-xl border border-white/10 text-white hover:scale-101 transition-all duration-200 hover:shadow-[0_8px_30px_rgba(0,0,0,0.4)]">
      {/* Backdrop image */}
      {movie.backdropUrl && (
        <div className="absolute inset-0 z-0">
          {/* Darkened backdrop */}
          <div
            className="h-full w-full bg-cover bg-center blur-[1px] opacity-15 group-hover:opacity-20 transition-opacity duration-300"
            style={{ backgroundImage: `url(${movie.backdropUrl})` }}
          />
          {/* Gradient for legibility */}
          <div className="absolute inset-0 bg-gradient-to-b from-slate-800/80 via-black/40 to-transparent" />
        </div>
      )}

      <CardContent className="relative z-10 flex flex-col md:flex-row gap-4 p-4">
        <div className="flex-shrink-0 w-full md:w-45 lg:w-45 mx-auto md:mx-0">
          <img
            src={movie.posterUrl}
            alt={movie.title}
            className="rounded-lg w-full h-auto object-cover"
          />
        </div>

        <div className="flex-1 flex flex-col justify-between text-sm text-zinc-200">
          <div>
            <h2 className="text-2xl font-semibold text-white leading-tight pt-2 pb-2">
              {movie.title}
            </h2>
            <div className="text-sm text-zinc-300 mt-1 leading-relaxed">
              <span className="font-medium">Genres:</span>{" "}
              {movie.genres.join(", ")}
              <br />
              {hasRating && (
                <p className="text-sm text-muted-foreground">
                  {hasValidScore(movie.imdbRating) && (
                    <span>⭐ {movie.imdbRating}/10</span>
                  )}
                  {hasValidScore(movie.imdbRating) &&
                    hasValidScore(movie.rottenTomatoesRating) && (
                      <span className="mx-2">|</span>
                    )}
                  {hasValidScore(movie.rottenTomatoesRating) && (
                    <span>🍅 {movie.rottenTomatoesRating}%</span>
                  )}
                </p>
              )}
            </div>
            <p className="text-base text-zinc-300 mt-2 whitespace-pre-line">
              <span className="font-bold">Why You Might Enjoy It:</span>{" "}
              {movie.why}
            </p>
            {movie.trailerKey && (
              <p className="mt-3 text-base">
                <a
                  href={`https://www.youtube.com/watch?v=${movie.trailerKey}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center text-base text-blue-300 hover:underline"
                >
                  <img
                    src="/icons/play_icon.png"
                    alt="Play"
                    className="h-6 w-auto mr-1"
                  />
                  Watch Trailer
                </a>
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
