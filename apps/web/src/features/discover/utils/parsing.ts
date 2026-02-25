export function toMediaId(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.trim() !== "") return value.trim();
  return null;
}

export function toNumericMediaId(value: string): number | null {
  if (!value) return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.trunc(numeric);
}

export function toOptionalNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function toOptionalRating(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.round(value * 10) / 10;
  }
  if (typeof value === "string") {
    const cleaned = value.trim().replace(/[^0-9.]/g, "");
    if (cleaned) {
      const parsed = Number(cleaned);
      if (Number.isFinite(parsed)) return Math.round(parsed * 10) / 10;
    }
  }
  return null;
}

export function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((entry) => {
      if (typeof entry === "string") return entry;
      if (entry && typeof entry === "object") {
        if ("name" in entry && typeof (entry as { name: unknown }).name === "string") {
          return (entry as { name: string }).name;
        }
        if (
          "provider" in entry &&
          typeof (entry as { provider: unknown }).provider === "string"
        ) {
          return (entry as { provider: string }).provider;
        }
      }
      return null;
    })
    .filter((entry): entry is string => Boolean(entry));
}

export function normalizeTomatoScore(value: unknown): number | null {
  let parsed: number | null = null;

  if (typeof value === "string") {
    const cleaned = value.trim().replace(/[^0-9.]/g, "");
    if (cleaned) {
      const num = Number(cleaned);
      parsed = Number.isFinite(num) ? num : null;
    }
  }

  if (parsed === null) {
    parsed = toOptionalNumber(value);
  }

  if (parsed === null) return null;

  if (parsed <= 1) {
    const scaled = parsed * 100;
    if (!Number.isFinite(scaled)) return null;
    return Math.round(scaled * 10) / 10;
  }

  if (parsed > 1000) {
    return Math.round(parsed / 10);
  }

  return Math.round(parsed * 10) / 10;
}