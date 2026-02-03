import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import YearRangeSlider from "@/components/YearRangeSlider";
import { YEAR_RANGE_MAX, YEAR_RANGE_MIN } from "@/utils/yearRange";

interface Props {
  value: [number, number] | null;
  onApply: (range: [number, number] | null) => void;
  min?: number;
  max?: number;
}

export default function YearRangeFilterChip({
  value,
  onApply,
  min = YEAR_RANGE_MIN,
  max = YEAR_RANGE_MAX,
}: Props) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<[number, number]>(value ?? [min, max]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const initialValueRef = useRef<[number, number] | null>(value);

  useEffect(() => {
    if (!open) return;
    const initial = value ?? null;
    initialValueRef.current = initial;
    setPending(initial ?? [min, max]);
  }, [open, value, min, max]);

  const canonicalRange = useCallback(
    (range: [number, number] | null): [number, number] | null => {
      if (!range) return null;
      const normalized: [number, number] = [
        Math.max(min, Math.min(range[0], range[1])),
        Math.min(max, Math.max(range[0], range[1])),
      ];
      if (normalized[0] <= min && normalized[1] >= max) {
        return null;
      }
      return normalized;
    },
    [min, max],
  );

  const isSameRange = useCallback(
    (a: [number, number] | null, b: [number, number] | null) => {
      if (a === null && b === null) return true;
      if (!a || !b) return false;
      return a[0] === b[0] && a[1] === b[1];
    },
    [],
  );

  const handleApply = useCallback(() => {
    const normalized = canonicalRange(pending);
    const initial = canonicalRange(initialValueRef.current);
    if (isSameRange(normalized, initial)) {
      setOpen(false);
      return;
    }
    onApply(normalized);
    setOpen(false);
  }, [pending, canonicalRange, onApply, isSameRange]);

  const handleClear = useCallback(() => {
    initialValueRef.current = null;
    onApply(null);
    setOpen(false);
  }, [onApply]);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent | TouchEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        handleApply();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [open, handleApply]);

  const label =
    value && value.length === 2
      ? `${value[0]}-${value[1]}`
      : "Years";

  return (
    <div className="relative" ref={containerRef}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-auto rounded-full border-gold/20 bg-background px-3 py-1.5 text-sm shadow-xs transition-all hover:border-gold/40 hover:shadow-md focus-visible:border-gold focus-visible:ring-2 focus-visible:ring-gold/50"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={label === "Years" ? "Filter by years: all years" : `Filter by years: ${label}`}
      >
        <div className="flex items-center gap-2">
          <span className="text-foreground">{label}</span>
          <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 text-muted-foreground">
            <path fill="currentColor" d="M5.5 7.5L10 12l4.5-4.5h-9z" />
          </svg>
        </div>
      </Button>

      {open ? (
        <div className="absolute left-0 z-30 mt-2 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-gold/30 bg-background shadow-xl">
          <div className="p-4">
            <YearRangeSlider min={min} max={max} values={pending} onChange={setPending} />
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-border/60 bg-muted/50 px-3 py-3">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="px-3 text-xs"
              onClick={handleClear}
              aria-label="Clear year range"
            >
              Clear All
            </Button>
            <Button type="button" size="sm" onClick={handleApply}>
              Apply
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
