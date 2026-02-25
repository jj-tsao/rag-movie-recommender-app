import type { FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";
import { EXAMPLE_CHIPS } from "@/features/landing/data/example_chips";

export interface SearchFormProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value?: string) => void;
  disabled?: boolean;
  helperId?: string;
  autoFocus?: boolean;
  showExamples?: boolean;
  compact?: boolean;
  footer?: ReactNode;
}

export function ExploreSearchForm({
  value,
  onChange,
  onSubmit,
  disabled,
  helperId,
  autoFocus,
  showExamples = false,
  compact = false,
  footer,
}: SearchFormProps) {
  const [showAllChips, setShowAllChips] = useState(false);
  const visibleChips = useMemo(
    () => (showAllChips ? EXAMPLE_CHIPS : EXAMPLE_CHIPS.slice(0, 4)),
    [showAllChips]
  );

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <div className="w-full space-y-3">
      <form
        onSubmit={handleSubmit}
        role="search"
        className="w-full"
        aria-describedby={helperId}
      >
        <label className="sr-only" htmlFor="explore-query-input">
          Describe what you want to watch
        </label>
        <div className={`w-full border border-gold/40 bg-background/90 transition focus-within:border-primary focus-within:ring-2 focus-within:ring-primary focus-within:shadow-[0_0_12px_rgba(196,164,105,0.15)] ${compact && footer ? "rounded-2xl shadow-[0_0_10px_rgba(196,164,105,0.1)]" : compact ? "rounded-full shadow-[0_0_10px_rgba(196,164,105,0.1)]" : "rounded-full shadow-inner"}`}>
          <div className={`flex w-full items-center gap-2 ${compact ? "px-3 py-2" : "px-4 py-3"}`}>
            <input
              id="explore-query-input"
              type="text"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={compact ? "Refine your picks, or explore something new..." : "Tell Reelix a mood, vibe, or cinematic style..."}
              className={`w-full bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none ${compact ? "text-sm" : "text-base"}`}
              aria-label="Explore by vibe"
              autoComplete="off"
              disabled={disabled}
              autoFocus={autoFocus}
            />
            <button
              type="submit"
              disabled={disabled}
              className={`inline-flex shrink-0 items-center justify-center rounded-full bg-muted/40 text-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60 ${compact ? "h-8 w-8" : "h-10 w-10"}`}
              aria-label="Submit search"
              title="Find recommendations"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M21 21l-4.3-4.3M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          {footer ? (
            <div className="px-3 pb-2">
              {footer}
            </div>
          ) : null}
        </div>
      </form>

      {showExamples ? (
        <>
          <div
            className="flex flex-wrap items-center justify-center gap-2"
            aria-live="polite"
            id="explore-chip-list"
          >
            {visibleChips.map((text) => (
              <button
                key={text}
                type="button"
                onClick={() => {
                  onChange(text);
                  onSubmit(text);
                }}
                disabled={disabled}
                className="inline-flex max-w-full items-center rounded-full border border-border/70 bg-background/80 px-3 py-1.5 text-xs text-foreground transition-transform duration-150 hover:-translate-y-0.5 hover:border-primary/70 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"
                aria-label={`Try: ${text}`}
                title={text}
              >
                <span className="truncate">{text}</span>
              </button>
            ))}

            {EXAMPLE_CHIPS.length > 4 ? (
              <button
                type="button"
                onClick={() => setShowAllChips((v) => !v)}
                className="inline-flex items-center rounded-full border border-border/70 bg-background/80 px-3 py-1.5 text-xs text-muted-foreground transition hover:border-primary/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                aria-expanded={showAllChips}
                aria-controls="explore-chip-list"
              >
                {showAllChips ? "Show less" : "More..."}
              </button>
            ) : null}
          </div>

          {helperId ? (
            <span id={helperId} className="block text-xs text-muted-foreground text-center" />
          ) : null}
        </>
      ) : null}
    </div>
  );
}