import { useEffect, useState, type ChangeEvent } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Mode = "address" | "name_only" | "parcel";

interface SkipTraceAddressDialogProps {
  open: boolean;
  lead: {
    property_address?: string | null;
    property_city?: string | null;
    property_state?: string | null;
    property_zip?: string | null;
    parcel_id?: string | null;
    owner_name?: string | null;
  };
  onClose: () => void;
  onSubmit: (payload: {
    street?: string;
    city?: string;
    state?: string;
    zip_code?: string;
    parcel_number?: string;
    name_only: boolean;
  }) => void;
  isSubmitting?: boolean;
}

const primaryButtonClass =
  "inline-flex items-center justify-center rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)] disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass =
  "inline-flex items-center justify-center rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm font-medium text-[var(--lt-text)] transition-colors hover:bg-[var(--lt-surface-2)] disabled:opacity-50";
const inputClass =
  "border-[var(--lt-line)] bg-[rgba(7,11,21,0.75)] text-[var(--lt-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]";

/** Mirrors the backend's ADDRESS_INCOMPLETE rule (leads.py). */
export function isAddressComplete(fields: {
  street?: string | null;
  city?: string | null;
  state?: string | null;
  zip_code?: string | null;
}): boolean {
  const street = (fields.street || "").trim();
  const city = (fields.city || "").trim();
  const state = (fields.state || "").trim();
  const zip = (fields.zip_code || "").trim();
  if (street.length < 3) return false;
  if (/^SITUS\s*NA\b/i.test(street)) return false;
  const hasCityState = city.length > 0 && state.length > 0;
  const hasZip = zip.length >= 5;
  return hasCityState || hasZip;
}

export function SkipTraceAddressDialog({
  open,
  lead,
  onClose,
  onSubmit,
  isSubmitting,
}: SkipTraceAddressDialogProps) {
  const [mode, setMode] = useState<Mode>("address");
  const [street, setStreet] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zip, setZip] = useState("");
  const [parcel, setParcel] = useState("");

  // Re-seed whenever the dialog opens against a different lead so a
  // second attempt doesn't inherit stale values.
  useEffect(() => {
    if (!open) return;
    setMode("address");
    setStreet((lead.property_address || "").trim());
    setCity((lead.property_city || "").trim());
    setState((lead.property_state || "").trim().toUpperCase());
    setZip((lead.property_zip || "").trim());
    setParcel((lead.parcel_id || "").trim());
  }, [open, lead]);

  const addressValid = isAddressComplete({ street, city, state, zip_code: zip });
  const hasOwnerName = !!(lead.owner_name && lead.owner_name.trim().length > 0);
  const parcelValid = parcel.trim().length >= 3;
  const canSubmit =
    !isSubmitting &&
    (mode === "address"
      ? addressValid
      : mode === "parcel"
      ? parcelValid && hasOwnerName
      : hasOwnerName);

  const handleSubmit = () => {
    if (!canSubmit) return;
    if (mode === "name_only") {
      onSubmit({ name_only: true });
      return;
    }
    if (mode === "parcel") {
      onSubmit({ parcel_number: parcel.trim(), name_only: false });
      return;
    }
    onSubmit({
      street: street.trim(),
      city: city.trim(),
      state: state.trim().toUpperCase(),
      zip_code: zip.trim(),
      name_only: false,
    });
  };

  const ownerLabel = lead.owner_name || "this lead";

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md border-[var(--lt-line-2)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] text-[var(--lt-text)]">
        <DialogHeader>
          <DialogTitle>Run Skip Trace</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="inline-flex rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] p-1">
            {(
              [
                ["address", "By address"],
                ["parcel", "By parcel"],
                ["name_only", "By name only"],
              ] as const
            ).map(([val, label]) => (
              <button
                key={val}
                type="button"
                onClick={() => setMode(val)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  mode === val
                    ? "bg-[var(--lt-emerald)] text-[#042014]"
                    : "text-[var(--lt-text-muted)] hover:text-[var(--lt-text)]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {mode === "address" ? (
            <>
              <p className="text-sm text-[var(--lt-text-muted)]">
                Skip trace needs a complete mailing address to find contacts for{" "}
                <span className="font-medium text-[var(--lt-text)]">{ownerLabel}</span>. We
                pre-filled what the county had — fill in the missing parts (city + state OR zip).
              </p>
              <div className="space-y-2">
                <Label htmlFor="st-street">Street</Label>
                <Input
                  id="st-street"
                  value={street}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setStreet(e.target.value)}
                  placeholder="29432 Silverado Canyon Rd"
                  className={inputClass}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="st-city">City</Label>
                  <Input
                    id="st-city"
                    value={city}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setCity(e.target.value)}
                    placeholder="Silverado"
                    className={inputClass}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="st-state">State</Label>
                  <Input
                    id="st-state"
                    value={state}
                    maxLength={2}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      setState(e.target.value.toUpperCase())
                    }
                    placeholder="CA"
                    className={inputClass}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="st-zip">Zip code</Label>
                <Input
                  id="st-zip"
                  value={zip}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setZip(e.target.value)}
                  placeholder="92676"
                  className={inputClass}
                />
              </div>
              <p className="text-xs text-[var(--lt-text-dim)]">
                Provide either (city + state) OR a 5-digit zip — either combination is enough.
              </p>
            </>
          ) : mode === "parcel" ? (
            <div className="space-y-3">
              <p className="text-sm text-[var(--lt-text-muted)]">
                Look up by parcel / APN. Prefilled from the county data when available — edit if
                yours is formatted differently.
              </p>
              <div className="space-y-2">
                <Label htmlFor="st-parcel">Parcel / APN</Label>
                <Input
                  id="st-parcel"
                  value={parcel}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setParcel(e.target.value)}
                  placeholder="105-131-04-00-0000"
                  className={inputClass}
                />
              </div>
              <div className="rounded-[14px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.02)] px-3 py-2 text-sm">
                <span className="text-[var(--lt-text-dim)]">Owner: </span>
                <span className="font-medium text-[var(--lt-text)]">
                  {lead.owner_name || "(unknown)"}
                </span>
              </div>
              <p className="text-xs text-[var(--lt-text-dim)]">
                Current provider (SkipSherpa) doesn't match by parcel natively — this mode records
                the parcel with the lookup and currently runs a name-based match. A parcel-aware
                provider will be wired in separately.
              </p>
              {!hasOwnerName && (
                <p className="text-xs text-[#fca5a5]">
                  No owner name on file — parcel lookup can't run without a name to match.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-[var(--lt-text-muted)]">
                Search for contacts by owner name only. Useful for leads with no property address
                (common in FL counties). Expect more false positives than an address lookup.
              </p>
              <div className="rounded-[14px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.02)] px-3 py-2 text-sm">
                <span className="text-[var(--lt-text-dim)]">Owner: </span>
                <span className="font-medium text-[var(--lt-text)]">
                  {lead.owner_name || "(unknown)"}
                </span>
              </div>
              {!hasOwnerName && (
                <p className="text-xs text-[#fca5a5]">
                  No owner name on file — name-only lookup can't run.
                </p>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button onClick={onClose} className={secondaryButtonClass} disabled={isSubmitting}>
              Cancel
            </button>
            <button onClick={handleSubmit} className={primaryButtonClass} disabled={!canSubmit}>
              {isSubmitting ? "Running…" : "Run Skip Trace"}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
