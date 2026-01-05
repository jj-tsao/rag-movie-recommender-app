import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { logUserRecReaction } from "../api";
import { rebuildTasteProfile } from "@/api";
import type { PropsWithChildren } from "react";
import { SEED_MOVIES } from "../data/seed_movies";
import { useToast } from "@/components/ui/useToast";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Heart, ThumbsUp, ThumbsDown, Shuffle, CircleSlash, Plus } from "lucide-react";
import clsx from "clsx";

type SeedMovie = {
  title: string;
  year: number;
  poster_url: string;
  vibes: string[];
  media_id?: number | string;
};

type Rating = "love" | "like" | "dislike" | "dismiss";

type Props = {
  genres: string[];
  onBack?: () => void;
  onFinish?: (ratings: Record<string, Rating>) => void;
};

function shuffleInPlace<T>(arr: T[]): T[] {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export default function RateSeedMoviesStep({ genres, onBack, onFinish }: Props) {
  const [ratings, setRatings] = useState<Record<string, Rating>>({});
  const { toast } = useToast();
  const [submitting, setSubmitting] = useState(false);

  // Cards displayed and remaining pools per genre to support "skip" swaps
  const [cards, setCards] = useState<{ genre: string; movie: SeedMovie }[]>([]);
  const [remainingByGenre, setRemainingByGenre] = useState<Record<string, SeedMovie[]>>({});
  const [animatingIndex, setAnimatingIndex] = useState<number | null>(null);
  const animTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isDesktop, setIsDesktop] = useState(false);

  // Initialize cards when genres change
  useEffect(() => {
    const nextCards: { genre: string; movie: SeedMovie }[] = [];
    const nextRemaining: Record<string, SeedMovie[]> = {};

    // Build shuffled pools per genre
    const pools = genres.map((g) => {
      const all = [
        ...(((SEED_MOVIES as unknown as Record<string, readonly SeedMovie[]>)[g] ?? []) as readonly SeedMovie[]),
      ];
      return { genre: g, pool: shuffleInPlace(all.slice()) };
    });

    // Desired initial cards
    const targetTotal = genres.length === 1 ? 6 : 9; // rule: 6 when one genre; otherwise max at 9 overall

    if (pools.length === 1) {
      const p = pools[0]!;
      const take = Math.min(targetTotal, p.pool.length);
      for (let i = 0; i < take; i++) {
        nextCards.push({ genre: p.genre, movie: p.pool[i]! });
      }
      nextRemaining[p.genre] = p.pool.slice(take);
    } else {
      const totalAvailable = pools.reduce((acc, p) => acc + p.pool.length, 0);
      const desired = Math.min(targetTotal, totalAvailable);
      let added = 0;
      while (added < desired) {
        let progressed = false;
        for (let i = 0; i < pools.length && added < desired; i++) {
          const p = pools[i]!;
          if (p.pool.length > 0) {
            const mv = p.pool.shift()!;
            nextCards.push({ genre: p.genre, movie: mv });
            added++;
            progressed = true;
          }
        }
        if (!progressed) break;
      }
      for (const p of pools) {
        nextRemaining[p.genre] = p.pool;
      }
    }

    shuffleInPlace(nextCards);
    setCards(nextCards);
    setRemainingByGenre(nextRemaining);
    setRatings({});
    setSubmitting(false);
  }, [genres]);

  // Track responsive breakpoint for how many to load
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  function keyFor(genre: string, m: SeedMovie) {
    return `${genre}:${m.title}:${m.year}`;
  }

  function setRating(genre: string, m: SeedMovie, r: Rating) {
    const k = keyFor(genre, m);
    setRatings((prev) => ({ ...prev, [k]: r }));
    // Debounced upsert per title so rapid changes settle to the latest choice
    scheduleUpsert(genre, m, r);
  }

  function handleSkip(index: number, genre: string, m: SeedMovie) {
    // Record the skip rating for the current movie
    setRating(genre, m, "dismiss");
    setAnimatingIndex(index);
    // Build exclusion set of keys currently displayed (excluding the card being replaced)
    const excludeKeys = new Set(
      cards.filter((_, i) => i !== index).map(({ genre: g, movie }) => keyFor(g, movie))
    );

    // Choose a replacement from the same genre if possible,
    // otherwise randomly from any genre that still has remaining movies, avoiding duplicates.
    setRemainingByGenre((old) => {
      const mutable: Record<string, SeedMovie[]> = Object.fromEntries(
        Object.entries(old).map(([g, list]) => [g, list.slice()])
      );

      const candidateGenres = (() => {
        const others = Object.keys(mutable).filter((g) => g !== genre && (mutable[g]?.length ?? 0) > 0);
        shuffleInPlace(others);
        return [genre, ...others];
      })();

      let chosenGenre: string | null = null;
      let replacement: SeedMovie | null = null;

      for (const g of candidateGenres) {
        const pool = mutable[g] ?? [];
        const filtered = pool.filter((mv) => !excludeKeys.has(keyFor(g, mv)));
        if (filtered.length === 0) continue;
        const pick = filtered[Math.floor(Math.random() * filtered.length)];
        // Remove from the actual pool
        const idx = pool.findIndex((mv) => mv.title === pick.title && mv.year === pick.year);
        if (idx >= 0) pool.splice(idx, 1);
        chosenGenre = g;
        replacement = pick;
        break;
      }

      if (!replacement || !chosenGenre) {
        // Nothing left anywhere to swap in; leave the card as-is.
        return old;
      }

      setCards((prev) => {
        const next = prev.slice();
        next[index] = { genre: chosenGenre!, movie: replacement! };
        return next;
      });

      // Reset the animating index after the animation window
      if (animTimer.current) clearTimeout(animTimer.current);
      animTimer.current = setTimeout(() => setAnimatingIndex(null), 200);

      return { ...mutable };
    });
  }

  // Append more cards from the shared remaining pool, avoiding duplicates
  function loadMore(requestedCount: number) {
    const excludeKeys = new Set(cards.map(({ genre, movie }) => keyFor(genre, movie)));
    const mutable: Record<string, SeedMovie[]> = Object.fromEntries(
      Object.entries(remainingByGenre).map(([g, list]) => [g, (list ?? []).slice()])
    );
    const order = Object.keys(mutable);
    const picked: { genre: string; movie: SeedMovie }[] = [];

    let progressed = true;
    while (picked.length < requestedCount && progressed) {
      progressed = false;
      for (const g of order) {
        const pool = mutable[g] ?? [];
        const idx = pool.findIndex((mv) => !excludeKeys.has(keyFor(g, mv)));
        if (idx >= 0) {
          const mv = pool.splice(idx, 1)[0]!;
          picked.push({ genre: g, movie: mv });
          excludeKeys.add(keyFor(g, mv));
          progressed = true;
          if (picked.length >= requestedCount) break;
        }
      }
    }

    if (picked.length === 0) {
      toast({ title: "All caught up", description: "No more titles to load right now.", variant: "success" });
      return;
    }

    setCards((prev) => [...prev, ...picked]);
    setRemainingByGenre(mutable);
  }

  // Debounce machinery for per-click writes
  const upsertTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  function scheduleUpsert(genre: string, m: SeedMovie, r: Rating) {
    const key = keyFor(genre, m);
    const t = upsertTimers.current.get(key);
    if (t) clearTimeout(t);
    if (!m.media_id) return;
    if (r === "dismiss") {
      upsertTimers.current.delete(key);
      return; // We no longer log dismisses during taste onboarding
    }
    const timer = setTimeout(() => {
      logUserRecReaction({ mediaId: m.media_id!, title: m.title, reaction: r }).catch((err) => {
        console.error("Failed to log reaction", err);
      });
      upsertTimers.current.delete(key);
    }, 200);
    upsertTimers.current.set(key, timer);
  }

  useEffect(() => {
    const timers = upsertTimers.current;
    return () => {
      timers.forEach((t) => clearTimeout(t));
      timers.clear();
    };
  }, []);

  const ratedCount = useMemo(
    () =>
      Object.values(ratings).filter(
        (value) => value === "love" || value === "like" || value === "dislike"
      ).length,
    [ratings]
  );
  const needsMoreRatings = ratedCount < 3;
  const helperMessage = useMemo(() => {
    if (ratedCount < 3) return "Rate 3+ to personalize better.";
    if (ratedCount < 6) return "Great! Aim for 6+ for a sharper feed.";
    return "All set. Finish now or keep rating.";
  }, [ratedCount]);
  function AnimatedSwap({ token, active, children }: PropsWithChildren<{ token: string; active: boolean }>) {
    const [visible, setVisible] = useState(true);
    useLayoutEffect(() => {
      if (!active) return;
      setVisible(false);
      const t = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(t);
    }, [token, active]);

    return (
      <div
        style={{
          transition: "opacity 180ms ease, transform 180ms ease",
          opacity: active ? (visible ? 1 : 0) : 1,
          transform: active ? (visible ? "none" : "scale(0.98)") : "none",
        }}
      >
        {children}
      </div>
    );
  }

  // (Inline per-card availability messaging; no global banner)

  async function handleContinue() {
    if (submitting || needsMoreRatings) return;
    try {
      setSubmitting(true);
      await rebuildTasteProfile();
    } catch (err) {
      console.warn("Failed to rebuild taste profile", err);
    } finally {
      setSubmitting(false);
      onFinish?.(ratings);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 pb-10 pt-4 sm:pt-4">
      <h2 className="mb-1 text-2xl font-semibold text-foreground">Rate a few picks</h2>
      <div className="sticky top-[3.5rem] z-20 mb-6 border-b border-border/60 bg-background/95 py-3 shadow-sm backdrop-blur sm:top-[4.25rem]">
        <p className="text-sm text-muted-foreground">
          Rate a few you’ve seen. Tap Love, Like, Not for me, or Haven't seen.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        {cards.map(({ genre, movie: m }, i) => {
          const k = keyFor(genre, m);
          const r = ratings[k];
          // Determine if a replacement exists anywhere, excluding currently visible cards (except this one)
          const excludeKeys = new Set(
            cards.filter((_, j) => j !== i).map(({ genre: g, movie }) => keyFor(g, movie))
          );
          const canShuffle = Object.keys(remainingByGenre).some((g) =>
            (remainingByGenre[g] ?? []).some((mv) => !excludeKeys.has(keyFor(g, mv)))
          );
          return (
            <Card key={i} className="overflow-hidden">
              <CardContent className="p-0">
                <AnimatedSwap token={k} active={i === animatingIndex}>
                <div className="aspect-[2/3] w-full bg-muted overflow-hidden">
                  {m.poster_url && (
                    <img
                      src={m.poster_url}
                      alt={m.title}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  )}
                </div>
                <div className="p-3 border-t">
                  <div className="text-sm font-medium leading-tight">{m.title}</div>
                  <div className="text-xs text-muted-foreground">{m.year}</div>
                  {m.vibes && m.vibes.length > 0 && (
                    <div className="mt-1.5 text-xs text-muted-foreground leading-snug whitespace-normal break-words">
                      {m.vibes.map((v, idx) => (
                        <span key={`${m.title}-${v}`}>
                          {v}
                          {idx < m.vibes.length - 1 ? <span className="mx-1">•</span> : null}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="mt-3 grid grid-cols-4 gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className={clsx(
                        "justify-center w-full",
                        r === "love" && "bg-pink-100 text-pink-700 border border-pink-300"
                      )}
                      onClick={() => setRating(genre, m, "love")}
                      aria-pressed={r === "love"}
                      title="Love"
                    >
                      <Heart className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className={clsx(
                        "justify-center w-full",
                        r === "like" && "bg-green-100 text-green-700 border border-green-300"
                      )}
                      onClick={() => setRating(genre, m, "like")}
                      aria-pressed={r === "like"}
                      title="Like"
                    >
                      <ThumbsUp className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className={clsx(
                        "justify-center w-full",
                        r === "dislike" && "bg-amber-100 text-amber-800 border border-amber-300"
                      )}
                      onClick={() => setRating(genre, m, "dislike")}
                      aria-pressed={r === "dislike"}
                      title="Not for me"
                    >
                      <ThumbsDown className="h-4 w-4" />
                    </Button>
                    <div className={clsx("relative group w-full")}
                      title={
                        canShuffle ? undefined : "You’ve rated all the titles for now — thanks! 🎉"
                      }
                      onClick={() => {
                        if (!canShuffle) {
                          toast({
                            title: "All Rated",
                            description: "You’ve rated all the titles for now — thanks! 🎉",
                            variant: "success",
                          });
                        }
                      }}
                    >
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className={clsx(
                          "justify-center w-full",
                          r === "dismiss" && "bg-slate-100 text-slate-700 border border-slate-300"
                        )}
                        onClick={() => canShuffle && handleSkip(i, genre, m)}
                        aria-pressed={r === "dismiss"}
                        aria-disabled={!canShuffle}
                        disabled={!canShuffle}
                        title={canShuffle ? "Haven't seen" : undefined}
                      >
                        {canShuffle ? (
                          <Shuffle className="h-4 w-4" />
                        ) : (
                          <CircleSlash className="h-4 w-4 text-muted-foreground" />
                        )}
                      </Button>
                      {/* No custom hover tooltip to avoid clipping inside card; rely on title + toast */}
                    </div>
                  </div>
                </div>
                </AnimatedSwap>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Rate more titles (loads from the same remaining pool) */}
      {(() => {
        const displayed = new Set(cards.map(({ genre, movie }) => keyFor(genre, movie)));
        let remainingCount = 0;
        for (const [g, list] of Object.entries(remainingByGenre)) {
          for (const mv of list ?? []) {
            if (!displayed.has(keyFor(g, mv))) remainingCount++;
          }
        }
        const canLoadMore = remainingCount > 0;
        const desired = isDesktop ? 6 : 3;
        return canLoadMore ? (
          <div className="mt-4 flex justify-center">
            <Button
              variant="outline"
              size="sm"
              className="rounded-full gap-2 px-3"
              aria-label="Rate more titles"
              title="Rate more titles"
              onClick={() => loadMore(desired)}
            >
              <Plus className="h-4 w-4" />
              Rate more titles
            </Button>
          </div>
        ) : (
          <div className="mt-4 flex justify-center text-xs text-muted-foreground">
            All rated! Congrats 🎉
          </div>
        );
      })()}

      <div className="sticky bottom-0 z-20 mt-10 border-t border-border/60 bg-background/95 py-4 shadow-md backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <Button variant="outline" onClick={onBack}>
              Back
            </Button>
            <span>
              Rated: <span className="font-medium">{ratedCount}</span> title
              {ratedCount === 1 ? "" : "s"}
            </span>
          </div>
          <Button
            onClick={handleContinue}
            disabled={submitting || needsMoreRatings}
            className={clsx(
              "transition-opacity",
              needsMoreRatings && !submitting ? "opacity-60" : "opacity-100"
            )}
          >
            {submitting ? "Saving..." : "See my recommendations"}
          </Button>
        </div>
        <div className="mt-1 w-full text-right text-sm text-muted-foreground">
          {helperMessage}
        </div>
      </div>
    </div>
  );
}
