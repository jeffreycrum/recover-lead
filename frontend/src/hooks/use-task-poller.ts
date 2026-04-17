import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["SUCCESS", "FAILURE", "REVOKED"]);

/**
 * Polls GET /tasks/{taskId} every 2 seconds until the task reaches a terminal
 * state, then invalidates the provided query keys and calls onDone.
 *
 * Pass null as taskId to disable polling.
 */
export function useTaskPoller({
  taskId,
  invalidateKeys,
  onDone,
  onError,
}: {
  taskId: string | null;
  invalidateKeys: unknown[][];
  onDone?: (result: unknown) => void;
  onError?: (error: string) => void;
}) {
  const qc = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!taskId) return;

    timerRef.current = setInterval(async () => {
      try {
        const data = await api.getTaskStatus(taskId);
        if (!TERMINAL_STATUSES.has(data.status)) return;

        clearInterval(timerRef.current!);
        timerRef.current = null;

        for (const key of invalidateKeys) {
          qc.invalidateQueries({ queryKey: key });
        }

        if (data.status === "SUCCESS") {
          onDone?.(data.result);
        } else {
          onError?.(data.error ?? "Task failed");
        }
      } catch {
        // Network blip — keep polling
      }
    }, POLL_INTERVAL_MS);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [taskId]); // eslint-disable-line react-hooks/exhaustive-deps
}
