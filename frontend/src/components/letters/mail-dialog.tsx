import { useEffect, useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useQueryClient } from "@tanstack/react-query";
import { api, type MailLetterData } from "@/lib/api";
import { X, Send, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { StatusPill } from "@/components/landing-chrome";

interface MailDialogProps {
  open: boolean;
  onClose: () => void;
  letter: {
    id: string;
    case_number?: string | null;
    owner_name?: string | null;
  } | null;
}

const EMPTY_FORM: MailLetterData = {
  from_name: "",
  from_street1: "",
  from_street2: "",
  from_city: "",
  from_state: "",
  from_zip: "",
  to_name: "",
  to_street1: "",
  to_street2: "",
  to_city: "",
  to_state: "",
  to_zip: "",
};

export function MailDialog({ open, onClose, letter }: MailDialogProps) {
  const { getToken } = useAuth();
  const qc = useQueryClient();

  const [form, setForm] = useState<MailLetterData>(EMPTY_FORM);
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<{
    task_id: string;
    message: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);

  useEffect(() => {
    if (open && letter) {
      setForm((prev) => ({
        ...prev,
        to_name: letter.owner_name || prev.to_name,
      }));
      setConfirmed(false);
      setDone(null);
      setError(null);
    }
  }, [open, letter]);

  if (!open || !letter) return null;

  const update = (key: keyof MailLetterData, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const requiredFilled = (): boolean => {
    const required: (keyof MailLetterData)[] = [
      "from_name",
      "from_street1",
      "from_city",
      "from_state",
      "from_zip",
      "to_name",
      "to_street1",
      "to_city",
      "to_state",
      "to_zip",
    ];
    return required.every((k) => (form[k] ?? "").trim().length > 0);
  };

  const canSubmit = confirmed && requiredFilled() && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.mailLetter(letter.id, form);
      setDone({ task_id: result.task_id, message: result.message });
      qc.invalidateQueries({ queryKey: ["letters"] });
    } catch {
      setError("Failed to queue letter for mailing. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="mail-dialog-title"
        className="w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-[24px] border border-[var(--lt-line-2)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] shadow-[0_40px_120px_-40px_rgba(0,0,0,0.9)] flex flex-col"
      >
        <div className="px-6 py-4 border-b border-[var(--lt-line)] flex items-center justify-between">
          <div>
            <h3 id="mail-dialog-title" className="font-semibold flex items-center gap-2 text-[var(--lt-text)]">
              <Send size={18} />
              Mail Letter via Lob {letter.case_number ? `— Case #${letter.case_number}` : ""}
            </h3>
            <div className="mt-2">
              <StatusPill status="queued" label="Physical mail" />
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded-full border border-transparent p-1.5 text-[var(--lt-text-muted)] transition-colors hover:border-[var(--lt-line)] hover:bg-[var(--lt-surface-2)] hover:text-[var(--lt-text)]"
          >
            <X size={18} />
          </button>
        </div>

        {done ? (
          <div className="p-8 text-center">
            <CheckCircle size={48} className="text-emerald mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--lt-text)]">Letter queued for mailing</h3>
            <p className="mt-1 text-sm text-[var(--lt-text-muted)]">{done.message}</p>
            <p className="mt-2 text-xs text-[var(--lt-text-muted)]">
              Task ID: <span className="font-mono">{done.task_id}</span>
            </p>
            <p className="mt-2 text-xs text-[var(--lt-text-muted)]">
              Tracking URL will appear on the letter after the mailing provider confirms the send.
            </p>
            <button
              onClick={onClose}
              className="mt-6 rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)]"
            >
              Close
            </button>
          </div>
        ) : submitting ? (
          <div className="p-8 text-center">
            <Loader2 size={48} className="animate-spin text-emerald mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--lt-text)]">Queueing letter...</h3>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-auto p-6 space-y-6">
              <div className="rounded-[18px] border border-[rgba(245,158,11,0.16)] bg-[var(--lt-amber-dim)] p-4 text-sm text-[#fcd34d] flex items-start gap-2">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                <div>
                  Lob charges ~<strong>$1.00 per letter</strong> (4-page double-sided, first-class).
                  Counts against your plan&apos;s monthly mailing quota.
                </div>
              </div>

              <section>
                <h4 className="mb-3 text-sm font-medium text-[var(--lt-text)]">From (Return Address)</h4>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <FormField
                    label="Name"
                    value={form.from_name}
                    onChange={(v) => update("from_name", v)}
                  />
                  <FormField
                    label="Street"
                    value={form.from_street1}
                    onChange={(v) => update("from_street1", v)}
                  />
                  <FormField
                    label="Unit / Apt (optional)"
                    value={form.from_street2 ?? ""}
                    onChange={(v) => update("from_street2", v)}
                  />
                  <FormField
                    label="City"
                    value={form.from_city}
                    onChange={(v) => update("from_city", v)}
                  />
                  <FormField
                    label="State (2-letter)"
                    value={form.from_state}
                    onChange={(v) => update("from_state", v.toUpperCase().slice(0, 2))}
                  />
                  <FormField
                    label="ZIP"
                    value={form.from_zip}
                    onChange={(v) => update("from_zip", v)}
                  />
                </div>
              </section>

              <section>
                <h4 className="mb-3 text-sm font-medium text-[var(--lt-text)]">To (Recipient)</h4>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <FormField
                    label="Name"
                    value={form.to_name}
                    onChange={(v) => update("to_name", v)}
                  />
                  <FormField
                    label="Street"
                    value={form.to_street1}
                    onChange={(v) => update("to_street1", v)}
                  />
                  <FormField
                    label="Unit / Apt (optional)"
                    value={form.to_street2 ?? ""}
                    onChange={(v) => update("to_street2", v)}
                  />
                  <FormField
                    label="City"
                    value={form.to_city}
                    onChange={(v) => update("to_city", v)}
                  />
                  <FormField
                    label="State (2-letter)"
                    value={form.to_state}
                    onChange={(v) => update("to_state", v.toUpperCase().slice(0, 2))}
                  />
                  <FormField
                    label="ZIP"
                    value={form.to_zip}
                    onChange={(v) => update("to_zip", v)}
                  />
                </div>
              </section>

              {error && (
                <div className="rounded-[18px] border border-[rgba(248,113,113,0.18)] bg-[var(--lt-red-dim)] p-3 text-sm text-[#fca5a5]">
                  {error}
                </div>
              )}

              <label className="flex items-start gap-2 text-sm cursor-pointer text-[var(--lt-text-muted)]">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  className="mt-0.5 rounded border-[var(--lt-line)] bg-[var(--lt-surface)]"
                />
                <span>I understand this will physically mail this letter via USPS.</span>
              </label>
            </div>

            <div className="px-6 py-4 border-t border-[var(--lt-line)] flex justify-end gap-2">
              <button
                onClick={onClose}
                className="rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm font-medium text-[var(--lt-text)] transition-colors hover:bg-[var(--lt-surface-2)]"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="inline-flex items-center gap-2 rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)] disabled:opacity-50"
              >
                <Send size={14} />
                Mail Letter
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

interface FormFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

function FormField({ label, value, onChange }: FormFieldProps) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs text-[var(--lt-text-dim)]">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-[14px] border border-[var(--lt-line)] bg-[rgba(7,11,21,0.75)] px-3 py-2 text-sm text-[var(--lt-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] focus:outline-none focus:ring-2 focus:ring-[rgba(16,185,129,0.3)]"
      />
    </label>
  );
}
