import type { JobEvent } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? window.location.origin;

export interface ReconnectingSocket {
  close: () => void;
  isOpen: () => boolean;
}

interface ReconnectOptions {
  /** Max number of reconnect attempts. 0 = unlimited. */
  maxAttempts?: number;
  /** Base backoff delay in ms (grows exponentially with jitter). */
  baseDelay?: number;
  /** Maximum backoff delay between attempts. */
  maxDelay?: number;
}

function toWsUrl(path: string): string {
  const url = new URL(path, API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function createReconnectingSocket<TEvent>(
  url: string,
  onEvent: (event: TEvent) => void,
  onOpen?: () => void,
  onClose?: (ev: CloseEvent | null) => void,
  options: ReconnectOptions = {},
): ReconnectingSocket {
  const { maxAttempts = 0, baseDelay = 1000, maxDelay = 15000 } = options;
  let attempt = 0;
  let closedByUser = false;
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    socket = new WebSocket(url);

    socket.onopen = () => {
      attempt = 0;
      onOpen?.();
    };

    socket.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data) as TEvent);
      } catch {
        // Ignore malformed payloads.
      }
    };

    socket.onclose = (ev) => {
      onClose?.(ev);
      if (closedByUser) return;
      if (maxAttempts > 0 && attempt >= maxAttempts) return;
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
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      try {
        socket?.close();
      } catch {
        /* noop */
      }
    },
    isOpen: () => socket?.readyState === WebSocket.OPEN,
  };
}

export function openJobSocket(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  onOpen?: () => void,
  onClose?: () => void,
): ReconnectingSocket {
  return createReconnectingSocket<JobEvent>(
    toWsUrl(`/ws/${jobId}`),
    onEvent,
    onOpen,
    () => onClose?.(),
  );
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
  return createReconnectingSocket<UsageEventPayload>(
    toWsUrl("/api/usage/stream"),
    onEvent,
    onOpen,
    () => onClose?.(),
  );
}
