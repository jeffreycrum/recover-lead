import { UserButton } from "@clerk/clerk-react";
import { useSubscription } from "@/hooks/use-subscription";
import { formatPercent } from "@/lib/utils";

export function Header() {
  const { data: sub } = useSubscription();

  return (
    <header className="h-14 border-b bg-white flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-medium text-muted-foreground">
          Surplus Funds Recovery Platform
        </h2>
      </div>

      <div className="flex items-center gap-4">
        {sub && (
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="px-2 py-1 rounded bg-emerald/10 text-emerald font-medium uppercase">
              {sub.plan}
            </span>
            {sub.usage && (
              <>
                <span>
                  Quals: {sub.usage.qualifications_used}/{sub.usage.qualifications_limit}{" "}
                  ({formatPercent(sub.usage.qualifications_pct)})
                </span>
                <span>
                  Letters: {sub.usage.letters_used}/{sub.usage.letters_limit}{" "}
                  ({formatPercent(sub.usage.letters_pct)})
                </span>
              </>
            )}
          </div>
        )}
        <UserButton afterSignOutUrl="/" />
      </div>
    </header>
  );
}
