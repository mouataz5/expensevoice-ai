import type { AxiosError } from "axios";

import type { DeviceReachabilityHint } from "./networkErrors";
import { isAxiosTimeout, isDeviceOffline } from "./networkErrors";

type Detail = string | Record<string, unknown>[] | Record<string, unknown> | undefined;

function detailToString(detail: Detail): string | null {
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((x) => {
        if (x && typeof x === "object" && "msg" in x) return String((x as { msg: unknown }).msg);
        return JSON.stringify(x);
      })
      .filter(Boolean)
      .join("\n");
  }
  if (typeof detail === "object") return JSON.stringify(detail);
  return String(detail);
}

export type FormatApiErrorContext = {
  /** Indique si l’OS signale l’absence de connexion (expo-network). */
  reachability?: DeviceReachabilityHint;
};

/**
 * Message utilisateur + indice optionnel.
 * Erreurs sans `response` : hors ligne vs timeout vs serveur injoignable.
 */
export function formatApiError(
  err: unknown,
  t: (key: string) => string,
  ctx?: FormatApiErrorContext
): { message: string; hint?: string } {
  const ax = err as AxiosError<{ detail?: Detail }>;
  const status = ax?.response?.status;
  const detailStr = detailToString(ax?.response?.data?.detail);

  if (!ax?.response) {
    if (ctx?.reachability && isDeviceOffline(ctx.reachability)) {
      return { message: t("errorNetworkOffline"), hint: t("errorHintNetwork") };
    }
    if (isAxiosTimeout(err)) {
      return { message: t("errorServerTimeout"), hint: t("retry") };
    }
    return { message: t("errorServerUnreachable"), hint: t("errorHintNetwork") };
  }
  if (status === 401) {
    return { message: t("errorUnauthorized"), hint: t("errorHintReauth") };
  }
  if (status === 403) {
    return { message: detailStr || t("errorForbidden") };
  }
  if (status === 404) {
    return { message: detailStr || t("errorNotFound") };
  }
  if (status != null && status >= 500) {
    return { message: detailStr || t("errorServer"), hint: t("errorHintRetryLater") };
  }
  return { message: detailStr || t("errorGeneric") };
}
