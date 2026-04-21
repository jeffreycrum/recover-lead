import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/common/empty-state";
import { formatDate } from "@/lib/utils";
import { FileSignature, Download, Check, Plus } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EyebrowTag, MonoCell, ProductCard, StatusPill } from "@/components/landing-chrome";

const NEXT_STATUS: Record<string, string | null> = {
  draft: "approved",
  approved: "signed",
  signed: null,
};

const NEXT_STATUS_LABEL: Record<string, string> = {
  approved: "Approve",
  signed: "Mark Signed",
};

const primaryButtonClass =
  "inline-flex items-center justify-center rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)] disabled:opacity-50";
const secondaryButtonClass =
  "inline-flex items-center justify-center rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm font-medium text-[var(--lt-text)] transition-colors hover:bg-[var(--lt-surface-2)] disabled:opacity-50";
const ghostButtonClass =
  "inline-flex items-center justify-center rounded-full border border-transparent px-3 py-1.5 text-xs font-medium text-[var(--lt-text-muted)] transition-colors hover:border-[var(--lt-line)] hover:bg-[var(--lt-surface-2)] hover:text-[var(--lt-text)] disabled:opacity-50";
const inputClass =
  "border-[var(--lt-line)] bg-[rgba(7,11,21,0.75)] text-[var(--lt-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]";

interface GenerateFormState {
  lead_id: string;
  fee_percentage: string;
  agent_name: string;
  contract_type: string;
}

export function ContractsPage() {
  const { getToken } = useAuth();
  const qc = useQueryClient();

  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);

  const [selectedContract, setSelectedContract] = useState<any>(null);
  const [editContent, setEditContent] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [pendingGeneration, setPendingGeneration] = useState(false);
  const pendingTimeoutRef = useRef<number | null>(null);
  const [showGenDialog, setShowGenDialog] = useState(false);
  const [genForm, setGenForm] = useState<GenerateFormState>({
    lead_id: "",
    fee_percentage: "25",
    agent_name: "",
    contract_type: "recovery_agreement",
  });
  const [genError, setGenError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [allContracts, setAllContracts] = useState<any[]>([]);
  const knownContractIdsRef = useRef<Set<string>>(new Set());

  const { data: page, isLoading } = useQuery({
    queryKey: ["contracts", cursor],
    queryFn: () => api.getContracts(cursor ? { cursor } : {}),
    refetchInterval: pendingGeneration ? 4000 : false,
  });

  useEffect(() => {
    if (!page) return;
    if (cursor === null) {
      setAllContracts(page.items);
    } else {
      setAllContracts((prev) => [...prev, ...page.items]);
    }
  }, [page, cursor]);

  useEffect(() => {
    if (!pendingGeneration || !page) return;
    const hasNewContract = page.items.some(
      (contract: any) => !knownContractIdsRef.current.has(contract.id)
    );
    if (hasNewContract) {
      setPendingGeneration(false);
      if (pendingTimeoutRef.current !== null) {
        window.clearTimeout(pendingTimeoutRef.current);
        pendingTimeoutRef.current = null;
      }
    }
  }, [page, pendingGeneration]);

  useEffect(() => {
    return () => {
      if (pendingTimeoutRef.current !== null) {
        window.clearTimeout(pendingTimeoutRef.current);
      }
    };
  }, []);

  const generateMutation = useMutation({
    mutationFn: (data: any) => api.generateContract(data),
    onSuccess: () => {
      setShowGenDialog(false);
      setGenForm({
        lead_id: "",
        fee_percentage: "25",
        agent_name: "",
        contract_type: "recovery_agreement",
      });
      setGenError(null);
      knownContractIdsRef.current = new Set(allContracts.map((contract: any) => contract.id));
      setPendingGeneration(true);
      setCursor(null);
      setAllContracts([]);
      qc.invalidateQueries({ queryKey: ["contracts"] });
      pendingTimeoutRef.current = window.setTimeout(() => setPendingGeneration(false), 60_000);
    },
    onError: (err: any) => {
      setGenError(err?.message || "Failed to queue contract generation");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.updateContract(id, data),
    onSuccess: () => {
      setCursor(null);
      setAllContracts([]);
      setSelectedContract(null);
      qc.invalidateQueries({ queryKey: ["contracts"] });
    },
  });

  const handleOpenEdit = async (contract: any) => {
    setEditLoading(true);
    setEditError(null);
    try {
      const detail = await api.getContract(contract.id);
      setSelectedContract(detail);
      setEditContent(detail.content);
    } catch {
      setEditError("Failed to load contract. Please try again.");
    } finally {
      setEditLoading(false);
    }
  };

  const handleSaveEdit = () => {
    if (!selectedContract) return;
    updateMutation.mutate({ id: selectedContract.id, data: { content: editContent } });
  };

  const handleAdvanceStatus = (contract: any) => {
    const next = NEXT_STATUS[contract.status];
    if (!next) return;
    updateMutation.mutate({ id: contract.id, data: { status: next } });
  };

  const handleDownloadPdf = async (id: string) => {
    const blob = await api.downloadContractPdf(id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `contract-${id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleGenerate = () => {
    setGenError(null);
    const feeNum = parseFloat(genForm.fee_percentage);
    if (!genForm.lead_id.trim()) return setGenError("Lead ID is required");
    if (isNaN(feeNum) || feeNum < 0 || feeNum > 100) return setGenError("Fee must be 0–100");
    if (!genForm.agent_name.trim()) return setGenError("Agent name is required");

    generateMutation.mutate({
      lead_id: genForm.lead_id.trim(),
      contract_type: genForm.contract_type,
      fee_percentage: feeNum,
      agent_name: genForm.agent_name.trim(),
    });
  };

  const handleGenDialogChange = (open: boolean) => {
    setShowGenDialog(open);
    if (!open) {
      setGenError(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <EyebrowTag>Recovery agreements</EyebrowTag>
          <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-[var(--lt-text)]">
            Contracts
          </h1>
          <p className="mt-2 text-[var(--lt-text-muted)]">
            Generate and manage surplus funds recovery agreements
          </p>
        </div>
        <button onClick={() => setShowGenDialog(true)} className={`${primaryButtonClass} gap-2`}>
          <Plus size={16} />
          Generate Contract
        </button>
      </div>

      {pendingGeneration && (
        <div className="rounded-[18px] border border-[rgba(59,130,246,0.18)] bg-[var(--lt-blue-dim)] px-4 py-3 text-sm text-[#bfdbfe]">
          Contract generation in progress — the new draft will appear shortly.
        </div>
      )}
      {editError && (
        <div className="rounded-[18px] border border-[rgba(248,113,113,0.18)] bg-[var(--lt-red-dim)] px-4 py-3 text-sm text-[#fca5a5]">
          {editError}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-[18px] bg-[rgba(255,255,255,0.04)]" />
          ))}
        </div>
      ) : allContracts.length === 0 && !isLoading ? (
        <ProductCard bodyClassName="py-10">
          <EmptyState
            icon={<FileSignature size={48} />}
            title="No contracts yet"
            description="Generate a recovery agreement for a claimed lead to get started."
            className="text-[var(--lt-text)]"
            action={
              <button onClick={() => setShowGenDialog(true)} className={primaryButtonClass}>
                Generate Contract
              </button>
            }
          />
        </ProductCard>
      ) : (
        <ProductCard heading="Recovery agreements" subtitle={`${allContracts.length} records`} showDots bodyClassName="px-0 pb-0 pt-4">
          <div className="overflow-x-auto">
            <table className="min-w-[980px] w-full text-sm">
              <thead>
                <tr className="border-y border-[var(--lt-line)] bg-[var(--lt-bg-2)]">
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">County / Case</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Owner</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Surplus</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Fee %</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {allContracts.map((contract: any) => {
                  const nextStatus = NEXT_STATUS[contract.status];
                  return (
                    <tr
                      key={contract.id}
                      className="border-b border-[var(--lt-line)] transition-colors hover:bg-[var(--lt-emerald-dim)]"
                    >
                      <td className="px-4 py-3.5">
                        <div className="font-medium text-[var(--lt-text)]">{contract.county_name}</div>
                        <div className="text-xs text-[var(--lt-text-muted)]">{contract.case_number}</div>
                      </td>
                      <td className="px-4 py-3.5 text-[var(--lt-text-muted)]">
                        {contract.owner_name || "—"}
                      </td>
                      <td className="px-4 py-3.5">
                        <MonoCell tone="emerald">
                          ${parseFloat(contract.surplus_amount).toLocaleString()}
                        </MonoCell>
                      </td>
                      <td className="px-4 py-3.5 text-[var(--lt-text-muted)]">
                        {contract.fee_percentage != null ? `${contract.fee_percentage}%` : "—"}
                      </td>
                      <td className="px-4 py-3.5">
                        <StatusPill status={contract.status} />
                      </td>
                      <td className="px-4 py-3.5">
                        <MonoCell size="sm" tone="muted">{formatDate(contract.created_at)}</MonoCell>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center justify-end gap-1.5">
                          {contract.status === "draft" && (
                            <button
                              onClick={() => handleOpenEdit(contract)}
                              disabled={editLoading}
                              className={ghostButtonClass}
                            >
                              {editLoading ? "Loading…" : "Edit"}
                            </button>
                          )}
                          {nextStatus && (
                            <button
                              onClick={() => handleAdvanceStatus(contract)}
                              className={`${ghostButtonClass} text-[var(--lt-emerald)] hover:text-[var(--lt-emerald-light)]`}
                            >
                              <Check size={14} className="mr-1" />
                              {NEXT_STATUS_LABEL[nextStatus]}
                            </button>
                          )}
                          <button
                            onClick={() => handleDownloadPdf(contract.id)}
                            className={ghostButtonClass}
                            title="Download PDF"
                          >
                            <Download size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {page?.has_more && (
            <div className="flex justify-center border-t border-[var(--lt-line)] py-3">
              <button
                onClick={() => setCursor(page.next_cursor)}
                disabled={isLoading}
                className={secondaryButtonClass}
              >
                {isLoading ? "Loading…" : "Load more"}
              </button>
            </div>
          )}
        </ProductCard>
      )}

      <Dialog open={showGenDialog} onOpenChange={handleGenDialogChange}>
        <DialogContent className="max-w-md border-[var(--lt-line-2)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] text-[var(--lt-text)]">
          <DialogHeader>
            <DialogTitle>Generate Recovery Agreement</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <p className="text-sm text-[var(--lt-text-muted)]">
              Claude will fill the narrative clauses based on the lead data. Review and approve
              before sending.
            </p>
            <div className="space-y-2">
              <Label htmlFor="lead-id">Lead ID</Label>
              <Input
                id="lead-id"
                placeholder="Paste the lead UUID"
                value={genForm.lead_id}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setGenForm((form) => ({ ...form, lead_id: e.target.value }))
                }
                className={inputClass}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent-name">Your Name (Agent)</Label>
              <Input
                id="agent-name"
                placeholder="Full legal name"
                value={genForm.agent_name}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setGenForm((form) => ({ ...form, agent_name: e.target.value }))
                }
                className={inputClass}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fee-pct">Contingency Fee (%)</Label>
              <Input
                id="fee-pct"
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={genForm.fee_percentage}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setGenForm((form) => ({ ...form, fee_percentage: e.target.value }))
                }
                className={inputClass}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contract-type">Contract Type</Label>
              <Select
                value={genForm.contract_type}
                onValueChange={(value) =>
                  setGenForm((form) => ({
                    ...form,
                    contract_type: value ?? form.contract_type,
                  }))
                }
              >
                <SelectTrigger id="contract-type" className="border-[var(--lt-line)] bg-[rgba(7,11,21,0.75)] text-[var(--lt-text)]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border border-[var(--lt-line)] bg-[var(--lt-surface)] text-[var(--lt-text)]">
                  <SelectItem value="recovery_agreement">FL Recovery Agreement</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {genError && <p className="text-sm text-[#fca5a5]">{genError}</p>}
            <div className="rounded-[18px] border border-[rgba(245,158,11,0.16)] bg-[var(--lt-amber-dim)] p-3 text-xs text-[#fcd34d]">
              Review all contract content carefully before approving. This is not legal advice.
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => handleGenDialogChange(false)} className={secondaryButtonClass}>
                Cancel
              </button>
              <button onClick={handleGenerate} disabled={generateMutation.isPending} className={primaryButtonClass}>
                {generateMutation.isPending ? "Queuing…" : "Generate"}
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {selectedContract && (
        <Dialog open onOpenChange={() => setSelectedContract(null)}>
          <DialogContent className="max-w-2xl border-[var(--lt-line-2)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] text-[var(--lt-text)]">
            <DialogHeader>
              <DialogTitle>Edit Contract — {selectedContract.case_number}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div className="rounded-[18px] border border-[rgba(245,158,11,0.16)] bg-[var(--lt-amber-dim)] p-3 text-xs text-[#fcd34d]">
                Review all content carefully before approving. This is not legal advice.
              </div>
              <Textarea
                value={editContent}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setEditContent(e.target.value)}
                className="min-h-[400px] border-[var(--lt-line)] bg-[rgba(7,11,21,0.75)] font-mono text-xs text-[var(--lt-text)]"
              />
              <div className="flex justify-end gap-2">
                <button onClick={() => setSelectedContract(null)} className={secondaryButtonClass}>
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={updateMutation.isPending}
                  className={secondaryButtonClass}
                >
                  Save Changes
                </button>
                <button
                  onClick={() => handleAdvanceStatus(selectedContract)}
                  disabled={updateMutation.isPending}
                  className={primaryButtonClass}
                >
                  <Check size={16} className="mr-1" />
                  Approve
                </button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
