import type { AxiosError } from "axios";

export type DeviceReachabilityHint = {
  /** false si pas de connexion données/Wi‑Fi utilisable */
  isConnected: boolean;
  /**
   * false si le système indique que l’internet n’est pas joignable.
   * null/undefined côté OS → on ne traite pas comme « hors ligne » pour éviter les faux positifs.
   */
  isInternetReachable: boolean | null;
};

/** Détermine si l’appareil est considéré comme hors ligne (bannière, libellés). */
export function isDeviceOffline(hint: DeviceReachabilityHint): boolean {
  if (hint.isConnected === false) return true;
  if (hint.isInternetReachable === false) return true;
  return false;
}

function asAxios(err: unknown): AxiosError | null {
  if (err && typeof err === "object" && "isAxiosError" in err && (err as AxiosError).isAxiosError) {
    return err as AxiosError;
  }
  return null;
}

/** Requête annulée par timeout axios (`timeout` ms). */
export function isAxiosTimeout(err: unknown): boolean {
  const ax = asAxios(err);
  if (!ax?.response && ax?.code === "ECONNABORTED") return true;
  const m = String(ax?.message || err || "").toLowerCase();
  return m.includes("timeout");
}

/** Erreur réseau sans réponse HTTP (serveur down, DNS, TLS, etc.). */
export function isAxiosNetworkError(err: unknown): boolean {
  const ax = asAxios(err);
  if (!ax) return false;
  return ax.response == null;
}
