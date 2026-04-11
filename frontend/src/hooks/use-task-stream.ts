import { useEffect, useState } from "react";
import { useAuth } from "@clerk/clerk-react";

interface TaskEvent {
  status?: "PENDING" | "PROGRESS" | "SUCCESS" | "FAILURE";
  current?: number;
  total?: number;
  result?: any;
  error?: string;
  heartbeat?: boolean;
}

interface UseTaskStreamReturn {
  status: string;
  progress: number;
  result: any | null;
  error: string | null;
}

const API_BASE = `${import.meta.env.VITE_API_URL || ""}/api/v1`;

/**
 * Subscribe to task progress events via SSE. Falls back to polling
 * if the SSE handshake fails.
 */
export function useTaskStream(taskId: string | null): UseTaskStreamReturn {
  const { getToken } = useAuth();
  const [status, setStatus] = useState<string>("PENDING");
  const [progress, setProgress] = useState<number>(0);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;

    let eventSource: EventSource | null = null;
    let pollInterval: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;

    async function connect() {
      try {
        // Get a one-time SSE token using the Clerk JWT
        const jwt = await getToken();
        const tokenResp = await fetch(`${API_BASE}/tasks/${taskId}/stream/token`, {
          method: "POST",
          headers: { Authorization: `Bearer ${jwt}` },
        });
        if (!tokenResp.ok) throw new Error("token");
        const { token } = await tokenResp.json();

        if (cancelled) return;

        // Open the SSE connection
        eventSource = new EventSource(
          `${API_BASE}/tasks/${taskId}/stream?token=${encodeURIComponent(token)}`
        );

        eventSource.onmessage = (e) => {
          try {
            const event: TaskEvent = JSON.parse(e.data);
            if (event.heartbeat) return;
            if (event.status) setStatus(event.status);
            if (event.current != null && event.total) {
              setProgress(Math.round((event.current / event.total) * 100));
            }
            if (event.result) setResult(event.result);
            if (event.error) setError(event.error);
            if (event.status === "SUCCESS" || event.status === "FAILURE") {
              eventSource?.close();
            }
          } catch {
            // ignore malformed events
          }
        };

        eventSource.onerror = () => {
          eventSource?.close();
          eventSource = null;
          if (!cancelled) startPolling();
        };
      } catch {
        startPolling();
      }
    }

    function startPolling() {
      pollInterval = setInterval(async () => {
        try {
          const jwt = await getToken();
          const r = await fetch(`${API_BASE}/tasks/${taskId}`, {
            headers: { Authorization: `Bearer ${jwt}` },
          });
          if (!r.ok) return;
          const data = await r.json();
          if (data.status) setStatus(data.status);
          if (data.result) setResult(data.result);
          if (data.status === "SUCCESS" || data.status === "FAILURE") {
            if (pollInterval) clearInterval(pollInterval);
          }
        } catch {
          // ignore
        }
      }, 3000);
    }

    connect();

    return () => {
      cancelled = true;
      eventSource?.close();
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [taskId, getToken]);

  return { status, progress, result, error };
}
