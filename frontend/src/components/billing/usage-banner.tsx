import { useSubscription } from "@/hooks/use-subscription";
import { useNavigate } from "react-router-dom";
import { useState } from "react";

const OVERAGE_PRICES = {
  qualification: 0.02,
  letter: 0.05,
};

type BannerLevel = "warning" | "danger" | "blocked" | "overage" | null;

function getBannerLevel(pct: number, plan: string): BannerLevel {
  if (pct >= 100 && plan === "free") return "blocked";
  if (pct >= 100 && plan !== "free") return "overage";
  if (pct >= 90) return "danger";
  if (pct >= 80) return "warning";
  return null;
}

const bannerStyles: Record<string, string> = {
  warning: "border-[rgba(245,158,11,0.35)] bg-[rgba(245,158,11,0.12)] text-[#fde68a]",
  danger: "border-[rgba(239,68,68,0.4)] bg-[rgba(239,68,68,0.14)] text-[#fecaca]",
  blocked: "border-[rgba(239,68,68,0.45)] bg-[rgba(239,68,68,0.18)] text-[#fee2e2]",
  overage: "border-[rgba(59,130,246,0.4)] bg-[rgba(59,130,246,0.14)] text-[#bfdbfe]",
};

export function UsageBanner() {
  const { data: sub } = useSubscription();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(() =>
    sessionStorage.getItem("usage-banner-dismissed") === "true"
  );

  if (!sub?.usage || dismissed) return null;

  const qualLevel = getBannerLevel(sub.usage.qualifications_pct, sub.plan);
  const letterLevel = getBannerLevel(sub.usage.letters_pct, sub.plan);

  // Pick the most severe level
  const levels: BannerLevel[] = ["blocked", "overage", "danger", "warning"];
  const activeLevel = levels.find((l) => l === qualLevel || l === letterLevel) ?? null;

  if (!activeLevel) return null;

  const handleDismiss = () => {
    sessionStorage.setItem("usage-banner-dismissed", "true");
    setDismissed(true);
  };

  const getMessage = (): string => {
    if (activeLevel === "blocked") {
      return "You've reached your free tier limit. Upgrade to continue qualifying leads and generating letters.";
    }
    if (activeLevel === "overage") {
      const parts: string[] = [];
      if (sub.usage.qualifications_overage > 0) {
        parts.push(
          `${sub.usage.qualifications_overage} qualification${sub.usage.qualifications_overage !== 1 ? "s" : ""} at $${OVERAGE_PRICES.qualification}/ea`
        );
      }
      if (sub.usage.letters_overage > 0) {
        parts.push(
          `${sub.usage.letters_overage} letter${sub.usage.letters_overage !== 1 ? "s" : ""} at $${OVERAGE_PRICES.letter}/ea`
        );
      }
      return `Overage usage this period: ${parts.join(", ")}. Estimated additional charges: $${sub.usage.overage_cost_estimate?.toFixed(2) ?? "0.00"}.`;
    }
    if (activeLevel === "danger") {
      const qualRemaining = Math.max(0, sub.usage.qualifications_limit - sub.usage.qualifications_used);
      const letterRemaining = Math.max(0, sub.usage.letters_limit - sub.usage.letters_used);
      return `Almost at your limit! ${qualRemaining} qualifications and ${letterRemaining} letters remaining.`;
    }
    // warning
    const maxPct = Math.max(sub.usage.qualifications_pct, sub.usage.letters_pct);
    return `You've used ${Math.round(maxPct)}% of your plan allowance. Consider upgrading for more capacity.`;
  };

  return (
    <div
      className={`flex flex-col gap-3 border-b px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-6 ${bannerStyles[activeLevel]}`}
    >
      <span className="max-w-4xl leading-6">{getMessage()}</span>
      <div className="ml-auto flex items-center gap-2 shrink-0">
        {(activeLevel === "blocked" || activeLevel === "warning" || activeLevel === "danger") && (
          <button
            onClick={() => navigate("/settings")}
            className="rounded-full bg-[var(--lt-emerald)] px-3 py-1.5 text-xs font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)]"
          >
            Upgrade
          </button>
        )}
        {activeLevel !== "blocked" && (
          <button
            onClick={handleDismiss}
            className="rounded-full border border-transparent px-3 py-1.5 text-xs font-medium text-[var(--lt-text-muted)] transition-colors hover:border-[var(--lt-line)] hover:bg-[var(--lt-surface)] hover:text-[var(--lt-text)]"
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}
