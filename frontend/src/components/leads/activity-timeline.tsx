import { useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Clock, MessageSquare, Zap, FileText, Search, ArrowRight, Send, Loader2 } from "lucide-react";
import { EyebrowTag } from "@/components/landing-chrome";

const ACTIVITY_ICONS: Record<string, any> = {
  claimed: ArrowRight,
  released: ArrowRight,
  status_change: ArrowRight,
  qualified: Zap,
  qualify_started: Zap,
  letter_generated: FileText,
  skip_trace_completed: Search,
  deal_paid: Clock,
  deal_closed: Clock,
  note: MessageSquare,
};

const ACTIVITY_COLORS: Record<string, string> = {
  claimed: "text-[var(--lt-emerald)] bg-[var(--lt-emerald-dim)]",
  released: "text-[var(--lt-text-muted)] bg-[rgba(148,163,184,0.12)]",
  status_change: "text-[#93c5fd] bg-[var(--lt-blue-dim)]",
  qualified: "text-[#c4b5fd] bg-[var(--lt-violet-dim)]",
  qualify_started: "text-[#c4b5fd] bg-[var(--lt-violet-dim)]",
  letter_generated: "text-[#fcd34d] bg-[var(--lt-amber-dim)]",
  skip_trace_completed: "text-[#67e8f9] bg-[rgba(6,182,212,0.16)]",
  deal_paid: "text-[var(--lt-emerald)] bg-[var(--lt-emerald-dim)]",
  deal_closed: "text-[var(--lt-text-muted)] bg-[rgba(148,163,184,0.12)]",
  note: "text-[#93c5fd] bg-[var(--lt-blue-dim)]",
};

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

interface ActivityTimelineProps {
  leadId: string;
}

export function ActivityTimeline({ leadId }: ActivityTimelineProps) {
  const qc = useQueryClient();
  const [noteText, setNoteText] = useState("");

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteQuery({
    queryKey: ["activities", leadId],
    queryFn: ({ pageParam }) => {
      const params: Record<string, string> = { limit: "20" };
      if (pageParam) params.cursor = pageParam;
      return api.getLeadActivities(leadId, params);
    },
    getNextPageParam: (lastPage: any) =>
      lastPage.has_more ? lastPage.next_cursor : undefined,
    initialPageParam: undefined as string | undefined,
  });

  const addNote = useMutation({
    mutationFn: (description: string) => api.createLeadActivity(leadId, description),
    onSuccess: () => {
      setNoteText("");
      qc.invalidateQueries({ queryKey: ["activities", leadId] });
    },
  });

  const activities = data?.pages.flatMap((p: any) => p.items) || [];

  return (
    <div className="space-y-3 pt-2">
      <EyebrowTag>Activity</EyebrowTag>

      <div className="flex gap-2">
        <input
          type="text"
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && noteText.trim()) {
              addNote.mutate(noteText.trim());
            }
          }}
          placeholder="Add a note..."
          className="flex-1 rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm text-[var(--lt-text)] placeholder:text-[var(--lt-text-dim)] focus:outline-none focus:ring-1 focus:ring-[var(--lt-emerald)]"
        />
        <button
          onClick={() => noteText.trim() && addNote.mutate(noteText.trim())}
          disabled={!noteText.trim() || addNote.isPending}
          className="rounded-full bg-[var(--lt-emerald)] px-3 py-2 text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)] disabled:opacity-50"
        >
          {addNote.isPending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
        </button>
      </div>

      {isLoading ? (
        <p className="text-xs text-[var(--lt-text-muted)]">Loading activities...</p>
      ) : activities.length === 0 ? (
        <p className="text-xs text-[var(--lt-text-muted)]">No activity yet</p>
      ) : (
        <div className="space-y-2">
          {activities.map((activity: any) => {
            const Icon = ACTIVITY_ICONS[activity.activity_type] || Clock;
            const colorClass = ACTIVITY_COLORS[activity.activity_type] || "text-[var(--lt-text-muted)] bg-[rgba(148,163,184,0.12)]";
            return (
              <div
                key={activity.id}
                className="flex gap-3 rounded-[14px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.015)] px-3 py-3"
              >
                <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full ${colorClass}`}>
                  <Icon size={14} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-[var(--lt-text)]">
                    {activity.description || activity.activity_type.replace(/_/g, " ")}
                  </p>
                  <p className="text-xs text-[var(--lt-text-muted)]">
                    {formatRelativeTime(activity.created_at)}
                  </p>
                </div>
              </div>
            );
          })}
          {hasNextPage && (
            <button
              onClick={() => fetchNextPage()}
              disabled={isFetchingNextPage}
              className="text-xs font-medium text-[var(--lt-emerald)] hover:underline"
            >
              {isFetchingNextPage ? "Loading..." : "Load more"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
