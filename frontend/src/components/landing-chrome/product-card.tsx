import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
import { cn } from "@/lib/utils";

type ProductCardProps<T extends ElementType = "section"> = {
  as?: T;
  heading?: ReactNode;
  subtitle?: ReactNode;
  showDots?: boolean;
  headerClassName?: string;
  bodyClassName?: string;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "title">;

export function ProductCard<T extends ElementType = "section">({
  as,
  heading,
  subtitle,
  showDots = false,
  className,
  headerClassName,
  bodyClassName,
  children,
  ...props
}: ProductCardProps<T>) {
  const Component = as ?? "section";

  return (
    <Component
      className={cn(
        "relative overflow-hidden rounded-[18px] border border-[var(--lt-line)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] p-[18px] shadow-[0_40px_80px_-30px_rgba(0,0,0,0.8),0_0_0_1px_rgba(16,185,129,0.06)_inset,0_-1px_0_rgba(255,255,255,0.02)_inset]",
        className
      )}
      {...props}
    >
      {(heading || subtitle || showDots) && (
        <div
          className={cn(
            "flex items-center justify-between gap-4 border-b border-[var(--lt-line)] px-2 pb-3.5 pt-1",
            headerClassName
          )}
        >
          <div className="min-w-0">
            {heading && (
              <div className="truncate text-[13px] font-medium text-[var(--lt-text-muted)]">
                {heading}
              </div>
            )}
            {subtitle && (
              <div className="mt-1 text-xs text-[var(--lt-text-dim)]">{subtitle}</div>
            )}
          </div>
          {showDots && (
            <div className="flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-[#ef4444]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#f59e0b]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[var(--lt-emerald)]" />
            </div>
          )}
        </div>
      )}
      <div className={cn(heading || subtitle || showDots ? "px-1 pb-1 pt-4" : "", bodyClassName)}>
        {children}
      </div>
    </Component>
  );
}
