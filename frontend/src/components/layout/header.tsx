import { UserButton } from "@clerk/clerk-react";
import { useSubscription } from "@/hooks/use-subscription";
import { formatPercent } from "@/lib/utils";

export function Header() {
  const { data: sub } = useSubscription();

  return (
    <header className="flex min-h-16 items-center justify-between border-b border-[var(--lt-line)] bg-[rgba(13,18,32,0.88)] px-4 backdrop-blur sm:px-6">
      <div className="min-w-0">
        <p className="mono mb-1 text-[10px] uppercase tracking-[0.18em] text-[var(--lt-text-dim)]">
          Signed-In Workspace
        </p>
        <h2 className="truncate text-sm font-medium text-[var(--lt-text)]">
          Surplus Funds Recovery Platform
        </h2>
      </div>

      <div className="flex items-center gap-3">
        {sub && (
          <div className="hidden items-center gap-2 md:flex">
            <span className="inline-flex items-center gap-2 rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-3 py-1.5 text-[12px] text-[var(--lt-text-muted)]">
              <span className="rounded-full bg-[var(--lt-emerald-dim)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--lt-emerald)]">
                {sub.plan}
              </span>
              <span>Plan</span>
            </span>
            {sub.usage && (
              <>
                <span className="inline-flex items-center gap-2 rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-3 py-1.5 text-[12px] text-[var(--lt-text-muted)]">
                  <span className="mono text-[var(--lt-text)]">
                    {sub.usage.qualifications_used}/{sub.usage.qualifications_limit}
                  </span>
                  <span>Quals</span>
                  <span className="mono text-[var(--lt-text-dim)]">
                    {formatPercent(sub.usage.qualifications_pct)}
                  </span>
                </span>
                <span className="inline-flex items-center gap-2 rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-3 py-1.5 text-[12px] text-[var(--lt-text-muted)]">
                  <span className="mono text-[var(--lt-text)]">
                    {sub.usage.letters_used}/{sub.usage.letters_limit}
                  </span>
                  <span>Letters</span>
                  <span className="mono text-[var(--lt-text-dim)]">
                    {formatPercent(sub.usage.letters_pct)}
                  </span>
                </span>
              </>
            )}
          </div>
        )}
        <div className="rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] p-1">
          <UserButton afterSignOutUrl="/" />
        </div>
      </div>
    </header>
  );
}
