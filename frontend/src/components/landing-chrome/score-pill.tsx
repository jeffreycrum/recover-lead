import { cn } from "@/lib/utils";

interface ScorePillProps {
  score: number | null | undefined;
  className?: string;
}

export function ScorePill({ score, className }: ScorePillProps) {
  if (score === null || score === undefined) {
    return <span className="mono text-xs text-[var(--lt-text-dim)]">—</span>;
  }

  const tone =
    score >= 8
      ? "bg-[var(--lt-emerald-dim)] text-[var(--lt-emerald-light)]"
      : score >= 6
      ? "bg-[var(--lt-blue-dim)] text-[#93c5fd]"
      : score >= 4
      ? "bg-[var(--lt-amber-dim)] text-[#fcd34d]"
      : "bg-[var(--lt-red-dim)] text-[#fca5a5]";

  return (
    <span
      className={cn(
        "mono inline-flex items-center rounded-md px-2.5 py-1 text-[11px] font-semibold tracking-[-0.01em]",
        tone,
        className
      )}
    >
      {score}/10
    </span>
  );
}
