import { useEffect, useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useQueryClient } from "@tanstack/react-query";
import { api, type MailLetterData } from "@/lib/api";
import { X, Send, Loader2, CheckCircle, AlertCircle } from "lucide-react";

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
    } catch (e: unknown) {
      const err = e as { message?: string; code?: string };
      setError(err?.message || "Failed to queue letter for mailing");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2">
            <Send size={18} />
            Mail Letter via Lob {letter.case_number ? `— Case #${letter.case_number}` : ""}
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
            <X size={18} />
          </button>
        </div>

        {done ? (
          <div className="p-8 text-center">
            <CheckCircle size={48} className="text-emerald mx-auto mb-4" />
            <h3 className="text-lg font-medium">Letter queued for mailing</h3>
            <p className="text-sm text-muted-foreground mt-1">{done.message}</p>
            <p className="text-xs text-muted-foreground mt-2">
              Task ID: <span className="font-mono">{done.task_id}</span>
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              Tracking URL will appear on the letter after the mailing provider confirms the send.
            </p>
            <button
              onClick={onClose}
              className="mt-6 px-4 py-2 bg-emerald text-white rounded-md hover:bg-emerald/90 text-sm"
            >
              Close
            </button>
          </div>
        ) : submitting ? (
          <div className="p-8 text-center">
            <Loader2 size={48} className="animate-spin text-emerald mx-auto mb-4" />
            <h3 className="text-lg font-medium">Queueing letter...</h3>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-auto p-6 space-y-6">
              <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900 flex items-start gap-2">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                <div>
                  Lob charges ~<strong>$1.00 per letter</strong> (4-page double-sided, first-class).
                  Counts against your plan&apos;s monthly mailing quota.
                </div>
              </div>

              <section>
                <h4 className="font-medium text-sm mb-3">From (Return Address)</h4>
                <div className="grid grid-cols-2 gap-3">
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
                <h4 className="font-medium text-sm mb-3">To (Recipient)</h4>
                <div className="grid grid-cols-2 gap-3">
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
                <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-900">
                  {error}
                </div>
              )}

              <label className="flex items-start gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  className="mt-0.5 rounded"
                />
                <span>I understand this will physically mail this letter via USPS.</span>
              </label>
            </div>

            <div className="px-6 py-4 border-t flex justify-end gap-2">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="px-4 py-2 bg-emerald text-white rounded-md hover:bg-emerald/90 disabled:opacity-50 text-sm font-medium flex items-center gap-2"
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
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald/50"
      />
    </label>
  );
}
