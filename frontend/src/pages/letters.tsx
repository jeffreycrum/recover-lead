import { useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/common/empty-state";
import { formatDate } from "@/lib/utils";
import { FileText, Download, Trash2, Check, Plus, Send } from "lucide-react";
import { LetterBatchDialog } from "@/components/letters/letter-batch-dialog";
import { MailDialog } from "@/components/letters/mail-dialog";

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

  const { data, isLoading } = useQuery({
    queryKey: ["letters"],
    queryFn: () => api.getLetters(),
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Letters</h1>
          <p className="text-muted-foreground">Generated outreach letters</p>
        </div>
        <button
          onClick={() => setShowBatchDialog(true)}
          className="px-4 py-2 bg-emerald text-white rounded-md hover:bg-emerald/90 text-sm font-medium flex items-center gap-2"
        >
          <Plus size={16} /> Batch Generate
        </button>
      </div>

      <LetterBatchDialog open={showBatchDialog} onClose={() => setShowBatchDialog(false)} />

      <MailDialog
        open={mailLetter !== null}
        onClose={() => setMailLetter(null)}
        letter={mailLetter}
      />

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading...</div>
      ) : letters.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50/50">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">County</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Case #</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Owner</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Type</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Created</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {letters.map((letter: any) => (
                <tr key={letter.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3">{letter.county_name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{letter.case_number}</td>
                  <td className="px-4 py-3">{letter.owner_name || "—"}</td>
                  <td className="px-4 py-3 capitalize">{letter.letter_type?.replace("_", " ")}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      letter.status === "approved"
                        ? "bg-emerald/10 text-emerald"
                        : "bg-gray-100 text-gray-700"
                    } capitalize`}>
                      {letter.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{formatDate(letter.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleEdit(letter)}
                        className="p-1.5 rounded hover:bg-gray-100"
                        title="Edit"
                      >
                        <FileText size={14} />
                      </button>
                      <button
                        onClick={() => handleDownloadPdf(letter.id)}
                        className="p-1.5 rounded hover:bg-gray-100"
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
                          className="p-1.5 rounded hover:bg-emerald/10 text-emerald"
                          title="Mail via Lob"
                        >
                          <Send size={14} />
                        </button>
                      )}
                      {letter.status === "draft" && (
                        <button
                          onClick={() => deleteMutation.mutate(letter.id)}
                          className="p-1.5 rounded hover:bg-red-50 text-red-500"
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
      ) : (
        <EmptyState
          icon={<FileText size={48} />}
          title="No letters yet"
          description="Claim and qualify leads, then generate personalized outreach letters."
        />
      )}

      {/* Edit modal */}
      {selectedLetter && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <h3 className="font-semibold">
                Edit Letter — Case #{selectedLetter.case_number}
              </h3>
              <button onClick={() => setSelectedLetter(null)} className="text-muted-foreground hover:text-foreground">
                Close
              </button>
            </div>
            <div className="flex-1 overflow-auto p-6">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full h-96 p-4 border rounded-md text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-emerald/50"
              />
            </div>
            <div className="px-6 py-4 border-t flex justify-end gap-2">
              <button
                onClick={() =>
                  updateMutation.mutate({
                    id: selectedLetter.id,
                    data: { content: editContent },
                  })
                }
                className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
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
                className="px-4 py-2 text-sm bg-emerald text-white rounded-md hover:bg-emerald/90 flex items-center gap-2"
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
