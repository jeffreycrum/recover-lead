import { useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { useMyLeads } from "@/hooks/use-leads";
import { useQueryClient } from "@tanstack/react-query";
import { formatCurrency } from "@/lib/utils";
import { X, FileText, Loader2, CheckCircle } from "lucide-react";
import { MonoCell, ProductCard } from "@/components/landing-chrome";

interface LetterBatchDialogProps {
  open: boolean;
  onClose: () => void;
}

export function LetterBatchDialog({ open, onClose }: LetterBatchDialogProps) {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  const { data: myLeads } = useMyLeads({ status: "qualified" });
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [_taskId, setTaskId] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);

  useEffect(() => {
    if (open) {
      setSelectedIds(new Set());
      setGenerating(false);
      setTaskId(null);
      setDone(false);
      setError(null);
    }
  }, [open]);

  if (!open) return null;

  const leads = myLeads?.items ?? [];

  const toggleLead = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedIds(next);
  };

  const toggleAll = () => {
    if (selectedIds.size === leads.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(leads.map((l: any) => l.lead_id)));
    }
  };

  const handleGenerate = async () => {
    if (selectedIds.size === 0) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await api.generateBatch(Array.from(selectedIds));
      setTaskId(result.task_id);

      // Poll for completion
      if (result.task_id && result.task_id !== "placeholder") {
        for (let i = 0; i < 60; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          const status = await api.getTaskStatus(result.task_id);
          if (status.status === "SUCCESS" || status.status === "FAILURE") break;
        }
      }

      setDone(true);
      qc.invalidateQueries({ queryKey: ["letters"] });
    } catch (err: unknown) {
      const message =
        typeof err === "object" &&
        err !== null &&
        "message" in err &&
        typeof (err as { message?: unknown }).message === "string"
          ? ((err as { message: string }).message)
          : "Failed to generate letters";
      setError(message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg max-h-[80vh] overflow-hidden rounded-[24px] border border-[var(--lt-line-2)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] shadow-[0_40px_120px_-40px_rgba(0,0,0,0.9)] flex flex-col">
        <div className="px-6 py-4 border-b border-[var(--lt-line)] flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2 text-[var(--lt-text)]">
            <FileText size={18} />
            Batch Generate Letters
          </h3>
          <button
            onClick={onClose}
            className="rounded-full border border-transparent p-1.5 text-[var(--lt-text-muted)] transition-colors hover:border-[var(--lt-line)] hover:bg-[var(--lt-surface-2)] hover:text-[var(--lt-text)]"
          >
            <X size={18} />
          </button>
        </div>

        {done ? (
          <div className="p-8 text-center">
            <CheckCircle size={48} className="text-emerald mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--lt-text)]">Letters generated!</h3>
            <p className="mt-1 text-sm text-[var(--lt-text-muted)]">
              {selectedIds.size} letters have been created as drafts.
            </p>
            <button
              onClick={onClose}
              className="mt-4 rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)]"
            >
              View Letters
            </button>
          </div>
        ) : generating ? (
          <div className="p-8 text-center">
            <Loader2 size={48} className="animate-spin text-emerald mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--lt-text)]">
              Generating {selectedIds.size} letters...
            </h3>
            <p className="mt-1 text-sm text-[var(--lt-text-muted)]">
              This may take a minute.
            </p>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-auto p-4">
              {error && (
                <div className="mb-4 rounded-[18px] border border-[rgba(248,113,113,0.18)] bg-[var(--lt-red-dim)] px-4 py-3 text-sm text-[#fca5a5]">
                  {error}
                </div>
              )}
              {leads.length === 0 ? (
                <p className="py-8 text-center text-[var(--lt-text-muted)]">
                  No qualified leads available. Qualify leads first.
                </p>
              ) : (
                <>
                  <div className="mb-3 flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === leads.length && leads.length > 0}
                      onChange={toggleAll}
                      className="rounded border-[var(--lt-line)] bg-[var(--lt-surface)]"
                    />
                    <span className="text-sm text-[var(--lt-text-muted)]">
                      Select all ({leads.length})
                    </span>
                  </div>
                  <div className="space-y-1">
                    {leads.map((lead: any) => (
                      <ProductCard
                        key={lead.lead_id}
                        as="label"
                        className="cursor-pointer rounded-[16px] p-0"
                        bodyClassName="px-4 py-3"
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(lead.lead_id)}
                            onChange={() => toggleLead(lead.lead_id)}
                            className="rounded border-[var(--lt-line)] bg-[var(--lt-surface)]"
                          />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-[var(--lt-text)]">
                              {lead.owner_name || "Unknown"}
                            </p>
                            <p className="text-xs text-[var(--lt-text-muted)]">
                              {lead.case_number} - {lead.county_name}
                            </p>
                          </div>
                          <MonoCell tone="emerald">{formatCurrency(lead.surplus_amount)}</MonoCell>
                        </div>
                      </ProductCard>
                    ))}
                  </div>
                </>
              )}
            </div>
            <div className="px-6 py-4 border-t border-[var(--lt-line)] flex items-center justify-between">
              <span className="text-sm text-[var(--lt-text-muted)]">
                {selectedIds.size} selected
              </span>
              <button
                onClick={handleGenerate}
                disabled={selectedIds.size === 0}
                className="rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)] disabled:opacity-50"
              >
                Generate {selectedIds.size} Letters
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
