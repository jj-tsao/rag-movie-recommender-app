import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { MOVIE_GENRES } from "@/data/genres";

type Props = {
  selected: string[];
  onApply: (genres: string[]) => void;
};

export default function GenreFilterChip({ selected, onApply }: Props) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string[]>(selected);
  const containerRef = useRef<HTMLDivElement>(null);

  const order = useMemo<Map<string, number>>(
    () => new Map(MOVIE_GENRES.map((genre, idx) => [genre as string, idx])),
    [],
  );

  const sortByOrder = useCallback(
    (names: Iterable<string>) =>
      Array.from(names).sort(
        (a, b) => (order.get(a) ?? Number.MAX_SAFE_INTEGER) - (order.get(b) ?? Number.MAX_SAFE_INTEGER),
      ),
    [order],
  );

  useEffect(() => {
    if (!open) return;
    setPending(sortByOrder(selected));
  }, [open, selected, sortByOrder]);

  const toggleOption = (name: string) => {
    setPending((prev) => {
      const set = new Set(prev);
      if (set.has(name)) {
        set.delete(name);
      } else {
        set.add(name);
      }
      return sortByOrder(set);
    });
  };

  const handleApply = useCallback(() => {
    const sorted = sortByOrder(pending);
    setPending(sorted);
    const isSame =
      sorted.length === selected.length && sorted.every((value, index) => value === selected[index]);
    if (!isSame) {
      onApply(sorted);
    }
    setOpen(false);
  }, [onApply, pending, sortByOrder, selected]);

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

  const handleSelectAll = () => {
    setPending([]);
    if (selected.length > 0) {
      onApply([]);
    }
    setOpen(false);
  };

  const handleClear = () => {
    setPending([]);
  };

  const firstSelected = selected[0];
  const extraCount = selected.length > 1 ? selected.length - 1 : 0;

  return (
    <div className="relative" ref={containerRef}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-auto rounded-full border-border bg-background px-3 py-1.5 text-sm shadow-xs"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={
          selected.length === 0
            ? "Filter by genres: All genres"
            : `Filter by genres: ${selected.join(", ")}`
        }
      >
        <div className="flex items-center gap-2">
          {selected.length === 0 ? (
            <span className="text-foreground">All genres</span>
          ) : (
            <span className="flex items-center gap-1">
              <span>{firstSelected}</span>
              {extraCount > 0 ? (
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  +{extraCount}
                </span>
              ) : null}
            </span>
          )}
          <ChevronDown className="size-4 text-muted-foreground" />
        </div>
      </Button>

      {open ? (
        <div className="absolute left-0 z-30 mt-2 w-72 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-border bg-background shadow-xl">
          <div className="max-h-[320px] overflow-y-auto py-2 scrollbar-styled">
            <FilterRow label="All genres" selected={pending.length === 0} onClick={handleSelectAll} />

            <div className="my-2 border-t border-border/60" />

            {MOVIE_GENRES.map((genre) => (
              <div key={genre}>
                <FilterRow
                  label={genre}
                  selected={pending.includes(genre)}
                  onClick={() => toggleOption(genre)}
                />
                {genre === "Thriller" ? <div className="my-2 border-t border-border/60" /> : null}
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-border/60 bg-muted/50 px-3 py-3">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="px-3 text-xs"
              onClick={handleClear}
              disabled={pending.length === 0}
              aria-disabled={pending.length === 0}
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

function FilterRow({
  label,
  selected,
  onClick,
  children,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  children?: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 px-4 py-2 text-left transition-colors",
        selected ? "bg-primary/10 text-foreground" : "hover:bg-muted/60 text-foreground",
      )}
    >
      {children}
      <span className="flex-1 text-sm">{label}</span>
      {selected ? <Check className="size-4 text-primary" /> : null}
    </button>
  );
}
