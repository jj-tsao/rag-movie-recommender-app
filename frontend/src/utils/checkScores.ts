export function hasValidScore(value: number | string | undefined): boolean {
  if (typeof value === "number") {
    return !isNaN(value) && value > 0;
  }
  return value !== "N/A" && value !== undefined && value !== null;
}

export function hasAnyRating(movie: {
  imdbRating?: number | string;
  rottenTomatoesRating?: number | string;
}): boolean {
  return (
    hasValidScore(movie.imdbRating) || hasValidScore(movie.rottenTomatoesRating)
  );
}

