import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/common/empty-state";
import { formatDate } from "@/lib/utils";
import { FileSignature, Download, Check, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  approved: "bg-emerald-100 text-emerald-700",
  signed: "bg-blue-100 text-blue-700",
};

const NEXT_STATUS: Record<string, string | null> = {
  draft: "approved",
  approved: "signed",
  signed: null,
};

const NEXT_STATUS_LABEL: Record<string, string> = {
  approved: "Approve",
  signed: "Mark Signed",
};

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
  const pendingTimeoutRef = useRef<ReturnType<typeof window.setTimeout> | null>(null);
  const [showGenDialog, setShowGenDialog] = useState(false);
  const [genForm, setGenForm] = useState<GenerateFormState>({
    lead_id: "",
    fee_percentage: "25",
    agent_name: "",
    contract_type: "recovery_agreement",
  });
  const [genError, setGenError] = useState<string | null>(null);

  const prevContractCountRef = useRef<number>(0);

  const { data: contracts, isLoading } = useQuery({
    queryKey: ["contracts"],
    queryFn: () => api.getContracts(),
    // Poll while a Celery task is in flight so the new draft surfaces automatically
    refetchInterval: pendingGeneration ? 4000 : false,
  });

  // Clear pending indicator as soon as a new contract row appears
  useEffect(() => {
    if (!pendingGeneration || !contracts) return;
    if (contracts.length > prevContractCountRef.current) {
      setPendingGeneration(false);
      if (pendingTimeoutRef.current !== null) {
        window.clearTimeout(pendingTimeoutRef.current);
        pendingTimeoutRef.current = null;
      }
    }
    prevContractCountRef.current = contracts.length;
  }, [contracts, pendingGeneration]);

  // Cancel timeout on unmount
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
      setGenForm({ lead_id: "", fee_percentage: "25", agent_name: "", contract_type: "recovery_agreement" });
      setGenError(null);
      prevContractCountRef.current = contracts?.length ?? 0;
      setPendingGeneration(true);
      qc.invalidateQueries({ queryKey: ["contracts"] });
      // Fallback: stop polling after 60 s if the contract never appears
      pendingTimeoutRef.current = window.setTimeout(() => setPendingGeneration(false), 60_000);
    },
    onError: (err: any) => {
      setGenError(err?.message || "Failed to queue contract generation");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.updateContract(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contracts"] });
      setSelectedContract(null);
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Contracts</h1>
          <p className="text-muted-foreground">
            Generate and manage surplus funds recovery agreements
          </p>
        </div>
        <Button onClick={() => setShowGenDialog(true)} size="sm" className="gap-2">
          <Plus size={16} />
          Generate Contract
        </Button>
      </div>

      {pendingGeneration && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-200">
          Contract generation in progress — the new draft will appear shortly.
        </div>
      )}
      {editError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {editError}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      ) : !contracts || contracts.length === 0 ? (
        <EmptyState
          icon={<FileSignature size={48} />}
          title="No contracts yet"
          description="Generate a recovery agreement for a claimed lead to get started."
          action={
            <Button onClick={() => setShowGenDialog(true)}>Generate Contract</Button>
          }
        />
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th className="text-left px-4 py-3 font-medium">County / Case</th>
                <th className="text-left px-4 py-3 font-medium">Owner</th>
                <th className="text-left px-4 py-3 font-medium">Surplus</th>
                <th className="text-left px-4 py-3 font-medium">Fee %</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {contracts.map((contract: any) => {
                const nextStatus = NEXT_STATUS[contract.status];
                return (
                  <tr key={contract.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-medium">{contract.county_name}</div>
                      <div className="text-muted-foreground text-xs">{contract.case_number}</div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {contract.owner_name || "—"}
                    </td>
                    <td className="px-4 py-3">
                      ${parseFloat(contract.surplus_amount).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      {contract.fee_percentage != null ? `${contract.fee_percentage}%` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATUS_BADGE[contract.status] || "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {contract.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(contract.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        {contract.status === "draft" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenEdit(contract)}
                            disabled={editLoading}
                            className="h-8 px-2 text-xs"
                          >
                            {editLoading ? "Loading…" : "Edit"}
                          </Button>
                        )}
                        {nextStatus && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleAdvanceStatus(contract)}
                            className="h-8 px-2 text-xs text-emerald-700 hover:text-emerald-800"
                          >
                            <Check size={14} className="mr-1" />
                            {NEXT_STATUS_LABEL[nextStatus]}
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownloadPdf(contract.id)}
                          className="h-8 px-2"
                          title="Download PDF"
                        >
                          <Download size={14} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Generate Contract Dialog */}
      <Dialog open={showGenDialog} onOpenChange={setShowGenDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Generate Recovery Agreement</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <p className="text-sm text-muted-foreground">
              Claude will fill the narrative clauses based on the lead data. Review and approve
              before sending.
            </p>
            <div className="space-y-2">
              <Label htmlFor="lead-id">Lead ID</Label>
              <Input
                id="lead-id"
                placeholder="Paste the lead UUID"
                value={genForm.lead_id}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGenForm((f) => ({ ...f, lead_id: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent-name">Your Name (Agent)</Label>
              <Input
                id="agent-name"
                placeholder="Full legal name"
                value={genForm.agent_name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGenForm((f) => ({ ...f, agent_name: e.target.value }))}
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
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGenForm((f) => ({ ...f, fee_percentage: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contract-type">Contract Type</Label>
              <Select
                value={genForm.contract_type}
                onValueChange={(v: string) => setGenForm((f) => ({ ...f, contract_type: v }))}
              >
                <SelectTrigger id="contract-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recovery_agreement">FL Recovery Agreement</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {genError && (
              <p className="text-sm text-destructive">{genError}</p>
            )}
            <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800">
              Review all contract content carefully before approving. This is not legal advice.
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowGenDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleGenerate} disabled={generateMutation.isPending}>
                {generateMutation.isPending ? "Queuing…" : "Generate"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Contract Dialog */}
      {selectedContract && (
        <Dialog open onOpenChange={() => setSelectedContract(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Edit Contract — {selectedContract.case_number}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800">
                Review all content carefully before approving. This is not legal advice.
              </div>
              <Textarea
                value={editContent}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditContent(e.target.value)}
                className="font-mono text-xs min-h-[400px]"
              />
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setSelectedContract(null)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSaveEdit}
                  disabled={updateMutation.isPending}
                >
                  Save Changes
                </Button>
                <Button
                  onClick={() => {
                    handleAdvanceStatus(selectedContract);
                  }}
                  disabled={updateMutation.isPending}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <Check size={16} className="mr-1" />
                  Approve
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
