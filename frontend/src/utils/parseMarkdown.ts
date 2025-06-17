export type ParsedMovie = {
  mediaId: number;
  title: string;
  posterUrl: string;
  backdropUrl: string;
  genres: string[];
  imdbRating: number;
  rottenTomatoesRating: number;
  trailerKey?: string;
  why: string;
};

export function parseMarkdown(markdown: string): ParsedMovie[] {
  const movieBlocks = markdown.split(/### \d+\.\s+/).slice(1);
  return movieBlocks.map((block) => {
    const titleMatch = block.match(/^(.*?)\n/);
    const title = titleMatch?.[1].trim() ?? "Untitled";

    const posterMatch = block.match(/- POSTER_PATH:\s*(.*)/);
    const backdropMatch = block.match(/- BACKDROP_PATH:\s*(.*)/);
    const genresMatch = block.match(/- GENRES:\s*(.*)/);
    const imdbMatch = block.match(/- IMDB_RATING:\s*(.*)/);
    const rtMatch = block.match(/- ROTTEN_TOMATOES_RATING:\s*(.*)/);
    const trailerMatch = block.match(/- TRAILER_KEY:\s*(.*)/);
    const mediaIdMatch = block.match(/- MEDIA_ID:\s*(\d+)/);
    const whyMatch = block.match(/- WHY_YOU_MIGHT_ENJOY_IT:\s*([\s\S]*)/);

    return {
      mediaId: mediaIdMatch ? parseInt(mediaIdMatch[1]) : -1,
      title,
      posterUrl: posterMatch ? `https://image.tmdb.org/t/p/w500${posterMatch[1]}` : "",
      backdropUrl: backdropMatch ? `https://image.tmdb.org/t/p/original${backdropMatch[1]}` : "",
      genres: genresMatch ? genresMatch[1].split(",").map((g) => g.trim()) : [],
      imdbRating: imdbMatch ? parseFloat(imdbMatch[1]) : 0,
      rottenTomatoesRating: rtMatch ? parseInt(rtMatch[1]) : 0,
      trailerKey: trailerMatch?.[1],
      why: whyMatch?.[1].trim() ?? "",
    };
  });
}
