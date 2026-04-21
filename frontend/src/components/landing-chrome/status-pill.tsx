import { cn } from "@/lib/utils";

type StatusTone = "emerald" | "blue" | "slate" | "amber" | "red" | "signed";

const STATUS_TONE_CLASSES: Record<StatusTone, string> = {
  emerald: "bg-[var(--lt-emerald-dim)] text-[var(--lt-emerald-light)]",
  blue: "bg-[var(--lt-blue-dim)] text-[#93c5fd]",
  slate: "bg-[rgba(148,163,184,0.14)] text-[var(--lt-text-muted)]",
  amber: "bg-[var(--lt-amber-dim)] text-[#fcd34d]",
  red: "bg-[var(--lt-red-dim)] text-[#fca5a5]",
  signed: "bg-[rgba(16,185,129,0.2)] text-[var(--lt-emerald)] shadow-[0_0_0_1px_rgba(16,185,129,0.18)_inset]",
};

export function statusPillTone(status?: string | null): StatusTone {
  const normalized = status?.trim().toLowerCase();

  if (!normalized || normalized === "new" || normalized === "draft" || normalized === "closed") {
    return "slate";
  }
  if (normalized === "qualified" || normalized === "approved" || normalized === "paid") {
    return "emerald";
  }
  if (normalized === "signed") {
    return "signed";
  }
  if (normalized === "contacted" || normalized === "sent" || normalized === "filed") {
    return "blue";
  }
  if (normalized === "pending" || normalized === "queued" || normalized === "processing") {
    return "amber";
  }
  if (normalized === "failed" || normalized === "error" || normalized === "rejected" || normalized === "blocked" || normalized === "miss") {
    return "red";
  }

  return "slate";
}

interface StatusPillProps {
  status?: string | null;
  label?: string | null;
  className?: string;
}

export function StatusPill({ status, label, className }: StatusPillProps) {
  const normalizedLabel = label ?? status?.replace(/_/g, " ") ?? "new";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em]",
        STATUS_TONE_CLASSES[statusPillTone(status)],
        className
      )}
    >
      {normalizedLabel}
    </span>
  );
}
