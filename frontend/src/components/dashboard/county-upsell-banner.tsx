import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { X, TrendingUp } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { ProductCard } from "@/components/landing-chrome";

const DISMISS_KEY_PREFIX = "recoverlead_upsell_dismissed_";
const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000;

function isDismissed(countyId: string): boolean {
  const raw = localStorage.getItem(`${DISMISS_KEY_PREFIX}${countyId}`);
  if (!raw) return false;
  const expiresAt = parseInt(raw, 10);
  return Date.now() < expiresAt;
}

function dismiss(countyId: string) {
  localStorage.setItem(
    `${DISMISS_KEY_PREFIX}${countyId}`,
    String(Date.now() + DISMISS_TTL_MS)
  );
}

const UPSELL_THRESHOLD = 0.75;

export function CountyUpsellBanner() {
  const { data: exhaustion } = useQuery({
    queryKey: ["county-exhaustion"],
    queryFn: () => api.getCountyExhaustion(),
    staleTime: 5 * 60 * 1000,
  });

  const [sessionDismissed, setSessionDismissed] = useState<Set<string>>(
    () => new Set<string>()
  );

  if (!exhaustion || exhaustion.length === 0) return null;

  const nudges = exhaustion.filter(
    (c: any) =>
      c.exhaustion_pct >= UPSELL_THRESHOLD &&
      !sessionDismissed.has(c.county_id) &&
      !isDismissed(c.county_id)
  );

  if (nudges.length === 0) return null;

  const top = nudges[0];
  const pct = Math.round(top.exhaustion_pct * 100);

  const handleDismiss = () => {
    dismiss(top.county_id);
    setSessionDismissed((prev) => new Set([...prev, top.county_id]));
  };

  return (
    <ProductCard
      heading="County expansion"
      className="border-[rgba(245,158,11,0.28)] bg-[linear-gradient(180deg,rgba(245,158,11,0.08)_0%,var(--lt-bg-2)_100%)]"
      bodyClassName="pt-4"
    >
      <div className="flex items-start gap-3 text-sm text-[#fde68a]">
        <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-[#fcd34d]" />
        <div className="flex-1 leading-6">
          <span className="font-semibold text-[#fef3c7]">
            You&apos;ve qualified {pct}% of {top.county_name} leads.
          </span>{" "}
          <Link to="/counties" className="font-medium underline underline-offset-4">
            Explore more counties
          </Link>{" "}
          to find new opportunities.
        </div>
        <button
          onClick={handleDismiss}
          aria-label="Dismiss"
          className="ml-1 rounded-full border border-transparent p-1 text-[var(--lt-text-dim)] transition-colors hover:border-[var(--lt-line)] hover:bg-[var(--lt-surface)] hover:text-[var(--lt-text)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </ProductCard>
  );
}
