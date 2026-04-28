import { api } from "./client";

export type BackendReachability =
  | { ok: true }
  | {
      ok: false;
      kind: "timeout" | "unreachable" | "http_error" | "unknown";
      status?: number;
      message?: string;
    };

export async function checkBackendReachability(): Promise<BackendReachability> {
  try {
    await api.get("/health", { timeout: 4000 });
    return { ok: true };
  } catch (e) {
    const ax = e as {
      response?: { status?: number };
      code?: string;
      message?: string;
      isAxiosError?: boolean;
    };
    if (ax?.response?.status) {
      return { ok: false, kind: "http_error", status: ax.response.status, message: ax.message };
    }
    if (ax?.code === "ECONNABORTED" || String(ax?.message || "").toLowerCase().includes("timeout")) {
      return { ok: false, kind: "timeout", message: ax?.message };
    }
    if (ax?.isAxiosError && !ax?.response) {
      return { ok: false, kind: "unreachable", message: ax?.message };
    }
    return { ok: false, kind: "unknown", message: String(ax?.message || e) };
  }
}

