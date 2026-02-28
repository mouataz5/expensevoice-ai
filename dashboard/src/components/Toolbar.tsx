import * as React from "react";
import { cn } from "@/lib/utils";

function Toolbar({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 p-1",
        className
      )}
      {...props}
    />
  );
}

export { Toolbar };
