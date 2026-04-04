type Listener = (online: boolean) => void;

const listeners = new Set<Listener>();

export function subscribeNetworkStatus(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function notifyApiReachable(): void {
  listeners.forEach((l) => l(true));
}

export function notifyApiUnreachable(): void {
  listeners.forEach((l) => l(false));
}
