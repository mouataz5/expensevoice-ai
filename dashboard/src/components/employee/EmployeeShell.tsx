import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function EmployeePage({
  children,
  className,
}: React.PropsWithChildren<{ className?: string }>) {
  return <div className={cn("space-y-6", className)}>{children}</div>;
}

export function EmployeeSectionCard({
  title,
  subtitle,
  actions,
  children,
  className,
}: React.PropsWithChildren<{
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  className?: string;
}>) {
  return (
    <Card className={cn("border-border/70 shadow-sm", className)}>
      <CardContent className="p-5 space-y-4">
        {(title || subtitle || actions) && (
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-0.5">
              {title ? <h2 className="text-base font-semibold text-foreground">{title}</h2> : null}
              {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
            </div>
            {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
          </div>
        )}
        {children}
      </CardContent>
    </Card>
  );
}

export function EmployeeKpiCard({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("border-border/70 bg-card shadow-sm", className)}>
      <CardContent className="p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-2 text-2xl font-semibold text-foreground">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}

export function EmployeeHero({
  eyebrow,
  title,
  subtitle,
  meta,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  meta?: Array<{ label: string; value: React.ReactNode }>;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-background to-background p-5 shadow-sm">
      <div className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full bg-primary/10 blur-2xl" />
      <div className="pointer-events-none absolute -left-10 -bottom-10 h-24 w-24 rounded-full bg-primary/10 blur-2xl" />
      <div className="relative space-y-2">
        {eyebrow ? <p className="text-xs uppercase tracking-wide text-primary">{eyebrow}</p> : null}
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
        {meta?.length ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {meta.map((m) => (
              <div key={m.label} className="rounded-full border border-border/70 bg-card/80 px-3 py-1 text-xs">
                <span className="text-muted-foreground">{m.label}: </span>
                <span className="font-semibold text-foreground">{m.value}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
