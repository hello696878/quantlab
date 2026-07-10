/**
 * Route-segment loading state (Next.js app-router convention, 37.0 UX
 * polish). Reuses the shared skeleton primitives so the shell doesn't flash
 * empty while the client bundle loads. Purely visual — no data, no network.
 */

import { Skeleton, SkeletonCard, SkeletonText } from "@/components/ui/LoadingSkeleton";

export default function RouteLoading() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 p-6" aria-busy="true" aria-label="Loading QuantLab">
      <div className="card p-5">
        <Skeleton className="h-6" style={{ width: "40%" }} />
        <SkeletonText lines={2} className="mt-3" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
      <div className="card p-5">
        <SkeletonText lines={4} />
      </div>
    </div>
  );
}
