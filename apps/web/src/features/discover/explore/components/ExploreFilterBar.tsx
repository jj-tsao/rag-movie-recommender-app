import StreamingServiceFilterChip from "@/features/discover/for_you/components/StreamingServiceFilterChip";
import YearRangeFilterChip from "./YearRangeFilterChip";
import { DEFAULT_YEAR_RANGE } from "@/utils/yearRange";

interface ExploreFilterBarProps {
  selectedProviders: string[];
  onProviderApply: (providers: string[]) => void;
  selectedYearRange: [number, number] | null;
  onYearApply: (range: [number, number] | null) => void;
  excludedGenres?: string[];
  compact?: boolean;
}

export function ExploreFilterBar({
  selectedProviders,
  onProviderApply,
  selectedYearRange,
  onYearApply,
  excludedGenres,
  compact = false,
}: ExploreFilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <StreamingServiceFilterChip
        selected={selectedProviders}
        onApply={onProviderApply}
        dropdownDirection="up"
        compact={compact}
      />
      <YearRangeFilterChip
        value={selectedYearRange}
        onApply={onYearApply}
        min={DEFAULT_YEAR_RANGE[0]}
        max={DEFAULT_YEAR_RANGE[1]}
        dropdownDirection="up"
        compact={compact}
      />
      {excludedGenres?.map((genre) => (
        <span
          key={genre}
          className={`inline-flex items-center rounded-full border border-muted-foreground/20 bg-muted/30 text-muted-foreground shadow-sm ${
            compact ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm"
          }`}
        >
          Not {genre}
        </span>
      ))}
    </div>
  );
}
