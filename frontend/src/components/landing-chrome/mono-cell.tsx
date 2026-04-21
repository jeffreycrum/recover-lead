import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
import { cn } from "@/lib/utils";

type MonoCellProps<T extends ElementType = "span"> = {
  as?: T;
  size?: "sm" | "md" | "lg";
  tone?: "default" | "muted" | "emerald";
  children: ReactNode;
} & Omit<ComponentPropsWithoutRef<T>, "as">;

export function MonoCell<T extends ElementType = "span">({
  as,
  size = "md",
  tone = "default",
  className,
  children,
  ...props
}: MonoCellProps<T>) {
  const Component = as ?? "span";

  const sizeClass =
    size === "lg"
      ? "text-2xl sm:text-3xl"
      : size === "sm"
      ? "text-xs"
      : "text-sm";
  const toneClass =
    tone === "emerald"
      ? "text-[var(--lt-emerald)]"
      : tone === "muted"
      ? "text-[var(--lt-text-muted)]"
      : "text-[var(--lt-text)]";

  return (
    <Component
      className={cn(
        "mono font-mono font-semibold tracking-[-0.02em]",
        sizeClass,
        toneClass,
        className
      )}
      {...props}
    >
      {children}
    </Component>
  );
}
