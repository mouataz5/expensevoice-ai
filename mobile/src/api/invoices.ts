import { api, baseURL } from "./client";
import { getStoredToken } from "../lib/secure-store";

export type InvoiceStatusOut = {
  id: string;
  status: string;
  created_at: string;
  error_message?: string | null;
};

export async function scanInvoice(
  imageUri: string,
  transactionType: "sell" | "buy"
): Promise<{ invoice_id: string; status: string }> {
  const formData = new FormData();
  const filename = imageUri.split("/").pop() || "invoice.jpg";
  formData.append("image", {
    uri: imageUri,
    type: "image/jpeg",
    name: filename,
  } as unknown as Blob);
  formData.append("transaction_type", transactionType);

  const { data } = await api.post<{ invoice_id: string; status: string }>("/invoices/scan", formData);
  return data;
}

export async function getInvoice(id: string): Promise<InvoiceStatusOut> {
  const { data } = await api.get<InvoiceStatusOut>(`/invoices/${id}`);
  return data;
}

export function getInvoicePdfUrl(id: string): string {
  return `${baseURL}/invoices/${id}/pdf`;
}

/** Fetch PDF as blob for sharing / opening. */
export async function fetchInvoicePdfBlob(id: string): Promise<Blob> {
  const token = await getStoredToken();
  const url = getInvoicePdfUrl(id);
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Failed to download PDF");
  return res.blob();
}
