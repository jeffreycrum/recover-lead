import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

export function EyebrowTag({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<"span">) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-[rgba(16,185,129,0.2)] bg-[var(--lt-emerald-dim)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-emerald)]",
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
