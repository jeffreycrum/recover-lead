import { useEffect, useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/common/empty-state";
import { formatDate } from "@/lib/utils";
import { FileText, Download, Trash2, Check, Plus, Send, RefreshCw } from "lucide-react";
import { LetterBatchDialog } from "@/components/letters/letter-batch-dialog";
import { MailDialog } from "@/components/letters/mail-dialog";
import { EyebrowTag, MonoCell, ProductCard, StatusPill } from "@/components/landing-chrome";

const primaryButtonClass =
  "inline-flex items-center gap-2 rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)] disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass =
  "inline-flex items-center gap-2 rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm font-medium text-[var(--lt-text)] transition-colors hover:bg-[var(--lt-surface-2)] disabled:cursor-not-allowed disabled:opacity-50";
const iconButtonClass =
  "rounded-full border border-transparent p-2 text-[var(--lt-text-muted)] transition-colors hover:border-[var(--lt-line)] hover:bg-[var(--lt-surface-2)] hover:text-[var(--lt-text)]";

export function LettersPage() {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  const [showBatchDialog, setShowBatchDialog] = useState(false);
  const [mailLetter, setMailLetter] = useState<{
    id: string;
    case_number?: string | null;
    owner_name?: string | null;
  } | null>(null);

  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);

  const [selectedLetter, setSelectedLetter] = useState<any>(null);
  const [editContent, setEditContent] = useState("");

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["letters"],
    queryFn: () => api.getLetters(),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });
  const lobEnabled = Boolean(me?.features?.lob_mailing_enabled);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteLetter(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["letters"] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.updateLetter(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["letters"] });
      setSelectedLetter(null);
    },
  });

  const handleDownloadPdf = async (id: string) => {
    const blob = await api.downloadLetterPdf(id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `letter-${id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleEdit = async (letter: any) => {
    const detail = await api.getLetter(letter.id);
    setSelectedLetter(detail);
    setEditContent(detail.content);
  };

  const letters = data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <EyebrowTag>Letter operations</EyebrowTag>
          <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-[var(--lt-text)]">
            Letters
          </h1>
          <p className="mt-2 text-[var(--lt-text-muted)]">
            Generate, approve, and mail outbound outreach from one queue
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className={secondaryButtonClass}
            aria-label="Refresh letters"
          >
            <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
            Refresh
          </button>
          <button
            onClick={() => setShowBatchDialog(true)}
            className={primaryButtonClass}
          >
            <Plus size={16} /> Batch Generate
          </button>
        </div>
      </div>

      <LetterBatchDialog open={showBatchDialog} onClose={() => setShowBatchDialog(false)} />

      <MailDialog
        open={mailLetter !== null}
        onClose={() => setMailLetter(null)}
        letter={mailLetter}
      />

      {isLoading ? (
        <div className="py-16 text-center text-[var(--lt-text-muted)]">Loading...</div>
      ) : letters.length > 0 ? (
        <ProductCard heading="Generated letters" subtitle={`${letters.length} records`} showDots bodyClassName="px-0 pb-0 pt-4">
          <div className="overflow-x-auto">
            <table className="min-w-[980px] w-full text-sm">
              <thead>
                <tr className="border-y border-[var(--lt-line)] bg-[var(--lt-bg-2)]">
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">County</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Case #</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Owner</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {letters.map((letter: any) => (
                  <tr
                    key={letter.id}
                    className="border-b border-[var(--lt-line)] transition-colors hover:bg-[var(--lt-emerald-dim)]"
                  >
                    <td className="px-4 py-3.5 text-[var(--lt-text)]">{letter.county_name}</td>
                    <td className="px-4 py-3 font-mono text-xs">{letter.case_number}</td>
                    <td className="px-4 py-3.5 text-[var(--lt-text)]">{letter.owner_name || "—"}</td>
                    <td className="px-4 py-3.5">
                      <span className="text-sm capitalize text-[var(--lt-text-muted)]">
                        {letter.letter_type?.replace("_", " ") || "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusPill status={letter.status} />
                    </td>
                    <td className="px-4 py-3.5">
                      <MonoCell size="sm" tone="muted">
                        {formatDate(letter.created_at)}
                      </MonoCell>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleEdit(letter)}
                          className={iconButtonClass}
                          title="Edit"
                        >
                          <FileText size={14} />
                        </button>
                        <button
                          onClick={() => handleDownloadPdf(letter.id)}
                          className={iconButtonClass}
                          title="Download PDF"
                        >
                          <Download size={14} />
                        </button>
                        {letter.status === "approved" && lobEnabled && (
                          <button
                            onClick={() =>
                              setMailLetter({
                                id: letter.id,
                                case_number: letter.case_number,
                                owner_name: letter.owner_name,
                              })
                            }
                            className="rounded-full border border-[rgba(16,185,129,0.2)] bg-[var(--lt-emerald-dim)] p-2 text-[var(--lt-emerald)] transition-colors hover:bg-[rgba(16,185,129,0.2)]"
                            title="Mail via Lob"
                          >
                            <Send size={14} />
                          </button>
                        )}
                        {letter.status === "draft" && (
                          <button
                            onClick={() => deleteMutation.mutate(letter.id)}
                            className="rounded-full border border-transparent p-2 text-[#fca5a5] transition-colors hover:border-[rgba(248,113,113,0.18)] hover:bg-[var(--lt-red-dim)]"
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ProductCard>
      ) : (
        <ProductCard bodyClassName="py-10">
          <EmptyState
            icon={<FileText size={48} />}
            title="No letters yet"
            description="Claim and qualify leads, then generate personalized outreach letters."
            className="text-[var(--lt-text)]"
          />
        </ProductCard>
      )}

      {/* Edit modal */}
      {selectedLetter && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl max-h-[80vh] overflow-hidden rounded-[24px] border border-[var(--lt-line-2)] bg-[linear-gradient(180deg,var(--lt-surface)_0%,var(--lt-bg-2)_100%)] shadow-[0_40px_120px_-40px_rgba(0,0,0,0.9)] flex flex-col">
            <div className="px-6 py-4 border-b border-[var(--lt-line)] flex items-center justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">
                  Letter editor
                </p>
                <h3 className="mt-1 font-semibold text-[var(--lt-text)]">
                  Edit Letter - Case #{selectedLetter.case_number}
                </h3>
              </div>
              <button
                onClick={() => setSelectedLetter(null)}
                className="text-[var(--lt-text-muted)] transition-colors hover:text-[var(--lt-text)]"
              >
                Close
              </button>
            </div>
            <div className="flex-1 overflow-auto p-6">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <StatusPill status={selectedLetter.status} />
                <span className="rounded-full border border-[var(--lt-line)] bg-[var(--lt-bg-2)] px-3 py-1 text-xs text-[var(--lt-text-muted)] capitalize">
                  {selectedLetter.letter_type?.replace(/_/g, " ") || "letter"}
                </span>
              </div>
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="h-96 w-full rounded-[18px] border border-[var(--lt-line)] bg-[rgba(7,11,21,0.75)] p-4 text-sm text-[var(--lt-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] resize-none focus:outline-none focus:ring-2 focus:ring-[rgba(16,185,129,0.3)]"
              />
            </div>
            <div className="px-6 py-4 border-t border-[var(--lt-line)] flex justify-end gap-2">
              <button
                onClick={() =>
                  updateMutation.mutate({
                    id: selectedLetter.id,
                    data: { content: editContent },
                  })
                }
                disabled={updateMutation.isPending}
                className={secondaryButtonClass}
              >
                Save Draft
              </button>
              <button
                onClick={() =>
                  updateMutation.mutate({
                    id: selectedLetter.id,
                    data: { content: editContent, status: "approved" },
                  })
                }
                disabled={updateMutation.isPending}
                className={primaryButtonClass}
              >
                <Check size={14} /> Approve
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
