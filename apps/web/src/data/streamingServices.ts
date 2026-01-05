import { WATCH_PROVIDERS, type WatchProvider } from "./watchProviders";

export type StreamingServiceOption = {
  id: number | null;
  name: string;
  providerName: string;
  logoPath: string | null;
};

const STREAMING_SERVICE_NAMES = [
  "Netflix",
  "Hulu",
  "HBO Max",
  "Disney+",
  "Apple TV+",
  "Amazon Prime Video",
  "Paramount Plus",
  "Peacock Premium",
  "MGM Plus",
  "Starz",
  "AMC+",
  "Crunchyroll",
  "BritBox",
  "Acorn TV",
  "Criterion Channel",
  "Tubi TV",
  "Pluto TV",
  "The Roku Channel",
] as const;

const ALIAS_LOOKUP: Record<string, string> = {
  max: "hbo max",
};

function normalize(name: string): string {
  return name.trim().toLowerCase().replace(/\+/g, " plus ").replace(/\s+/g, " ");
}

const PROVIDER_BY_NORMALIZED_NAME = new Map<string, WatchProvider>();

for (const provider of WATCH_PROVIDERS) {
  const normalized = normalize(provider.provider_name);
  if (!PROVIDER_BY_NORMALIZED_NAME.has(normalized)) {
    PROVIDER_BY_NORMALIZED_NAME.set(normalized, provider);
  }
}

function findProviderByName(name: string): WatchProvider | undefined {
  const normalized = normalize(name);
  const target = ALIAS_LOOKUP[normalized] ?? normalized;
  return PROVIDER_BY_NORMALIZED_NAME.get(target);
}

export function getStreamingServiceOptions(): StreamingServiceOption[] {
  return STREAMING_SERVICE_NAMES.map((name) => {
    const provider = findProviderByName(name);
    return {
      id: provider?.provider_id ?? null,
      name,
      providerName: provider?.provider_name ?? name,
      logoPath: provider?.logo_path ?? null,
    };
  });
}

export function mapStreamingServiceNamesToIds(names: string[]): number[] {
  return names
    .map((name) => findProviderByName(name)?.provider_id)
    .filter((id): id is number => typeof id === "number");
}

export { STREAMING_SERVICE_NAMES };
