import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getStreamingServiceOptions,
  type StreamingServiceOption,
} from "@/data/streamingServices";

type Props = {
  selected: string[];
  onApply: (names: string[]) => void;
};

export default function StreamingServiceFilterChip({ selected, onApply }: Props) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string[]>(selected);
  const containerRef = useRef<HTMLDivElement>(null);

  const options = useMemo(() => getStreamingServiceOptions(), []);
  const optionByName = useMemo(() => {
    const map = new Map<string, StreamingServiceOption>();
    options.forEach((option) => map.set(option.name, option));
    return map;
  }, [options]);
  const optionOrder = useMemo(() => {
    const order = new Map<string, number>();
    options.forEach((option, index) => order.set(option.name, index));
    return order;
  }, [options]);

  const sortByOptionOrder = useCallback(
    (names: Iterable<string>) =>
      Array.from(names).sort(
        (a, b) =>
          (optionOrder.get(a) ?? Number.MAX_SAFE_INTEGER) -
          (optionOrder.get(b) ?? Number.MAX_SAFE_INTEGER),
      ),
    [optionOrder],
  );

  useEffect(() => {
    if (!open) return;
    setPending(sortByOptionOrder(selected));
  }, [open, selected, sortByOptionOrder]);

  const topSelected = selected.slice(0, 3);
  const extraCount = selected.length > 3 ? selected.length - 3 : 0;

  const toggleOption = (name: string) => {
    setPending((prev) => {
      const set = new Set(prev);
      if (set.has(name)) {
        set.delete(name);
      } else {
        set.add(name);
      }
      return sortByOptionOrder(set);
    });
  };

  const handleApply = useCallback(() => {
    const sortedPending = sortByOptionOrder(pending);
    const sortedSelected = sortByOptionOrder(selected);
    setPending(sortedPending);
    const isSame =
      sortedPending.length === sortedSelected.length &&
      sortedPending.every((value, index) => value === sortedSelected[index]);
    if (!isSame) {
      onApply([...sortedPending]);
    }
    setOpen(false);
  }, [onApply, pending, sortByOptionOrder, selected]);

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

  return (
    <div className="relative" ref={containerRef}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-auto rounded-full border-gold/20 bg-background px-3 py-1.5 text-sm shadow-xs transition-all hover:border-gold/40 hover:shadow-md focus-visible:border-gold focus-visible:ring-2 focus-visible:ring-gold/50"
        onClick={() => setOpen((openState) => !openState)}
        aria-expanded={open}
        aria-label={
          selected.length === 0
            ? "Filter by streaming services: All services"
            : `Filter by streaming services: ${selected.join(", ")}`
        }
      >
        <div className="flex items-center gap-2">
          {selected.length === 0 ? (
            <span className="text-foreground">All services</span>
          ) : (
            <span className="flex items-center gap-1">
              {topSelected.map((name) => (
                <ProviderLogo key={name} option={optionByName.get(name)} className="size-5" />
              ))}
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
        <div className="absolute left-0 z-30 mt-2 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-gold/30 bg-background shadow-xl">
          <div className="max-h-[320px] overflow-y-auto py-2 scrollbar-styled">
            <FilterRow
              label="All services"
              selected={pending.length === 0}
              onClick={handleSelectAll}
            />

            <div className="my-2 border-t border-border/60" />

            {options.map((option) => (
              <FilterRow
                key={option.name}
                label={option.name}
                selected={pending.includes(option.name)}
                onClick={() => toggleOption(option.name)}
              >
                <ProviderLogo option={option} />
              </FilterRow>
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
        selected ? "bg-gold/10 text-foreground" : "hover:bg-muted/60 text-foreground",
      )}
    >
      {children}
      <span className="flex-1 text-sm">{label}</span>
      {selected ? <Check className="size-4 text-gold" /> : null}
    </button>
  );
}

function ProviderLogo({
  option,
  className,
}: {
  option?: StreamingServiceOption;
  className?: string;
}) {
  if (!option) {
    return (
      <span
        className={cn(
          "flex size-6 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-muted-foreground",
          className,
        )}
      >
        ?
      </span>
    );
  }

  if (option.logoPath) {
    return (
      <img
        src={option.logoPath}
        alt={option.name}
        loading="lazy"
        className={cn("size-6 rounded-sm object-contain", className)}
      />
    );
  }

  return (
    <span
      className={cn(
        "flex size-6 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-muted-foreground",
        className,
      )}
      aria-hidden
    >
      {option.name.charAt(0)}
    </span>
  );
}
