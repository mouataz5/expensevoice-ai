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
  const res = await api.get("/api/purchases/me");
  return res.data;
}

export async function getPurchase(id: string) {
  const res = await api.get(`/api/purchases/${id}`);
  return res.data;
}

export async function fetchPurchaseAlerts(id: string) {
  const res = await api.get(`/api/purchases/${id}/alerts`);
  return res.data;
}

export async function uploadVoice(audio: File, language?: string) {
  const fd = new FormData();
  fd.append("audio", audio);
  if (language) fd.append("language", language);
  const res = await api.post("/api/purchases/record", fd);
  return res.data;
}

export async function extractPurchase(id: string) {
  const res = await api.post(`/api/purchases/${id}/extract`);
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
  const res = await api.post(`/api/purchases/${id}/confirm`, payload);
  return res.data;
}
