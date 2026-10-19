import { ChevronDown } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** A native select (keyboard and screen-reader friendly) with the arrow set in from the edge. */
export function NativeSelect({ className, ...props }: ComponentProps<"select">) {
  return (
    <div className="relative inline-flex">
      <select
        {...props}
        className={cn(
          "h-9 w-full appearance-none rounded-lg border bg-card pr-9 pl-3 text-[14px] text-foreground",
          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          className,
        )}
      />
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
      />
    </div>
  );
}
