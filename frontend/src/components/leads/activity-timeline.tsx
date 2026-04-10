import { useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Clock, MessageSquare, Zap, FileText, Search, ArrowRight, Send, Loader2 } from "lucide-react";

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
  claimed: "text-emerald bg-emerald/10",
  released: "text-gray-500 bg-gray-100",
  status_change: "text-blue-600 bg-blue-50",
  qualified: "text-purple-600 bg-purple-50",
  qualify_started: "text-purple-400 bg-purple-50",
  letter_generated: "text-amber-600 bg-amber-50",
  skip_trace_completed: "text-cyan-600 bg-cyan-50",
  deal_paid: "text-emerald bg-emerald/10",
  deal_closed: "text-gray-600 bg-gray-100",
  note: "text-blue-500 bg-blue-50",
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
    <div className="pt-2">
      <h3 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
        <Clock size={14} /> Activity
      </h3>

      {/* Add note input */}
      <div className="flex gap-2 mb-4">
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
          className="flex-1 px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-1 focus:ring-emerald"
        />
        <button
          onClick={() => noteText.trim() && addNote.mutate(noteText.trim())}
          disabled={!noteText.trim() || addNote.isPending}
          className="px-3 py-1.5 text-sm bg-emerald text-white rounded-md hover:bg-emerald/90 disabled:opacity-50"
        >
          {addNote.isPending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
        </button>
      </div>

      {isLoading ? (
        <p className="text-xs text-muted-foreground">Loading activities...</p>
      ) : activities.length === 0 ? (
        <p className="text-xs text-muted-foreground">No activity yet</p>
      ) : (
        <div className="space-y-0">
          {activities.map((activity: any) => {
            const Icon = ACTIVITY_ICONS[activity.activity_type] || Clock;
            const colorClass = ACTIVITY_COLORS[activity.activity_type] || "text-gray-500 bg-gray-100";
            return (
              <div key={activity.id} className="flex gap-3 py-2">
                <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${colorClass}`}>
                  <Icon size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm">{activity.description || activity.activity_type.replace(/_/g, " ")}</p>
                  <p className="text-xs text-muted-foreground">{formatRelativeTime(activity.created_at)}</p>
                </div>
              </div>
            );
          })}
          {hasNextPage && (
            <button
              onClick={() => fetchNextPage()}
              disabled={isFetchingNextPage}
              className="text-xs text-emerald hover:underline mt-2"
            >
              {isFetchingNextPage ? "Loading..." : "Load more"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
