import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

export function DataRow({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<"div">) {
  return (
    <div
      className={cn(
        "grid items-center gap-3 rounded-[10px] border border-transparent bg-[rgba(255,255,255,0.015)] px-3 py-3 transition-colors hover:border-[var(--lt-line)] hover:bg-[rgba(16,185,129,0.04)] sm:grid-cols-[minmax(0,1fr)_auto_auto_auto]",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function DataRowMeta({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<"div">) {
  return (
    <div className={cn("text-xs text-[var(--lt-text-dim)]", className)} {...props}>
      {children}
    </div>
  );
}

export function DataRowAmount({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<"div">) {
  return (
    <div
      className={cn(
        "mono text-sm font-semibold tracking-[-0.01em] text-[var(--lt-emerald)]",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
