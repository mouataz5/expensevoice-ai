import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface SkeletonCardProps {
  className?: string;
  lines?: number;
  showChart?: boolean;
}

function SkeletonCard({ className, lines = 3, showChart }: SkeletonCardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-card p-5 shadow-sm",
        className
      )}
    >
      <Skeleton className="h-5 w-24 mb-3" />
      {showChart ? (
        <Skeleton className="h-64 w-full rounded-xl" />
      ) : (
        <div className="space-y-2">
          {Array.from({ length: lines }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
      )}
    </div>
  );
}

function SkeletonKpi() {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <Skeleton className="h-4 w-20 mb-2" />
      <Skeleton className="h-8 w-28" />
    </div>
  );
}

export { SkeletonCard, SkeletonKpi };
