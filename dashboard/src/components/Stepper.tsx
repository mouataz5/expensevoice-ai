import * as React from "react";
import { cn } from "@/lib/utils";

export interface StepItem {
  key: string;
  label: string;
  done?: boolean;
  active?: boolean;
}

interface StepperProps {
  steps: StepItem[];
  className?: string;
}

function Stepper({ steps, className }: StepperProps) {
  return (
    <nav className={cn("flex items-center gap-2 flex-wrap", className)} aria-label="Progress">
      {steps.map((step, i) => (
        <React.Fragment key={step.key}>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium ring-2 ring-border",
                step.active && "bg-primary text-primary-foreground ring-primary",
                step.done && !step.active && "bg-primary/15 text-primary ring-primary/30",
                !step.done && !step.active && "bg-muted text-muted-foreground"
              )}
            >
              {step.done && !step.active ? "✓" : i + 1}
            </span>
            <span
              className={cn(
                "text-sm font-medium",
                step.active ? "text-foreground" : "text-muted-foreground"
              )}
            >
              {step.label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <span className="h-px w-4 bg-border shrink-0" aria-hidden />
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}

export { Stepper };
