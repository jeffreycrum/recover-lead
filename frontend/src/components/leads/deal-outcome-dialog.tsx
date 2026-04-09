import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X, DollarSign, XCircle, Loader2 } from "lucide-react";

const CLOSED_REASONS = [
  { value: "recovered", label: "Funds Recovered" },
  { value: "declined", label: "Owner Declined" },
  { value: "unreachable", label: "Owner Unreachable" },
  { value: "expired", label: "Claim Expired" },
  { value: "other", label: "Other" },
];

interface DealOutcomeDialogProps {
  leadId: string;
  currentStatus: string;
  onClose: () => void;
}

export function DealOutcomeDialog({ leadId, currentStatus, onClose }: DealOutcomeDialogProps) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<"pay" | "close" | null>(null);

  // Pay form state
  const [outcomeAmount, setOutcomeAmount] = useState("");
  const [feePercentage, setFeePercentage] = useState("33");
  const [payNotes, setPayNotes] = useState("");

  // Close form state
  const [closedReason, setClosedReason] = useState("declined");
  const [closeNotes, setCloseNotes] = useState("");

  const payMutation = useMutation({
    mutationFn: () =>
      api.payLead(leadId, {
        outcome_amount: parseFloat(outcomeAmount),
        fee_percentage: parseFloat(feePercentage),
        notes: payNotes || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leads"] });
      qc.invalidateQueries({ queryKey: ["activities", leadId] });
      onClose();
    },
  });

  const closeMutation = useMutation({
    mutationFn: () =>
      api.closeLead(leadId, {
        closed_reason: closedReason,
        notes: closeNotes || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leads"] });
      qc.invalidateQueries({ queryKey: ["activities", leadId] });
      onClose();
    },
  });

  const feeAmount =
    outcomeAmount && feePercentage
      ? (parseFloat(outcomeAmount) * parseFloat(feePercentage)) / 100
      : 0;

  return (
    <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">
            {mode === "pay" ? "Mark as Paid" : mode === "close" ? "Close Deal" : "Deal Outcome"}
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
            <X size={20} />
          </button>
        </div>

        <div className="p-6">
          {!mode ? (
            <div className="space-y-3">
              {currentStatus === "filed" && (
                <button
                  onClick={() => setMode("pay")}
                  className="w-full flex items-center gap-3 p-4 border rounded-lg hover:bg-gray-50 text-left"
                >
                  <DollarSign className="text-emerald" size={20} />
                  <div>
                    <p className="font-medium">Mark as Paid</p>
                    <p className="text-sm text-muted-foreground">Record the recovery amount and your fee</p>
                  </div>
                </button>
              )}
              <button
                onClick={() => setMode("close")}
                className="w-full flex items-center gap-3 p-4 border rounded-lg hover:bg-gray-50 text-left"
              >
                <XCircle className="text-gray-500" size={20} />
                <div>
                  <p className="font-medium">Close Without Recovery</p>
                  <p className="text-sm text-muted-foreground">Mark this deal as closed with a reason</p>
                </div>
              </button>
            </div>
          ) : mode === "pay" ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Recovery Amount ($)</label>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={outcomeAmount}
                  onChange={(e) => setOutcomeAmount(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  placeholder="25000.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Fee Percentage (%)</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.5"
                  value={feePercentage}
                  onChange={(e) => setFeePercentage(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                />
              </div>
              {feeAmount > 0 && (
                <div className="p-3 bg-emerald/5 rounded-md border border-emerald/20">
                  <p className="text-sm">
                    Your fee: <span className="font-semibold text-emerald">${feeAmount.toFixed(2)}</span>
                  </p>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium mb-1">Notes (optional)</label>
                <textarea
                  value={payNotes}
                  onChange={(e) => setPayNotes(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  rows={2}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => setMode(null)}
                  className="px-4 py-2 border rounded-md text-sm hover:bg-gray-50"
                >
                  Back
                </button>
                <button
                  onClick={() => payMutation.mutate()}
                  disabled={!outcomeAmount || parseFloat(outcomeAmount) <= 0 || payMutation.isPending}
                  className="flex-1 px-4 py-2 bg-emerald text-white rounded-md text-sm hover:bg-emerald/90 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {payMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                  Confirm Payment
                </button>
              </div>
              {payMutation.isError && (
                <p className="text-xs text-red-600">
                  {(payMutation.error as any)?.message || "Failed to record payment"}
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Reason</label>
                <select
                  value={closedReason}
                  onChange={(e) => setClosedReason(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                >
                  {CLOSED_REASONS.filter((r) =>
                    currentStatus === "paid" ? r.value === "recovered" : r.value !== "recovered"
                  ).map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Notes (optional)</label>
                <textarea
                  value={closeNotes}
                  onChange={(e) => setCloseNotes(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  rows={2}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => setMode(null)}
                  className="px-4 py-2 border rounded-md text-sm hover:bg-gray-50"
                >
                  Back
                </button>
                <button
                  onClick={() => closeMutation.mutate()}
                  disabled={closeMutation.isPending}
                  className="flex-1 px-4 py-2 bg-gray-800 text-white rounded-md text-sm hover:bg-gray-700 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {closeMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                  Close Deal
                </button>
              </div>
              {closeMutation.isError && (
                <p className="text-xs text-red-600">
                  {(closeMutation.error as any)?.message || "Failed to close deal"}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
