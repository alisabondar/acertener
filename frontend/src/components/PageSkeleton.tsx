import { Skeleton } from "@/components/ui/skeleton";

/** The page area while it loads: a title, the summary cards, and a list, like the real pages. */
export function ContentSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-4 w-80" />
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} data-testid="card-skeleton" className="h-20 rounded-xl" />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-16 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

/** The whole app while it starts: sidebar with its navigation, the header, and the page. */
export function AppSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading the dashboard"
      aria-busy="true"
      className="flex min-h-screen bg-background"
    >
      <div
        data-testid="sidebar-skeleton"
        className="hidden w-64 shrink-0 space-y-6 border-r bg-sidebar p-4 md:block"
      >
        <Skeleton className="h-6 w-32" />
        <div className="space-y-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      </div>
      <div className="flex-1">
        <div
          data-testid="header-skeleton"
          className="flex h-14 items-center justify-end gap-3 border-b px-4"
        >
          <Skeleton className="size-8 rounded-full" />
          <Skeleton className="h-4 w-40" />
        </div>
        <div className="mx-auto w-full max-w-7xl px-8 py-6">
          <ContentSkeleton />
        </div>
      </div>
    </div>
  );
}
