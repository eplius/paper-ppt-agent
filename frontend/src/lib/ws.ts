import type { JobEvent } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? window.location.origin;

export function openJobSocket(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  onOpen?: () => void,
  onClose?: () => void,
): WebSocket {
  const url = new URL(`/ws/${jobId}`, API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";

  const socket = new WebSocket(url.toString());
  socket.onopen = () => onOpen?.();
  socket.onclose = () => onClose?.();
  socket.onmessage = (message) => {
    onEvent(JSON.parse(message.data) as JobEvent);
  };
  return socket;
}
