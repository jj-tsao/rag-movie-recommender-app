import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import clsx from "clsx";
import {
  Check,
  ChevronDown,
  Heart,
  Plus,
  Star,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import type { ParsedMovie } from "../utils/parseMarkdown";
import { hasAnyRating, hasValidScore } from "@/utils/checkScores";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { WatchlistStatus } from "@/features/watchlist/api";

type MovieCardExtras = {
  releaseYear?: number;
  providers?: string[];
  whyMarkdown?: string;
  whyText?: string;
  whySource?: "cache" | "llm";
  isWhyLoading?: boolean;
  isRatingsLoading?: boolean;
  layout?: "grid" | "wide";
};

type MovieCardInput = Omit<Partial<ParsedMovie>, "mediaId" | "imdbRating" | "rottenTomatoesRating"> &
  MovieCardExtras & {
    mediaId?: string | number;
    title: string;
    imdbRating?: number | string | null;
    rottenTomatoesRating?: number | string | null;
    posterUrl?: string;
    backdropUrl?: string;
  };

type WatchlistButtonState = "loading" | "not_added" | "in_list";

interface WatchlistControlProps {
  state: WatchlistButtonState;
  status?: WatchlistStatus | null;
  rating?: number | null;
  busy?: boolean;
  onAdd: () => void;
  onSelectStatus: (status: WatchlistStatus) => void;
  onRemove: () => void;
  showRatingPrompt?: boolean;
  onRatingSelect?: (value: number) => void;
  onRatingSkip?: () => void;
  onRatingPromptOpen?: () => void;
  onRatingClear?: () => void;
  onOverlayChange?: (active: boolean) => void;
}

interface Props {
  movie: MovieCardInput;
  layout?: "grid" | "wide";
  feedback?: {
    value?: "love" | "like" | "dislike";
    disabled?: boolean;
    onChange: (value: "love" | "like" | "dislike") => void;
  };
  watchlist?: WatchlistControlProps;
  onTrailerClick?: () => void;
}

export default function MovieCard({
  movie,
  layout = "grid",
  feedback,
  watchlist,
  onTrailerClick,
}: Props) {
  const posterUrl = movie.posterUrl ?? undefined;
  const backdropUrl = movie.backdropUrl ?? undefined;
  const providers = movie.providers ?? [];
  const genres = movie.genres ?? [];
  const imdbRaw = movie.imdbRating ?? undefined;
  const rtRaw = movie.rottenTomatoesRating ?? undefined;
  const isWhyLoading = movie.isWhyLoading ?? false;
  const isRatingsLoading = movie.isRatingsLoading ?? false;
  const hasRating =
    !isRatingsLoading &&
    hasAnyRating({ imdbRating: imdbRaw, rottenTomatoesRating: rtRaw });
  const whySource = movie.whyMarkdown ?? movie.whyText ?? movie.why ?? "";
  const hasWhyContent =
    !isWhyLoading &&
    typeof whySource === "string" &&
    whySource.trim().length > 0;
  const isWide = layout === "wide";

  const containerClass = clsx(
    "group relative flex h-full flex-col overflow-visible rounded-xl border border-white/10 bg-background/95 text-white transition-all duration-200 hover:shadow-[0_8px_30px_rgba(0,0,0,0.4),0_0_40px_rgba(197,165,114,0.15)] hover:scale-[1.01] card-grain",
    isWide ? "md:hover:-translate-y-0.5" : "hover:-translate-y-1"
  );

  const contentClass = clsx(
    "relative z-10 flex flex-col gap-3 px-4 py-3 md:flex-row",
    isWide && "gap-5 px-6 py-3"
  );

  const posterWrapperClass = clsx(
    "mx-auto flex w-full max-w-[11rem] flex-shrink-0 overflow-hidden rounded-lg bg-black/30 md:mx-0 md:w-44",
    isWide && "max-w-[12rem] md:w-48"
  );

  const titleClass = "font-display text-4xl font-semibold leading-tight text-white tracking-tight";
  const metaClass = "text-sm text-zinc-300";
  const bulletClass = "text-zinc-500";
  const ratingContainerClass =
    "flex flex-wrap items-center gap-2 text-sm text-zinc-300";
  const whyHeaderClass =
    "text-sm font-semibold tracking-normal text-gold-dark";
  const emptyWhyClass = "text-sm italic text-zinc-400";
  const providerBadgeClass =
    "rounded-full border border-gold/20 bg-white/5 px-2.5 py-1 text-xs font-medium text-zinc-100 backdrop-blur";
  const feedbackValue = feedback?.value;
  const feedbackDisabled = feedback?.disabled ?? false;
  const feedbackLabelClass =
    "text-xs font-semibold uppercase tracking-wide text-zinc-400";
  const [overlayActive, setOverlayActive] = useState(false);

  return (
    <Card
      className={containerClass}
      style={overlayActive ? { position: "relative", zIndex: 30 } : undefined}
    >
      {backdropUrl ? (
        <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden rounded-xl">
          {/* Backdrop image with consistent opacity across /query and /discover/for-you */}
          <div
            className="h-full w-full bg-cover bg-center blur-[1px] opacity-15 transition-opacity duration-300 group-hover:opacity-20"
            style={{ backgroundImage: `url(${backdropUrl})` }}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-slate-800/80 via-black/40 to-transparent" />
        </div>
      ) : null}

      <CardContent className={contentClass}>
        <div className={posterWrapperClass}>
          {posterUrl ? (
            <img
              src={posterUrl}
              alt={movie.title}
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.01]"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center px-3 text-center text-xs text-muted-foreground/70">
              Poster coming soon
            </div>
          )}
        </div>

        <div className="flex flex-1 flex-col gap-3 text-sm">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className={titleClass}>{movie.title}</h2>
              {movie.releaseYear ? (
                <span className="inline-flex items-center rounded-full border border-gold/30 px-3 py-0.5 text-xs leading-none text-white/70">
                  {movie.releaseYear}
                </span>
              ) : null}
            </div>

            {providers.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {providers.map((provider) => (
                  <span key={provider} className={providerBadgeClass}>
                    {provider}
                  </span>
                ))}
              </div>
            ) : null}

            {genres.length > 0 ? (
              <div className={metaClass}>
                <span className="font-medium text-white">Genres:</span>{" "}
                {genres.join(", ")}
              </div>
            ) : null}

            <div className="min-h-[1.25rem]">
              {isRatingsLoading ? (
                <div className="flex items-center gap-2 animate-pulse">
                  <span className="h-3 w-16 rounded bg-muted/80" />
                  <span className="h-3 w-12 rounded bg-muted/70" />
                </div>
              ) : hasRating ? (
                <p className={ratingContainerClass}>
                  {hasValidScore(imdbRaw) ? (
                    <span className="flex items-center gap-1">
                      <span className="text-gold">⭐</span> {formatRating(imdbRaw)}/10
                    </span>
                  ) : null}
                  {hasValidScore(imdbRaw) && hasValidScore(rtRaw) ? (
                    <span className={bulletClass}>•</span>
                  ) : null}
                  {hasValidScore(rtRaw) ? (
                    <span>🍅 {formatRating(rtRaw)}%</span>
                  ) : null}
                </p>
              ) : (
                <span className="text-sm text-zinc-500/60">—</span>
              )}
            </div>
          </div>

          <div className="space-y-2 text-sm text-zinc-300">
            <div className={whyHeaderClass}>Why this fits your taste</div>
            {isWhyLoading ? (
              <div className="space-y-2 animate-pulse">
                <div className="h-3 w-full rounded bg-muted/80" />
                <div className="h-3 w-5/6 rounded bg-muted/70" />
                <div className="h-3 w-4/6 rounded bg-muted/60" />
              </div>
            ) : hasWhyContent ? (
              <div className="prose prose-invert prose-sm max-w-none text-base leading-relaxed text-zinc-200">
                <ReactMarkdown>{whySource}</ReactMarkdown>
              </div>
            ) : (
              <p className={emptyWhyClass}>
                We're still working on a personalized reason for this pick.
              </p>
            )}
          </div>

          {movie.trailerKey || watchlist ? (
            <div className="flex flex-wrap items-center gap-4">
              {movie.trailerKey ? (
                <a
                  href={`https://www.youtube.com/watch?v=${movie.trailerKey}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => onTrailerClick?.()}
                  className="inline-flex items-center gap-2 text-base font-medium text-zinc-300 hover:text-gold-light transition-all hover:gap-2.5"
                >
                  <img
                    src="/icons/play_icon.png"
                    alt="Play"
                    className="h-5 w-5"
                  />
                  Watch trailer
                </a>
              ) : null}
              {watchlist ? (
                <WatchlistButton
                  {...watchlist}
                  onOverlayChange={setOverlayActive}
                />
              ) : null}
            </div>
          ) : null}

          {feedback ? (
            <div className="mt-4 flex flex-col gap-2">
              <span className={feedbackLabelClass}>What do you think?</span>
              <div className="flex items-center gap-2">
                <FeedbackButton
                  icon={Heart}
                  label="Love"
                  active={feedbackValue === "love"}
                  disabled={feedbackDisabled}
                  onClick={() => feedback.onChange("love")}
                  activeClass="bg-pink-500/20 text-pink-200 border-pink-400/50"
                />
                <FeedbackButton
                  icon={ThumbsUp}
                  label="Like"
                  active={feedbackValue === "like"}
                  disabled={feedbackDisabled}
                  onClick={() => feedback.onChange("like")}
                  activeClass="bg-emerald-500/15 text-emerald-200 border-emerald-400/50"
                />
                <FeedbackButton
                  icon={ThumbsDown}
                  label="Not for me"
                  active={feedbackValue === "dislike"}
                  disabled={feedbackDisabled}
                  onClick={() => feedback.onChange("dislike")}
                  activeClass="bg-amber-500/15 text-amber-200 border-amber-400/50"
                />
              </div>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function WatchlistButton({
  state,
  status,
  rating,
  busy = false,
  onAdd,
  onSelectStatus,
  onRemove,
  showRatingPrompt = false,
  onRatingSelect,
  onRatingSkip,
  onRatingPromptOpen,
  onRatingClear,
  onOverlayChange,
}: WatchlistControlProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (event: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("mousedown", handleClick);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  useEffect(() => {
    if (state !== "in_list") {
      setOpen(false);
    }
  }, [state]);

  const shouldShowPrompt = Boolean(
    state === "in_list" && showRatingPrompt && onRatingSelect && onRatingSkip && !busy,
  );

  const isOverlayActive = open || shouldShowPrompt;

  useEffect(() => {
    onOverlayChange?.(isOverlayActive);
  }, [isOverlayActive, onOverlayChange]);

  useEffect(() => {
    if (!shouldShowPrompt) return;
    const handleClick = (event: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        onRatingSkip?.();
      }
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onRatingSkip?.();
      }
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [shouldShowPrompt, onRatingSkip]);

  const baseButtonClasses = "min-w-[12rem] justify-center";

  if (state === "loading") {
    return (
      <Button type="button" disabled className={clsx("gap-2", baseButtonClasses)}>
        Checking…
      </Button>
    );
  }

  if (state === "not_added") {
    return (
      <Button
        type="button"
        onClick={onAdd}
        disabled={busy}
        aria-live="polite"
        className={clsx("gap-2 text-background", "bg-gold hover:bg-gold-light transition-colors", baseButtonClasses)}
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
        Add to Watchlist
      </Button>
    );
  }

  const effectiveStatus: WatchlistStatus = status === "watched" ? "watched" : "want";
  const isWatched = effectiveStatus === "watched";
  const label = isWatched ? "Watched" : "In Watchlist";

  const buttonClass = isWatched
    ? "bg-gold-dark hover:bg-[#8A6F42] text-white transition-colors"
    : "bg-burgundy/80 hover:bg-burgundy text-gold-light border border-burgundy transition-colors";

  return (
    <div
      className={clsx(
        "relative flex flex-wrap items-center gap-2",
        isOverlayActive ? "z-40" : "z-0",
      )}
      style={{ isolation: "isolate" }}
    >
      <div className="relative inline-flex" ref={containerRef}>
        <Button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          disabled={busy}
          aria-expanded={open}
          aria-haspopup="menu"
          className={clsx("gap-2 pr-3", buttonClass, baseButtonClasses)}
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          {label}
          <ChevronDown
            className={clsx("h-4 w-4 transition-transform", open && "-rotate-180")}
            aria-hidden="true"
          />
          <span className="sr-only">Manage watchlist</span>
        </Button>
        {shouldShowPrompt ? (
          <>
            <RatingPrompt
              variant="popover"
              onSelect={(value) => onRatingSelect?.(value)}
              onSkip={() => onRatingSkip?.()}
              onClear={typeof rating === "number" ? onRatingClear : undefined}
              hasRating={typeof rating === "number"}
              initialRating={typeof rating === "number" ? rating : null}
            />
            <RatingPrompt
              variant="sheet"
              onSelect={(value) => onRatingSelect?.(value)}
              onSkip={() => onRatingSkip?.()}
              onClear={typeof rating === "number" ? onRatingClear : undefined}
              hasRating={typeof rating === "number"}
              initialRating={typeof rating === "number" ? rating : null}
            />
          </>
        ) : null}
        {open ? (
          <div
            role="menu"
            className="absolute right-0 top-full z-40 mt-2 w-48 rounded-md border border-white/10 bg-background/95 p-1 text-sm shadow-lg backdrop-blur"
          >
            <WatchlistMenuButton
              role="menuitemradio"
              active={effectiveStatus === "want"}
              ariaChecked={effectiveStatus === "want"}
              disabled={busy}
              onClick={() => {
                if (effectiveStatus !== "want") {
                  onSelectStatus("want");
                }
                setOpen(false);
              }}
            >
              <Check
                className={clsx(
                  "h-4 w-4 transition-opacity",
                  effectiveStatus === "want" ? "opacity-100" : "opacity-0",
                )}
                aria-hidden="true"
              />
              <span>Want to watch</span>
            </WatchlistMenuButton>
            <WatchlistMenuButton
              role="menuitemradio"
              active={effectiveStatus === "watched"}
              ariaChecked={effectiveStatus === "watched"}
              disabled={busy}
              onClick={() => {
                if (effectiveStatus !== "watched") {
                  onSelectStatus("watched");
                }
                setOpen(false);
              }}
            >
              <Check
                className={clsx(
                  "h-4 w-4 transition-opacity",
                  effectiveStatus === "watched" ? "opacity-100" : "opacity-0",
                )}
                aria-hidden="true"
              />
              <span>Watched</span>
            </WatchlistMenuButton>
            <div className="my-1 h-px bg-white/10" role="none" />
            <WatchlistMenuButton
              variant="danger"
              disabled={busy}
              onClick={() => {
                onRemove();
                setOpen(false);
              }}
            >
              <span>Remove</span>
            </WatchlistMenuButton>
          </div>
        ) : null}
      </div>
      {state === "in_list" && onRatingPromptOpen && (effectiveStatus === "watched" || typeof rating === "number") ? (
        <RatingPill
          rating={typeof rating === "number" ? rating : null}
          disabled={busy}
          onClick={() => {
            if (!busy) {
              onRatingPromptOpen();
            }
          }}
        />
      ) : null}
    </div>
  );
}

function WatchlistMenuButton({
  children,
  active = false,
  disabled = false,
  onClick,
  variant = "default",
  role = "menuitem",
  ariaChecked,
}: {
  children: ReactNode;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  variant?: "default" | "danger";
  role?: "menuitem" | "menuitemradio";
  ariaChecked?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      role={role}
      aria-checked={
        role === "menuitemradio" ? (ariaChecked ?? active) : undefined
      }
      className={clsx(
        "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-white/90 transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20",
        active && "bg-white/15 text-white font-medium",
        variant === "danger" &&
          "text-rose-300 hover:bg-rose-500/20 focus-visible:ring-rose-400/40",
        disabled &&
          "cursor-not-allowed opacity-60 hover:bg-transparent focus-visible:ring-0"
      )}
    >
      {children}
    </button>
  );
}

function RatingPrompt({
  variant,
  onSelect,
  onSkip,
  onClear,
  hasRating = false,
  initialRating = null,
}: {
  variant: "popover" | "sheet";
  onSelect: (value: number) => void;
  onSkip: () => void;
  onClear?: () => void;
  hasRating?: boolean;
  initialRating?: number | null;
}) {
  const baseClass =
    variant === "popover"
      ? "absolute left-1/2 top-[calc(100%+0.75rem)] z-30 hidden min-w-[22.5rem] -translate-x-1/2 transform rounded-lg border border-white/10 bg-slate-900/95 p-4 text-white shadow-xl backdrop-blur md:block"
      : "fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-md rounded-t-2xl border border-white/10 bg-slate-900/95 px-6 py-5 text-white shadow-[0_-12px_30px_rgba(0,0,0,0.35)] md:hidden";

  const ratingOptions = Array.from({ length: 10 }, (_, index) => index + 1);
  const [hoverValue, setHoverValue] = useState<number | null>(null);
  const [focusValue, setFocusValue] = useState<number | null>(null);
  const baseValue = typeof initialRating === "number" ? initialRating : null;
  const highlighted = hoverValue ?? focusValue ?? baseValue;

  useEffect(() => {
    setHoverValue(null);
    setFocusValue(null);
  }, [initialRating, variant]);

  return (
    <div
      role="dialog"
      aria-modal={variant === "sheet" ? true : undefined}
      aria-label="Rate this title"
      className={baseClass}
    >
      <button
        type="button"
        onClick={onSkip}
        className="absolute right-3 top-3 rounded-full p-2 text-white/70 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        aria-label="Cancel"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
      <div className="flex flex-col items-center gap-3">
        <p className="text-sm font-medium text-white">Rate this title?</p>
        <div
          className="flex items-center justify-center gap-1"
          role="group"
          aria-label="Select a star rating"
          onMouseLeave={() => setHoverValue(null)}
        >
          {ratingOptions.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => onSelect(value)}
              title={`${value} out of 10`}
              onMouseEnter={() => setHoverValue(value)}
              onFocus={() => setFocusValue(value)}
              onBlur={() => setFocusValue((current) => (current === value ? null : current))}
              className="flex h-8 w-8 items-center justify-center rounded-md transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/50"
            >
              <Star
                className={clsx(
                  "h-5 w-5 transition-colors",
                  highlighted !== null && value <= highlighted
                    ? "text-gold"
                    : "text-white/35",
                )}
                strokeWidth={1.4}
                fill={highlighted !== null && value <= highlighted ? "currentColor" : "none"}
              />
              <span className="sr-only">{`Rate ${value} out of 10`}</span>
            </button>
          ))}
        </div>
        {onClear && hasRating ? (
          <button
            type="button"
            onClick={() => {
              onClear();
            }}
            className="text-xs font-medium text-white/70 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
          >
            Clear rating
          </button>
        ) : null}
      </div>
    </div>
  );
}

function RatingPill({
  rating,
  disabled,
  onClick,
}: {
  rating: number | null;
  disabled?: boolean;
  onClick: () => void;
}) {
  const hasRating = typeof rating === "number";
  const label = hasRating ? `Edit rating: ${rating}` : "Add rating";
  const display = hasRating ? rating : "Rate";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/5 px-3 py-1 text-sm text-white/85 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40",
        disabled && "cursor-not-allowed opacity-60 hover:bg-white/5",
      )}
      aria-label={label}
    >
      <Star
        className={clsx("h-4 w-4", hasRating ? "text-gold" : "text-white/40")}
        strokeWidth={hasRating ? 1.4 : 1.2}
        fill={hasRating ? "currentColor" : "none"}
        aria-hidden="true"
      />
      <span className="font-semibold text-white">{display}</span>
    </button>
  );
}

type FeedbackIcon = typeof Heart;

function FeedbackButton({
  icon: Icon,
  label,
  active,
  disabled,
  onClick,
  activeClass,
}: {
  icon: FeedbackIcon;
  label: string;
  active: boolean;
  disabled: boolean;
  onClick: () => void;
  activeClass: string;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={disabled}
      aria-disabled={disabled}
      aria-pressed={active}
      onClick={onClick}
      className={clsx(
        "h-9 w-9 rounded-full border px-0 transition-all",
        active
          ? activeClass
          : "border-gold/20 bg-background/60 text-zinc-300 hover:border-gold/40 hover:bg-gold/10 hover:text-gold-light",
        disabled && "opacity-60 cursor-not-allowed"
      )}
      title={label}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </Button>
  );
}

function formatRating(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Number.isInteger(value) ? value.toString() : value.toFixed(1);
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return "";
    const numeric = Number(trimmed);
    if (!Number.isNaN(numeric)) {
      return Number.isInteger(numeric)
        ? numeric.toString()
        : numeric.toFixed(1);
    }
    return trimmed;
  }
  return "";
}
