import type { JobEvent, JobSocketMessage } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? window.location.origin;

export interface ReconnectingSocket {
  close: () => void;
  isOpen: () => boolean;
  /** Last seq this socket has acknowledged from the server. */
  lastSeq: () => number;
}

interface ReconnectOptions {
  /** Max number of reconnect attempts. 0 = unlimited. */
  maxAttempts?: number;
  /** Base backoff delay in ms (grows exponentially with jitter). */
  baseDelay?: number;
  /** Maximum backoff delay between attempts. */
  maxDelay?: number;
  /**
   * If we go this long with no message (including server pings), assume
   * the connection is dead even if the browser hasn't fired ``onclose``
   * yet — common with some reverse proxies — and force a reconnect.
   */
  staleTimeoutMs?: number;
  /** Called when the client gives up reconnecting after maxAttempts. */
  onGiveUp?: () => void;
}

function toWsUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(path, API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, value);
    }
  }
  return url.toString();
}

interface CreateSocketArgs<TEvent> {
  /** Build the URL each connection attempt — receives the current ``lastSeq``. */
  buildUrl: (lastSeq: number) => string;
  onEvent: (event: TEvent) => void;
  onOpen?: () => void;
  onClose?: (ev: CloseEvent | null) => void;
  /** Extract the seq from a message so the client can ack & replay. */
  extractSeq?: (event: TEvent) => number | undefined;
  /** Return true if this message should NOT be forwarded to ``onEvent``. */
  isInternal?: (raw: unknown) => boolean;
  options?: ReconnectOptions;
}

function createReconnectingSocket<TEvent>({
  buildUrl,
  onEvent,
  onOpen,
  onClose,
  extractSeq,
  isInternal,
  options = {},
}: CreateSocketArgs<TEvent>): ReconnectingSocket {
  const {
    maxAttempts = 12,
    baseDelay = 1000,
    maxDelay = 15000,
    staleTimeoutMs = 60_000,
    onGiveUp,
  } = options;
  let attempt = 0;
  let closedByUser = false;
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let staleTimer: ReturnType<typeof setTimeout> | null = null;
  let lastSeq = 0;

  const armStaleTimer = () => {
    if (staleTimer) clearTimeout(staleTimer);
    staleTimer = setTimeout(() => {
      // Force a reconnect — the server has been silent for too long.
      try {
        socket?.close(4000, "stale");
      } catch {
        /* noop */
      }
    }, staleTimeoutMs);
  };

  const clearTimers = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (staleTimer) {
      clearTimeout(staleTimer);
      staleTimer = null;
    }
  };

  const connect = () => {
    socket = new WebSocket(buildUrl(lastSeq));

    socket.onopen = () => {
      attempt = 0;
      armStaleTimer();
      onOpen?.();
    };

    socket.onmessage = (message) => {
      armStaleTimer();
      let parsed: unknown;
      try {
        parsed = JSON.parse(message.data);
      } catch {
        return;
      }
      if (isInternal && isInternal(parsed)) {
        return;
      }
      const event = parsed as TEvent;
      const seq = extractSeq?.(event);
      if (typeof seq === "number" && seq > lastSeq) {
        lastSeq = seq;
      }
      onEvent(event);
    };

    socket.onclose = (ev) => {
      if (staleTimer) {
        clearTimeout(staleTimer);
        staleTimer = null;
      }
      onClose?.(ev);
      if (closedByUser) return;
      // Treat clean closes as terminal:
      //   1000 — normal closure (server signalled "done")
      //   1005 — no status; browsers report this when the server closed
      //          without an explicit code, which our backend does on
      //          terminal job state via Starlette's default
      //   1008 — policy violation; we use this for "job not found", the
      //          client must not retry
      const code = ev?.code;
      if (code === 1000 || code === 1005 || code === 1008) return;
      if (maxAttempts > 0 && attempt >= maxAttempts) {
        onGiveUp?.();
        return;
      }
      const delay = Math.min(
        maxDelay,
        baseDelay * 2 ** attempt * (0.5 + Math.random() * 0.5),
      );
      attempt += 1;
      reconnectTimer = setTimeout(connect, delay);
    };

    socket.onerror = () => {
      // Let onclose drive reconnection; just ensure the socket is torn down.
      try {
        socket?.close();
      } catch {
        /* noop */
      }
    };
  };

  connect();

  return {
    close: () => {
      closedByUser = true;
      clearTimers();
      try {
        socket?.close();
      } catch {
        /* noop */
      }
    },
    isOpen: () => socket?.readyState === WebSocket.OPEN,
    lastSeq: () => lastSeq,
  };
}

export function openJobSocket(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  onOpen?: () => void,
  onClose?: () => void,
  onGiveUp?: () => void,
): ReconnectingSocket {
  return createReconnectingSocket<JobEvent>({
    buildUrl: (lastSeq) =>
      toWsUrl(`/ws/${jobId}`, lastSeq > 0 ? { since_seq: String(lastSeq) } : undefined),
    onEvent,
    onOpen,
    onClose: () => onClose?.(),
    extractSeq: (event) => {
      const seq = (event as JobEvent & { seq?: number; last_seq?: number }).seq;
      if (typeof seq === "number") return seq;
      // Snapshot frames carry the latest known seq so we can resume from
      // it even before a real progress event has been delivered.
      const lastFromSnapshot = (event as JobEvent & { last_seq?: number }).last_seq;
      if (typeof lastFromSnapshot === "number") return lastFromSnapshot;
      return undefined;
    },
    isInternal: (raw) => {
      // Drop server pings — they exist purely to keep the socket alive
      // and shouldn't be forwarded to UI handlers.
      return Boolean(raw && typeof raw === "object" && (raw as { type?: string }).type === "ping");
    },
    options: { onGiveUp },
  });
}

export interface UsageEventPayload {
  type: "snapshot" | "usage";
  // For `snapshot` the server inlines summary/by_model/by_stage/daily/recent.
  // For `usage` the server inlines a single `record`.
  [key: string]: unknown;
}

export function openUsageSocket(
  onEvent: (event: UsageEventPayload) => void,
  onOpen?: () => void,
  onClose?: () => void,
): ReconnectingSocket {
  return createReconnectingSocket<UsageEventPayload>({
    buildUrl: () => toWsUrl("/api/usage/stream"),
    onEvent,
    onOpen,
    onClose: () => onClose?.(),
  });
}

export type { JobSocketMessage };
