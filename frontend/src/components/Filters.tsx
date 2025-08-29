import React from "react";
import type { FilterSettings } from "../types/types";
import MultiSelectDropdown from "./MultiSelectDropdown";
import YearRangeSlider from "./YearRangeSlider";

type Props = {
  filters: FilterSettings;
  setFilters: React.Dispatch<React.SetStateAction<FilterSettings>>;
};

export default function Filters({ filters, setFilters }: Props) {
  const movie_genres = [
    "Action",
    "Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "History",
    "Horror",
    "Music",
    "Mystery",
    "Romance",
    "Science Fiction",
    "TV Movie",
    "Thriller",
    "War",
    "Western",
  ];

  const tv_genres = [
    "Action & Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Kids",
    "Mystery",
    "News",
    "Reality",
    "Sci-Fi & Fantasy",
    "Soap",
    "Talk",
    "War & Politics",
    "Western",
  ];

  const providers = [
    "Netflix",
    "Hulu",
    "Max",
    "Amazon Prime Video",
    "Disney Plus",
    "Apple TV+",
    "Paramount Plus",
    "Paramount+ with Showtime",
    "Peacock Premium",
    "Crunchyroll",
    "MGM Plus",
    "fuboTV",
    "Starz",
    "AMC+",
    "Tubi TV",
    "Philo",
    "Sling TV",
  ];

  return (
    <div className="flex flex-wrap gap-4">
      <div className="w-full">
        <MultiSelectDropdown
          label="Streaming Services"
          options={providers}
          selected={filters.providers}
          onChange={(providers: string[]) =>
            setFilters((f) => ({ ...f, providers }))
          }
        />
      </div>

      <div className="w-full">
        <MultiSelectDropdown
          label="Genres"
          options={filters.media_type === "movie" ? movie_genres : tv_genres}
          selected={filters.genres}
          onChange={(genres: string[]) => setFilters((f) => ({ ...f, genres }))}
        />
      </div>

      <div className="w-full px-1">
        <YearRangeSlider
          min={1970}
          max={2025}
          values={filters.year_range}
          onChange={(range: [number, number]) =>
            setFilters((f) => ({ ...f, year_range: range }))
          }
        />
      </div>
    </div>
  );
}
