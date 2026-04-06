import { cn } from "@/lib/utils";

interface LeadScoreBadgeProps {
  score: number | null;
}

export function LeadScoreBadge({ score }: LeadScoreBadgeProps) {
  if (score === null || score === undefined) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }

  const color =
    score >= 8
      ? "bg-emerald/10 text-emerald"
      : score >= 6
      ? "bg-blue-100 text-blue-700"
      : score >= 4
      ? "bg-amber-100 text-amber-700"
      : "bg-red-100 text-red-700";

  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium", color)}>
      {score}/10
    </span>
  );
}
