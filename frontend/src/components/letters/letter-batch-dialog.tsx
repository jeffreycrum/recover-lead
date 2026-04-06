import { useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { useMyLeads } from "@/hooks/use-leads";
import { useQueryClient } from "@tanstack/react-query";
import { formatCurrency } from "@/lib/utils";
import { X, FileText, Loader2, CheckCircle } from "lucide-react";

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

  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);

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
    } catch {
      setDone(true);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2">
            <FileText size={18} />
            Batch Generate Letters
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
            <X size={18} />
          </button>
        </div>

        {done ? (
          <div className="p-8 text-center">
            <CheckCircle size={48} className="text-emerald mx-auto mb-4" />
            <h3 className="text-lg font-medium">Letters generated!</h3>
            <p className="text-sm text-muted-foreground mt-1">
              {selectedIds.size} letters have been created as drafts.
            </p>
            <button
              onClick={onClose}
              className="mt-4 px-4 py-2 bg-emerald text-white rounded-md hover:bg-emerald/90 text-sm"
            >
              View Letters
            </button>
          </div>
        ) : generating ? (
          <div className="p-8 text-center">
            <Loader2 size={48} className="animate-spin text-emerald mx-auto mb-4" />
            <h3 className="text-lg font-medium">Generating {selectedIds.size} letters...</h3>
            <p className="text-sm text-muted-foreground mt-1">
              This may take a minute.
            </p>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-auto p-4">
              {leads.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  No qualified leads available. Qualify leads first.
                </p>
              ) : (
                <>
                  <div className="flex items-center gap-2 mb-3">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === leads.length && leads.length > 0}
                      onChange={toggleAll}
                      className="rounded"
                    />
                    <span className="text-sm text-muted-foreground">
                      Select all ({leads.length})
                    </span>
                  </div>
                  <div className="space-y-1">
                    {leads.map((lead: any) => (
                      <label
                        key={lead.lead_id}
                        className="flex items-center gap-3 p-2 rounded hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.has(lead.lead_id)}
                          onChange={() => toggleLead(lead.lead_id)}
                          className="rounded"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {lead.owner_name || "Unknown"}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {lead.case_number} — {lead.county_name}
                          </p>
                        </div>
                        <span className="text-sm font-medium text-emerald">
                          {formatCurrency(lead.surplus_amount)}
                        </span>
                      </label>
                    ))}
                  </div>
                </>
              )}
            </div>
            <div className="px-6 py-4 border-t flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                {selectedIds.size} selected
              </span>
              <button
                onClick={handleGenerate}
                disabled={selectedIds.size === 0}
                className="px-4 py-2 bg-emerald text-white rounded-md hover:bg-emerald/90 disabled:opacity-50 text-sm font-medium"
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
