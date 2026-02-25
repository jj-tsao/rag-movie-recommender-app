import { rebuildTasteProfile } from "@/api";

const RATING_COUNT_KEY = "rating_count";
const PENDING_REBUILD_KEY = "pending_rebuild";
const LAST_REBUILD_KEY = "last_rebuild_at";
const MIN_RATINGS_FOR_REBUILD = 2;
const REBUILD_DELAY_MS = 10_000;
const REBUILD_COOLDOWN_MS = 2 * 60 * 1000;

function parseStoredNumber(value: string | null): number | null {
  if (typeof value !== "string") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function isTruthyString(value: string | null): boolean {
  return value === "true" || value === "1";
}

export class DiscoverRebuildController {
  private ratingTimer: ReturnType<typeof setTimeout> | null = null;
  private cooldownTimer: ReturnType<typeof setTimeout> | null = null;
  private ratingCount = 0;
  private pendingRebuild = false;
  private lastRebuildAt: number | null = null;
  private rebuildInFlight = false;
  private hydrated = false;

  hydrate() {
    if (typeof window === "undefined" || this.hydrated) return;

    const storedCount = parseStoredNumber(window.localStorage.getItem(RATING_COUNT_KEY));
    this.ratingCount = storedCount && storedCount > 0 ? Math.floor(storedCount) : 0;
    window.localStorage.setItem(RATING_COUNT_KEY, String(this.ratingCount));

    this.pendingRebuild = isTruthyString(window.localStorage.getItem(PENDING_REBUILD_KEY));

    const storedLast = parseStoredNumber(window.localStorage.getItem(LAST_REBUILD_KEY));
    this.lastRebuildAt = storedLast && storedLast > 0 ? storedLast : null;

    this.hydrated = true;
    this.resumeCooldown();
  }

  registerRating() {
    if (typeof window === "undefined") return;
    this.ratingCount += 1;
    window.localStorage.setItem(RATING_COUNT_KEY, String(this.ratingCount));
    this.startRatingTimer();
  }

  dispose() {
    if (this.ratingTimer) {
      clearTimeout(this.ratingTimer);
      this.ratingTimer = null;
    }
    if (this.cooldownTimer) {
      clearTimeout(this.cooldownTimer);
      this.cooldownTimer = null;
    }
  }

  private startRatingTimer() {
    if (typeof window === "undefined") return;
    if (this.ratingTimer) {
      clearTimeout(this.ratingTimer);
    }
    this.ratingTimer = setTimeout(() => {
      this.ratingTimer = null;
      if (this.ratingCount >= MIN_RATINGS_FOR_REBUILD) {
        void this.tryRebuild();
      }
    }, REBUILD_DELAY_MS);
  }

  private clearRatingTimer() {
    if (this.ratingTimer) {
      clearTimeout(this.ratingTimer);
      this.ratingTimer = null;
    }
  }

  private resumeCooldown() {
    if (typeof window === "undefined") return;
    if (this.cooldownTimer) {
      clearTimeout(this.cooldownTimer);
      this.cooldownTimer = null;
    }
    if (this.lastRebuildAt === null) {
      if (this.pendingRebuild && this.ratingCount >= MIN_RATINGS_FOR_REBUILD && !this.rebuildInFlight) {
        void this.tryRebuild();
      }
      return;
    }
    const remaining = REBUILD_COOLDOWN_MS - (Date.now() - this.lastRebuildAt);
    if (remaining <= 0) {
      if (this.pendingRebuild && !this.rebuildInFlight) {
        void this.tryRebuild();
      }
      return;
    }
    this.cooldownTimer = setTimeout(() => {
      this.cooldownTimer = null;
      if (this.pendingRebuild && !this.rebuildInFlight) {
        void this.tryRebuild();
      }
    }, remaining);
  }

  private async tryRebuild() {
    if (this.rebuildInFlight) return;
    if (typeof window === "undefined") return;
    if (this.ratingCount < MIN_RATINGS_FOR_REBUILD && !this.pendingRebuild) return;

    const now = Date.now();
    if (this.lastRebuildAt !== null && now - this.lastRebuildAt < REBUILD_COOLDOWN_MS) {
      if (!this.pendingRebuild) {
        this.pendingRebuild = true;
        window.localStorage.setItem(PENDING_REBUILD_KEY, "true");
      }
      this.resumeCooldown();
      return;
    }

    this.rebuildInFlight = true;

    try {
      await rebuildTasteProfile();
      this.ratingCount = 0;
      window.localStorage.setItem(RATING_COUNT_KEY, "0");
      this.pendingRebuild = false;
      window.localStorage.removeItem(PENDING_REBUILD_KEY);
      this.clearRatingTimer();
    } catch (error) {
      console.warn("Failed to rebuild taste profile from discover feed", error);
      this.pendingRebuild = true;
      window.localStorage.setItem(PENDING_REBUILD_KEY, "true");
    } finally {
      this.lastRebuildAt = now;
      window.localStorage.setItem(LAST_REBUILD_KEY, String(now));
      this.rebuildInFlight = false;
      this.resumeCooldown();
    }
  }
}