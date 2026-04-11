import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLead, useClaimLead, useReleaseLead, useQualifyLead } from "@/hooks/use-leads";
import { formatCurrency, formatDate } from "@/lib/utils";
import { api } from "@/lib/api";
import { LeadScoreBadge } from "./lead-score-badge";
import { SkipTraceResults } from "./skip-trace-results";
import { ActivityTimeline } from "./activity-timeline";
import { DealOutcomeDialog } from "./deal-outcome-dialog";
import { X, MapPin, User, DollarSign, Zap, Search, Loader2 } from "lucide-react";

interface LeadDetailProps {
  leadId: string;
  onClose: () => void;
}

export function LeadDetail({ leadId, onClose }: LeadDetailProps) {
  const { data: lead, isLoading } = useLead(leadId);
  const claimMutation = useClaimLead();
  const releaseMutation = useReleaseLead();
  const qualifyMutation = useQualifyLead();
  const [showDealDialog, setShowDealDialog] = useState(false);

  if (isLoading) {
    return (
      <div className="fixed inset-y-0 right-0 w-[480px] bg-white border-l shadow-xl z-50 animate-in slide-in-from-right">
        <div className="p-6 flex items-center justify-center h-full">
          <div className="animate-pulse text-muted-foreground">Loading...</div>
        </div>
      </div>
    );
  }

  if (!lead) return null;

  const isClaimed = !!lead.user_lead;

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-white border-l shadow-xl z-50 overflow-y-auto animate-in slide-in-from-right">
      <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Case #{lead.case_number}</h2>
          <p className="text-sm text-muted-foreground">{lead.county_name} County</p>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
          <X size={20} />
        </button>
      </div>

      <div className="p-6 space-y-6">
        {/* Surplus Amount */}
        <div className="flex items-center gap-3 p-4 bg-emerald/5 rounded-lg border border-emerald/20">
          <DollarSign className="text-emerald" size={24} />
          <div>
            <p className="text-2xl font-bold text-emerald">
              {formatCurrency(lead.surplus_amount)}
            </p>
            <p className="text-xs text-muted-foreground">
              {lead.sale_type?.replace("_", " ")} sale
              {lead.sale_date && ` on ${formatDate(lead.sale_date)}`}
            </p>
          </div>
        </div>

        {/* Owner */}
        <section>
          <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
            <User size={14} /> Owner
          </h3>
          <p className="font-medium">{lead.owner_name || "Unknown"}</p>
          {lead.owner_last_known_address && (
            <p className="text-sm text-muted-foreground">{lead.owner_last_known_address}</p>
          )}
        </section>

        {/* Property */}
        <section>
          <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
            <MapPin size={14} /> Property
          </h3>
          <p>{lead.property_address || "No address on file"}</p>
          {lead.property_city && (
            <p className="text-sm text-muted-foreground">
              {lead.property_city}, {lead.property_state} {lead.property_zip}
            </p>
          )}
        </section>

        {/* Score */}
        {lead.user_lead && (
          <section>
            <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
              <Zap size={14} /> AI Qualification
            </h3>
            <div className="flex items-center gap-2 mb-2">
              <LeadScoreBadge score={lead.user_lead.quality_score} />
              <span className="text-xs text-muted-foreground capitalize">
                {lead.user_lead.status}
              </span>
            </div>
            {lead.user_lead.quality_reasoning && (
              <p className="text-sm text-muted-foreground">{lead.user_lead.quality_reasoning}</p>
            )}
          </section>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-4 border-t">
          {!isClaimed ? (
            <button
              onClick={() => claimMutation.mutate(leadId)}
              disabled={claimMutation.isPending}
              className="flex-1 px-4 py-2 bg-emerald text-white rounded-md hover:bg-emerald/90 disabled:opacity-50 text-sm font-medium"
            >
              {claimMutation.isPending ? "Claiming..." : "Claim Lead"}
            </button>
          ) : (
            <>
              <button
                onClick={() => qualifyMutation.mutate(leadId)}
                disabled={qualifyMutation.isPending}
                className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 text-sm font-medium"
              >
                {qualifyMutation.isPending ? "Qualifying..." : "Qualify with AI"}
              </button>
              <button
                onClick={() => releaseMutation.mutate(leadId)}
                disabled={releaseMutation.isPending}
                className="px-4 py-2 border rounded-md hover:bg-gray-50 text-sm"
              >
                Release
              </button>
              {lead.user_lead && (lead.user_lead.status === "filed" || lead.user_lead.status === "paid" || lead.user_lead.status === "contacted") && (
                <button
                  onClick={() => setShowDealDialog(true)}
                  className="px-4 py-2 border border-emerald text-emerald rounded-md hover:bg-emerald/5 text-sm"
                >
                  Deal Outcome
                </button>
              )}
            </>
          )}
        </div>

        {/* Skip Trace */}
        {isClaimed && (
          <SkipTraceSection leadId={leadId} skipTraceResults={lead.skip_trace_results} />
        )}

        {/* Activity Timeline */}
        {isClaimed && <ActivityTimeline leadId={leadId} />}
      </div>

      {showDealDialog && lead.user_lead && (
        <DealOutcomeDialog
          leadId={leadId}
          currentStatus={lead.user_lead.status}
          onClose={() => setShowDealDialog(false)}
        />
      )}
    </div>
  );
}


function SkipTraceSection({
  leadId,
  skipTraceResults,
}: {
  leadId: string;
  skipTraceResults?: any[];
}) {
  const qc = useQueryClient();

  // Source of truth: lead detail query already loads skip_trace_results.
  // This query just mirrors it, keyed on leadId, so we get proper
  // cache invalidation when the lead is refetched.
  const { data: results = [] } = useQuery<any[]>({
    queryKey: ["skip-trace", leadId],
    queryFn: () => Promise.resolve(skipTraceResults || []),
    initialData: skipTraceResults || [],
  });

  const mutation = useMutation({
    mutationFn: () => api.skipTraceLead(leadId),
    onSuccess: () => {
      // Invalidate the lead so it refetches with the new skip trace result
      qc.invalidateQueries({ queryKey: ["leads", leadId] });
      qc.invalidateQueries({ queryKey: ["skip-trace", leadId] });
    },
  });

  const errorMessage = mutation.error
    ? (() => {
        const e = mutation.error as any;
        const detail = e?.detail || e?.message || "Skip trace failed";
        return typeof detail === "string" ? detail : detail.message || "Skip trace failed";
      })()
    : null;

  return (
    <div className="pt-2">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
          <Search size={14} /> Skip Trace
        </h3>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
        >
          {mutation.isPending ? (
            <>
              <Loader2 size={12} className="animate-spin" /> Running...
            </>
          ) : results.length > 0 ? (
            "Re-run Skip Trace"
          ) : (
            "Run Skip Trace"
          )}
        </button>
      </div>
      {errorMessage && (
        <p className="text-xs text-red-600 mb-2">{errorMessage}</p>
      )}
      <SkipTraceResults results={results} />
    </div>
  );
}
