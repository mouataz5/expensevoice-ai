import { api } from "./client";
import type { Locale } from "../i18n/translations";

/** Aligné sur backend `PurchaseOut` (liste + détail). */
export type PurchaseOut = {
  id: string;
  user_id: string;
  farm_id?: string | null;
  farm_name?: string | null;
  product_name: string;
  category: string | null;
  quantity: number;
  unit_price: number;
  total_amount: number;
  status: string;
  created_at: string;
  purchase_date?: string;
  transaction_type?: string | null;
  processing_status?: string | null;
  stt_confidence?: number | null;
  extraction_confidence?: number | null;
  transcription?: string | null;
  audio_file_path?: string | null;
  source?: "voice" | "manual" | "scan" | null;
  total_ht?: number | null;
  total_tva?: number | null;
  total_ttc?: number | null;
  is_tax_estimated?: boolean | null;
};

export type RecordResponse = {
  purchase_id: string;
  status: string;
  processing_status: string;
  transaction_type: string;
};

/** Réponse réelle de POST /purchases/{id}/confirm (pas un PurchaseOut complet). */
export type PurchaseConfirmResponse = {
  purchase_id: string;
  status: string;
  total_amount: number;
  alerts_created?: { type: string; severity: string; message: string }[];
};

/** Langue Whisper — "auto" lets the model auto-detect the spoken language. */
export function sttLanguageFromLocale(_locale: Locale): string {
  return "auto";
}

export type PurchaseFilterParams = {
  q?: string;
  transaction_type?: "buy" | "sell";
  status?: string;
  source?: "voice" | "manual" | "scan";
  farm_id?: string;
  qty_min?: number;
  qty_max?: number;
  unit_price_min?: number;
  unit_price_max?: number;
  ht_min?: number;
  ht_max?: number;
  tva_min?: number;
  tva_max?: number;
  ttc_min?: number;
  ttc_max?: number;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
};

export async function listMyPurchases(params?: PurchaseFilterParams): Promise<PurchaseOut[]> {
  const { data } = await api.get<PurchaseOut[]>("/purchases/me", { params });
  return data;
}

export type PurchaseAllOut = PurchaseOut & { employee_email?: string };

export async function listAllPurchases(params?: PurchaseFilterParams): Promise<PurchaseAllOut[]> {
  const { data } = await api.get<PurchaseAllOut[]>("/purchases/all", { params });
  return data;
}

export async function getPurchase(id: string): Promise<PurchaseOut> {
  const { data } = await api.get<PurchaseOut>(`/purchases/${id}`);
  return data;
}

export type PurchaseAlertRow = {
  id: string;
  alert_type: string;
  message: string;
  severity: string;
  status: string;
  created_at: string | null;
};

export async function fetchPurchaseAlerts(id: string): Promise<PurchaseAlertRow[]> {
  const { data } = await api.get<PurchaseAlertRow[]>(`/purchases/${id}/alerts`);
  return data;
}

export async function extractPurchase(id: string): Promise<{ extracted: Record<string, unknown> }> {
  const { data } = await api.post<{ extracted: Record<string, unknown> }>(`/purchases/${id}/extract`);
  return data;
}

export async function approvePurchase(id: string): Promise<{ purchase_id: string; status: string }> {
  const { data } = await api.post<{ purchase_id: string; status: string }>(`/purchases/${id}/approve`);
  return data;
}

export async function rejectPurchase(id: string): Promise<{ purchase_id: string; status: string }> {
  const { data } = await api.post<{ purchase_id: string; status: string }>(`/purchases/${id}/reject`);
  return data;
}

const AUDIO_MIME: Record<string, string> = {
  ".m4a": "audio/mp4",
  ".mp4": "audio/mp4",
  ".caf": "audio/x-caf",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".ogg": "audio/ogg",
  ".webm": "audio/webm",
  ".aac": "audio/aac",
};

/** True lorsque le backend a fini STT + extraction (status reste souvent `pending`). */
export function isVoicePipelineReady(p: Pick<PurchaseOut, "status" | "processing_status">): boolean {
  return p.processing_status === "ready_for_review";
}

/** Upload voix — timeout long (STT serveur). Langue = locale app pour Whisper. */
export async function uploadVoice(
  audioUri: string,
  transactionType: "sell" | "buy",
  options?: { language?: string; farm_id?: string }
): Promise<RecordResponse> {
  const formData = new FormData();
  const filename = audioUri.split("/").pop() || "recording.m4a";
  const ext = filename.includes(".") ? filename.slice(filename.lastIndexOf(".")).toLowerCase() : ".m4a";
  const mime = AUDIO_MIME[ext] ?? "audio/mp4";
  formData.append("audio", {
    uri: audioUri,
    type: mime,
    name: filename,
  } as unknown as Blob);
  formData.append("transaction_type", transactionType);
  if (options?.farm_id) {
    formData.append("farm_id", options.farm_id);
  }
  if (options?.language) {
    formData.append("language", options.language);
  }

  const { data } = await api.post<RecordResponse>("/purchases/record", formData, {
    timeout: 120000,
  });
  return data;
}

export async function confirmPurchase(
  id: string,
  payload: {
    product_name: string;
    category?: string | null;
    quantity: number;
    unit_price: number;
    total_amount: number;
  }
): Promise<PurchaseConfirmResponse> {
  const { data } = await api.post<PurchaseConfirmResponse>(`/purchases/${id}/confirm`, payload);
  return data;
}
