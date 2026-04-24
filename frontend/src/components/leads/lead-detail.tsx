import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLead, useClaimLead, useReleaseLead, useQualifyLead } from "@/hooks/use-leads";
import { useTaskPoller } from "@/hooks/use-task-poller";
import { formatCurrency, formatDate } from "@/lib/utils";
import { api } from "@/lib/api";
import { LeadScoreBadge } from "./lead-score-badge";
import { SkipTraceResults } from "./skip-trace-results";
import { SkipTraceAddressDialog } from "./skip-trace-address-dialog";
import { ActivityTimeline } from "./activity-timeline";
import { DealOutcomeDialog } from "./deal-outcome-dialog";
import { EyebrowTag, MonoCell, StatusPill } from "@/components/landing-chrome";
import { X, MapPin, User, DollarSign, Search, Loader2, FileSignature } from "lucide-react";

interface LeadDetailProps {
  leadId: string;
  onClose: () => void;
}

const primaryButtonClass =
  "rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)] disabled:opacity-50";
const secondaryButtonClass =
  "rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm font-medium text-[var(--lt-text)] transition-colors hover:bg-[var(--lt-surface-2)] disabled:opacity-50";

export function LeadDetail({ leadId, onClose }: LeadDetailProps) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: lead, isLoading } = useLead(leadId);
  const claimMutation = useClaimLead();
  const releaseMutation = useReleaseLead();
  const qualifyMutation = useQualifyLead();
  const [showDealDialog, setShowDealDialog] = useState(false);
  const [qualifyTaskId, setQualifyTaskId] = useState<string | null>(null);

  useTaskPoller({
    taskId: qualifyTaskId,
    invalidateKeys: [["leads", leadId]],
    onDone: () => setQualifyTaskId(null),
    onError: () => setQualifyTaskId(null),
  });

  const isQualifying = qualifyMutation.isPending || qualifyTaskId !== null;

  if (isLoading) {
    return (
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-[480px] border-l border-[var(--lt-line-2)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] shadow-[-24px_0_80px_-32px_rgba(0,0,0,0.85)] animate-in slide-in-from-right sm:w-[480px]">
        <div className="flex h-full items-center justify-center p-6">
          <div className="text-[var(--lt-text-muted)]">Loading...</div>
        </div>
      </div>
    );
  }

  if (!lead) return null;

  const isClaimed = !!lead.user_lead;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-[480px] overflow-y-auto border-l border-[var(--lt-line-2)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] shadow-[-24px_0_80px_-32px_rgba(0,0,0,0.85)] animate-in slide-in-from-right sm:w-[480px]">
      <div className="sticky top-0 z-10 border-b border-[var(--lt-line)] bg-[rgba(19,25,41,0.94)] px-5 py-4 backdrop-blur">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-[-0.02em] text-[var(--lt-text)]">
              Case #{lead.case_number}
            </h2>
            <p className="mt-1 text-sm text-[var(--lt-text-muted)]">
              {lead.county_name} County
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full border border-transparent p-1.5 text-[var(--lt-text-muted)] transition-colors hover:border-[var(--lt-line)] hover:bg-[var(--lt-surface-2)] hover:text-[var(--lt-text)]"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="space-y-6 p-5">
        <div className="rounded-[18px] border border-[rgba(16,185,129,0.18)] bg-[rgba(16,185,129,0.08)] p-4">
          <div className="flex items-start gap-3">
            <div className="mt-1 rounded-full bg-[var(--lt-emerald-dim)] p-2 text-[var(--lt-emerald)]">
              <DollarSign size={18} />
            </div>
            <div>
              <MonoCell as="p" size="lg" tone="emerald">
                {formatCurrency(lead.surplus_amount)}
              </MonoCell>
              <p className="mt-1 text-xs text-[var(--lt-text-muted)]">
                {lead.sale_type?.replace("_", " ")} sale
                {lead.sale_date && ` on ${formatDate(lead.sale_date)}`}
              </p>
            </div>
          </div>
        </div>

        <section className="space-y-2">
          <EyebrowTag>Owner</EyebrowTag>
          <div className="space-y-1 text-sm text-[var(--lt-text)]">
            <div className="flex items-center gap-2">
              <User size={14} className="text-[var(--lt-text-dim)]" />
              <span className="font-medium">{lead.owner_name || "Unknown"}</span>
            </div>
            {lead.owner_last_known_address && (
              <p className="text-[var(--lt-text-muted)]">{lead.owner_last_known_address}</p>
            )}
          </div>
        </section>

        <section className="space-y-2">
          <EyebrowTag>Property</EyebrowTag>
          <div className="space-y-1 text-sm text-[var(--lt-text)]">
            <div className="flex items-center gap-2">
              <MapPin size={14} className="text-[var(--lt-text-dim)]" />
              <span>{lead.property_address || "No address on file"}</span>
            </div>
            {lead.property_city && (
              <p className="text-[var(--lt-text-muted)]">
                {lead.property_city}, {lead.property_state} {lead.property_zip}
              </p>
            )}
          </div>
        </section>

        {lead.user_lead && (
          <section className="space-y-2">
            <EyebrowTag>AI Qualification</EyebrowTag>
            <div className="flex items-center gap-2">
              <LeadScoreBadge score={lead.user_lead.quality_score} />
              <StatusPill status={lead.user_lead.status} />
            </div>
            {lead.user_lead.quality_reasoning && (
              <p className="text-sm leading-6 text-[var(--lt-text-muted)]">
                {lead.user_lead.quality_reasoning}
              </p>
            )}
          </section>
        )}

        <div className="flex flex-wrap gap-2 border-t border-[var(--lt-line)] pt-4">
          {!isClaimed ? (
            <button
              onClick={() => claimMutation.mutate(leadId)}
              disabled={claimMutation.isPending}
              className={primaryButtonClass}
            >
              {claimMutation.isPending ? "Claiming..." : "Claim Lead"}
            </button>
          ) : (
            <>
              <button
                onClick={() =>
                  qualifyMutation.mutate(leadId, {
                    onSuccess: (data) => {
                      if (data.task_id) {
                        setQualifyTaskId(data.task_id);
                      } else {
                        qc.invalidateQueries({ queryKey: ["leads", leadId] });
                      }
                    },
                  })
                }
                disabled={isQualifying}
                className={primaryButtonClass}
              >
                {isQualifying ? (
                  <span className="flex items-center justify-center gap-1">
                    <Loader2 size={14} className="animate-spin" /> Qualifying...
                  </span>
                ) : (
                  "Qualify with AI"
                )}
              </button>
              <button
                onClick={() => navigate(`/contracts?lead_id=${encodeURIComponent(leadId)}`)}
                className={secondaryButtonClass}
              >
                <span className="flex items-center gap-1.5">
                  <FileSignature size={14} /> Generate Contract
                </span>
              </button>
              <button
                onClick={() => releaseMutation.mutate(leadId)}
                disabled={releaseMutation.isPending}
                className={secondaryButtonClass}
              >
                Release
              </button>
              {lead.user_lead &&
                (lead.user_lead.status === "filed" ||
                  lead.user_lead.status === "paid" ||
                  lead.user_lead.status === "contacted") && (
                  <button
                    onClick={() => setShowDealDialog(true)}
                    className="rounded-full border border-[rgba(16,185,129,0.3)] bg-[var(--lt-emerald-dim)] px-4 py-2 text-sm font-medium text-[var(--lt-emerald-light)] transition-colors hover:bg-[rgba(16,185,129,0.2)]"
                  >
                    Deal Outcome
                  </button>
                )}
            </>
          )}
        </div>

        {isClaimed && (
          <SkipTraceSection
            leadId={leadId}
            lead={lead}
            skipTraceResults={lead.skip_trace_results}
          />
        )}

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
  lead,
  skipTraceResults,
}: {
  leadId: string;
  lead: any;
  skipTraceResults?: any[];
}) {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: results = [] } = useQuery<any[]>({
    queryKey: ["skip-trace", leadId],
    queryFn: () => Promise.resolve(skipTraceResults || []),
    initialData: skipTraceResults || [],
    staleTime: Infinity,
  });

  const mutation = useMutation({
    mutationFn: (payload: {
      street?: string;
      city?: string;
      state?: string;
      zip_code?: string;
      name_only: boolean;
    }) => api.skipTraceLead(leadId, payload),
    onSuccess: (data) => {
      qc.setQueryData(["skip-trace", leadId], (old: any[] = []) => [data, ...old]);
      qc.invalidateQueries({ queryKey: ["leads", leadId] });
      setDialogOpen(false);
    },
  });

  const errorMessage = mutation.error
    ? (() => {
        const e = mutation.error as any;
        const detail = e?.detail || e?.message || "Skip trace failed";
        if (typeof detail === "object" && detail?.message) return detail.message;
        return typeof detail === "string" ? detail : "Skip trace failed";
      })()
    : null;

  return (
    <div className="space-y-3 pt-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <EyebrowTag>Skip Trace</EyebrowTag>
          <Search size={14} className="text-[var(--lt-text-dim)]" />
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          disabled={mutation.isPending}
          className={primaryButtonClass}
        >
          {mutation.isPending ? (
            <span className="flex items-center gap-1">
              <Loader2 size={12} className="animate-spin" /> Running...
            </span>
          ) : results.length > 0 ? (
            "Run another Skip Trace"
          ) : (
            "Run Skip Trace"
          )}
        </button>
      </div>
      {errorMessage && (
        <p className="text-xs text-[#fca5a5]">{errorMessage}</p>
      )}
      <SkipTraceResults results={results} />
      <SkipTraceAddressDialog
        open={dialogOpen}
        lead={lead}
        onClose={() => setDialogOpen(false)}
        onSubmit={(payload) => mutation.mutate(payload)}
        isSubmitting={mutation.isPending}
      />
    </div>
  );
}
