export default function BookCardSkeleton() {
  return (
    <div aria-hidden="true" className="flex gap-4 rounded-lg border border-zinc-200 p-4 motion-safe:animate-pulse">
      <div className="h-[120px] w-[64px] shrink-0 rounded bg-zinc-100 sm:w-[80px]" />
      <div className="min-w-0 flex-1 space-y-3 py-1">
        <div className="h-5 w-4/5 rounded bg-zinc-200" />
        <div className="h-4 w-1/2 rounded bg-zinc-100" />
        <div className="h-4 w-1/3 rounded bg-zinc-100" />
        <div className="space-y-2 pt-3">
          <div className="h-3 rounded bg-zinc-100" />
          <div className="h-3 w-5/6 rounded bg-zinc-100" />
        </div>
        <div className="h-11 w-28 rounded bg-zinc-100" />
      </div>
    </div>
  );
}
