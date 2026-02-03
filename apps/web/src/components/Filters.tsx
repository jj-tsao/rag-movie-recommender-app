import React from "react";
import type { FilterSettings } from "../types/types";
import MultiSelectDropdown from "./MultiSelectDropdown";
import YearRangeSlider from "./YearRangeSlider";
import { getProviderIdByName } from "@/data/watchProviders";
import { YEAR_RANGE_MAX, YEAR_RANGE_MIN } from "@/utils/yearRange";

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
    "HBO Max",
    "Disney Plus",
    "Apple TV+",
    "Amazon Prime Video",
    "Paramount Plus",
    "Paramount+ with Showtime",
    "Peacock Premium",
    "Crunchyroll",
    "MGM Plus",
    "fuboTV",
    "Starz",
    "AMC+",
    "BritBox",
    "Acorn TV",
    "Criterion Channel",
    "Tubi TV",
    "Pluto TV",
    "The Roku Channel",
  ].filter((name) => getProviderIdByName(name) !== undefined);

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
          min={YEAR_RANGE_MIN}
          max={YEAR_RANGE_MAX}
          values={filters.year_range}
          onChange={(range: [number, number]) =>
            setFilters((f) => ({ ...f, year_range: range }))
          }
        />
      </div>
    </div>
  );
}
