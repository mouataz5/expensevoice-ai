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

export type RecordResponse = {
  purchase_id: string;
  status: string;
  processing_status: string;
  transaction_type: string;
};

export async function listMyPurchases(): Promise<PurchaseOut[]> {
  const { data } = await api.get<PurchaseOut[]>("/purchases/me");
  return data;
}

export async function getPurchase(id: string): Promise<PurchaseOut> {
  const { data } = await api.get<PurchaseOut>(`/purchases/${id}`);
  return data;
}

/** Upload voice recording. audioUri from expo-av recording. */
export async function uploadVoice(
  audioUri: string,
  transactionType: "sell" | "buy"
): Promise<RecordResponse> {
  const formData = new FormData();
  const filename = audioUri.split("/").pop() || "recording.webm";
  formData.append("audio", {
    uri: audioUri,
    type: "audio/webm",
    name: filename,
  } as unknown as Blob);
  formData.append("transaction_type", transactionType);

  const { data } = await api.post<RecordResponse>("/purchases/record", formData);
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
): Promise<PurchaseOut> {
  const { data } = await api.post<PurchaseOut>(`/purchases/${id}/confirm`, payload);
  return data;
}
