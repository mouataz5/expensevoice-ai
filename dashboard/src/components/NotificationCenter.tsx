/**
 * Notification Center — Topbar bell with badge count and dropdown of latest alerts.
 * Shows unresolved critical count; dropdown lists latest 5 alerts with link to Alerts page.
 * Director/Admin only (caller should hide for employee).
 */
import { useRef, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchNotifications } from "../api/alerts";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function BellIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["alerts-notifications"],
    queryFn: () => fetchNotifications(5),
    refetchInterval: 60_000,
  });

  const count = data?.count ?? 0;
  const items = data?.items ?? [];

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="ghost"
        size="icon"
        className="rounded-xl relative"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
      >
        <BellIcon className="text-muted-foreground" />
        {count > 0 && (
          <span
            className={cn(
              "absolute -top-0.5 rounded-full bg-destructive text-destructive-foreground text-xs font-bold min-w-[18px] h-[18px] flex items-center justify-center px-1",
              "end-0 rtl:end-auto rtl:start-0"
            )}
          >
            {count > 99 ? "99+" : count}
          </span>
        )}
      </Button>

      {open && (
        <div
          className={cn(
            "absolute top-full mt-1 end-0 rtl:end-auto rtl:start-0",
            "w-80 max-h-[360px] overflow-hidden",
            "rounded-2xl border border-border bg-card shadow-lg z-50",
            "flex flex-col"
          )}
        >
          <div className="p-3 border-b border-border flex items-center justify-between">
            <span className="font-medium text-sm">الإشعارات</span>
            <Link to="/alerts" onClick={() => setOpen(false)}>
              <span className="text-xs text-primary hover:underline">عرض الكل</span>
            </Link>
          </div>
          <div className="overflow-y-auto flex-1">
            {isLoading && (
              <div className="p-4 text-sm text-muted-foreground text-center">
                جاري التحميل...
              </div>
            )}
            {!isLoading && items.length === 0 && (
              <div className="p-4 text-sm text-muted-foreground text-center">
                لا توجد إشعارات
              </div>
            )}
            {!isLoading &&
              items.length > 0 &&
              items.map((a) => (
                <Link
                  key={a.id}
                  to="/alerts"
                  onClick={() => setOpen(false)}
                  className="block p-3 border-b border-border last:border-0 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        a.severity === "critical"
                          ? "destructive"
                          : a.severity === "warning"
                            ? "warning"
                            : "info"
                      }
                      className="text-xs shrink-0"
                    >
                      {a.severity}
                    </Badge>
                    <span className="text-xs text-muted-foreground truncate">
                      {new Date(a.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm mt-1 line-clamp-2">{a.message}</p>
                </Link>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
