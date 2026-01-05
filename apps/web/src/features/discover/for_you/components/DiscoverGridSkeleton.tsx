interface Props {
  count?: number;
}

export default function DiscoverGridSkeleton({ count = 9 }: Props) {
  return (
    <div className="flex flex-col gap-4">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="relative overflow-hidden rounded-2xl border border-border/60 bg-background/70 shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-b from-slate-950/95 via-slate-950/65 to-slate-900/10" />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/25 via-transparent to-transparent" />
          <div className="absolute inset-0 bg-gradient-radial from-white/6 via-transparent to-transparent opacity-70 mix-blend-soft-light" />

          <div className="relative z-10 flex animate-pulse flex-col gap-6 p-6 md:flex-row">
            <div className="h-48 w-full max-w-[12rem] flex-shrink-0 overflow-hidden rounded-lg bg-slate-800/60" />

            <div className="flex flex-1 flex-col gap-4">
              <div className="space-y-3">
                <div className="h-5 w-2/3 rounded bg-slate-700/60" />
                <div className="h-4 w-24 rounded bg-slate-700/40" />
              </div>
              <div className="flex flex-wrap gap-2">
                <div className="h-5 w-20 rounded-full bg-slate-700/30" />
                <div className="h-5 w-16 rounded-full bg-slate-700/30" />
                <div className="h-5 w-24 rounded-full bg-slate-700/20" />
              </div>
              <div className="space-y-2">
                <div className="h-3 w-full rounded bg-slate-700/40" />
                <div className="h-3 w-5/6 rounded bg-slate-700/30" />
                <div className="h-3 w-4/6 rounded bg-slate-700/20" />
                <div className="h-3 w-3/5 rounded bg-slate-700/20" />
              </div>
              <div className="h-4 w-28 rounded bg-slate-700/30" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
