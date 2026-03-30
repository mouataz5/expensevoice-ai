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

const AUDIO_MIME: Record<string, string> = {
  ".m4a": "audio/mp4",
  ".mp4": "audio/mp4",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".ogg": "audio/ogg",
  ".webm": "audio/webm",
};

/** Upload voice recording. audioUri from expo-audio (e.g. file:///.../recording-xxx.m4a). */
export async function uploadVoice(
  audioUri: string,
  transactionType: "sell" | "buy"
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
