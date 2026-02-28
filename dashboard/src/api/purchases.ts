import { api } from "./client";

export type PurchaseOut = {
  id: string;
  user_id: string;
  product_name: string;
  category: string | null;
  quantity: number;
  unit_price: number;
  total_amount: number;
  status: string;
  transcription?: string | null;
  created_at: string;
};

export async function listMyPurchases(): Promise<PurchaseOut[]> {
  const res = await api.get("/purchases/me");
  return res.data;
}

export async function getPurchase(id: string) {
  const res = await api.get(`/purchases/${id}`);
  return res.data;
}

export async function fetchPurchaseAlerts(id: string) {
  const res = await api.get(`/purchases/${id}/alerts`);
  return res.data;
}

export type RecordResponse = {
  purchase_id: string;
  status: string;
  processing_status: string;
  transaction_type: string;
  audio_file_path?: string;
};

export async function uploadVoice(
  audio: File,
  language?: string,
  transactionType?: "sell" | "buy"
): Promise<RecordResponse> {
  const fd = new FormData();
  fd.append("audio", audio);
  if (language) fd.append("language", language);
  fd.append("transaction_type", transactionType === "sell" ? "sell" : "buy");
  const res = await api.post("/purchases/record", fd);
  return res.data;
}

export async function extractPurchase(id: string) {
  const res = await api.post(`/purchases/${id}/extract`);
  return res.data;
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
) {
  const res = await api.post(`/purchases/${id}/confirm`, payload);
  return res.data;
}
