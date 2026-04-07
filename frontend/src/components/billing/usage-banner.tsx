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
  warning: "bg-amber-50 border-amber-200 text-amber-800",
  danger: "bg-red-50 border-red-200 text-red-800",
  blocked: "bg-red-50 border-red-300 text-red-900",
  overage: "bg-blue-50 border-blue-200 text-blue-800",
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
    <div className={`flex items-center justify-between px-4 py-2 border-b text-sm ${bannerStyles[activeLevel]}`}>
      <span>{getMessage()}</span>
      <div className="flex items-center gap-2 ml-4 shrink-0">
        {(activeLevel === "blocked" || activeLevel === "warning" || activeLevel === "danger") && (
          <button
            onClick={() => navigate("/settings")}
            className="px-3 py-1 text-xs font-medium bg-emerald text-white rounded hover:bg-emerald/90"
          >
            Upgrade
          </button>
        )}
        {activeLevel !== "blocked" && (
          <button
            onClick={handleDismiss}
            className="text-xs opacity-60 hover:opacity-100"
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}
