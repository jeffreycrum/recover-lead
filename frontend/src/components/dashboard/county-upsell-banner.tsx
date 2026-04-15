import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { X, TrendingUp } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";

const DISMISS_KEY_PREFIX = "recoverlead_upsell_dismissed_";
const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

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

  // Tracks in-session dismissals so the banner disappears immediately on click.
  // isDismissed() reads localStorage directly on every render to catch dismissals
  // from previous sessions — no dependency on exhaustion at init time.
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

  // Show only the top nudge (highest exhaustion %)
  const top = nudges[0];
  const pct = Math.round(top.exhaustion_pct * 100);

  const handleDismiss = () => {
    dismiss(top.county_id);
    setSessionDismissed((prev) => new Set([...prev, top.county_id]));
  };

  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
      <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
      <div className="flex-1">
        <span className="font-semibold">
          You've qualified {pct}% of {top.county_name} leads.
        </span>{" "}
        <Link
          to="/counties"
          className="underline underline-offset-2 hover:text-amber-700 dark:hover:text-amber-300"
        >
          Explore more counties
        </Link>{" "}
        to find new opportunities.
      </div>
      <button
        onClick={handleDismiss}
        aria-label="Dismiss"
        className="ml-1 rounded p-0.5 hover:bg-amber-100 dark:hover:bg-amber-900"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
