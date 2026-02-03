interface Props {
  count?: number;
}

export default function DiscoverGridSkeleton({ count = 9 }: Props) {
  return (
    <div className="flex flex-col gap-4">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="relative overflow-hidden rounded-xl border border-white/10 bg-background/95 shadow-lg card-grain">
          {/* Shimmer overlay */}
          <div className="absolute inset-0 overflow-hidden">
            <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-gold/10 to-transparent" />
          </div>

          <div className="relative z-10 flex animate-pulse flex-col gap-6 p-6 md:flex-row">
            {/* Poster skeleton */}
            <div className="h-48 w-full max-w-[12rem] flex-shrink-0 overflow-hidden rounded-lg bg-muted/20" />

            <div className="flex flex-1 flex-col gap-4">
              {/* Title & year */}
              <div className="space-y-3">
                <div className="h-6 w-2/3 rounded bg-muted/30" />
                <div className="h-4 w-24 rounded bg-muted/20" />
              </div>

              {/* Genre chips */}
              <div className="flex flex-wrap gap-2">
                <div className="h-5 w-20 rounded-full bg-muted/20" />
                <div className="h-5 w-16 rounded-full bg-muted/20" />
                <div className="h-5 w-24 rounded-full bg-muted/15" />
              </div>

              {/* Description lines */}
              <div className="space-y-2">
                <div className="h-3 w-full rounded bg-muted/25" />
                <div className="h-3 w-5/6 rounded bg-muted/20" />
                <div className="h-3 w-4/6 rounded bg-muted/15" />
                <div className="h-3 w-3/5 rounded bg-muted/15" />
              </div>

              {/* Button placeholder */}
              <div className="h-10 w-32 rounded-full bg-primary/20" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
