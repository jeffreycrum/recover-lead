import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

interface CountyChipProps extends ComponentPropsWithoutRef<"span"> {
  variant?: "active" | "pending";
}

export function CountyChip({
  variant = "active",
  className,
  children,
  ...props
}: CountyChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-[var(--lt-line)] bg-[var(--lt-bg-2)] px-3 py-2 text-xs text-[var(--lt-text-muted)]",
        className
      )}
      {...props}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          variant === "active" ? "bg-[var(--lt-emerald)]" : "bg-[var(--lt-amber)]"
        )}
      />
      {children}
    </span>
  );
}

interface StateGroupLabelProps {
  label: string;
  count: number;
  className?: string;
}

export function StateGroupLabel({ label, count, className }: StateGroupLabelProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--lt-text-dim)]",
        className
      )}
    >
      <span>{label}</span>
      <span className="rounded-full border border-[var(--lt-line)] bg-[var(--lt-bg-2)] px-2 py-0.5 text-[10px] font-semibold text-[var(--lt-text-muted)]">
        {count}
      </span>
    </div>
  );
}
