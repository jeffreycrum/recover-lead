import { ScorePill } from "@/components/landing-chrome";

interface LeadScoreBadgeProps {
  score: number | null;
}

export function LeadScoreBadge({ score }: LeadScoreBadgeProps) {
  return <ScorePill score={score} />;
}
