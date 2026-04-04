import type { AxiosError } from "axios";

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

/** User-facing API error message + optional hint (e.g. retry network). */
export function formatApiError(
  err: unknown,
  t: (key: string) => string
): { message: string; hint?: string } {
  const ax = err as AxiosError<{ detail?: Detail }>;
  const status = ax?.response?.status;
  const detailStr = detailToString(ax?.response?.data?.detail);

  if (!ax?.response) {
    return { message: t("loginNetworkError"), hint: t("errorHintNetwork") };
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
