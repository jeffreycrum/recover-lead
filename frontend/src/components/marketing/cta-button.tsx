import type { MouseEvent, ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTrackEvent } from "@/hooks/use-track-event";
import type { AnalyticsEvent, AnalyticsProps } from "@/lib/analytics";
import { cn } from "@/lib/utils";

export type CtaVariant = "primary" | "secondary";

interface CtaButtonProps {
  to: string;
  variant?: CtaVariant;
  event?: AnalyticsEvent;
  eventProps?: AnalyticsProps;
  className?: string;
  children: ReactNode;
}

const baseStyles =
  "inline-flex items-center justify-center rounded-md px-6 py-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald focus-visible:ring-offset-2";

const variantStyles: Record<CtaVariant, string> = {
  primary: "bg-emerald text-white hover:bg-emerald/90",
  secondary:
    "border border-input bg-background text-foreground hover:bg-accent hover:text-accent-foreground",
};

export function CtaButton({
  to,
  variant = "primary",
  event,
  eventProps,
  className,
  children,
}: CtaButtonProps) {
  const track = useTrackEvent();
  const handleClick = (_e: MouseEvent<HTMLAnchorElement>) => {
    if (event) track(event, eventProps);
  };
  return (
    <Link
      to={to}
      onClick={handleClick}
      className={cn(baseStyles, variantStyles[variant], className)}
    >
      {children}
    </Link>
  );
}
