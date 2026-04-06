import { api, baseURL } from "./client";
import { getStoredToken } from "../lib/secure-store";

export type InvoiceStatusOut = {
  id: string;
  status: string;
  created_at: string;
  error_message?: string | null;
};

/** Extracted data for review before PDF download (GET /invoices/{id}/preview). */
export type InvoicePreview = {
  id: string;
  status: string;
  created_at: string;
  ocr_text: string;
  normalized_text?: string;
  supplier_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  currency: string;
  items: { designation?: string; quantity?: number; unit_price?: number; line_total?: number }[];
  totals: { htva?: number | null; tva?: number | null; ttc?: number | null; timbre?: number | null };
  confidence: number;
  global_confidence?: number;
  field_confidence?: Record<string, number>;
  validation?: Record<string, unknown>;
  warnings?: string[];
  missing_fields?: string[];
  extraction?: Record<string, unknown>;
  pipeline?: Record<string, unknown>;
  transaction_type: string;
  total_ttc: number | null;
  extraction_error?: string | null;
};

export async function getInvoicePreview(id: string): Promise<InvoicePreview> {
  const { data } = await api.get<InvoicePreview>(`/invoices/${id}/preview`);
  return data;
}

/** Apply user corrections (global draft keys: supplier_name, invoice_number, …). */
export async function applyInvoiceCorrections(
  id: string,
  patch: Record<string, unknown>
): Promise<InvoicePreview> {
  const { data } = await api.post<InvoicePreview>(`/invoices/${id}/apply_corrections`, {
    patch,
  });
  return data;
}

/** Re-run OCR + extraction on stored image; poll GET /invoices/{id} until ready. */
export async function retryInvoiceExtraction(
  id: string
): Promise<{ invoice_id: string; status: string }> {
  const { data } = await api.post<{ invoice_id: string; status: string }>(
    `/invoices/${id}/retry`
  );
  return data;
}

/** Synchronous full pipeline (no DB row). debug: include prompt/LLM excerpts in response. */
export async function extractInvoiceSync(
  imageUri: string,
  transactionType: "sell" | "buy",
  debug = false
): Promise<Record<string, unknown>> {
  const formData = new FormData();
  const filename = imageUri.split("/").pop() || "invoice.jpg";
  formData.append("image", {
    uri: imageUri,
    type: "image/jpeg",
    name: filename,
  } as unknown as Blob);
  formData.append("transaction_type", transactionType);
  formData.append("debug", debug ? "true" : "false");
  const { data } = await api.post<Record<string, unknown>>("/invoices/extract", formData, {
    timeout: 120_000,
  });
  return data;
}

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

  const { data } = await api.post<{ invoice_id: string; status: string }>("/invoices/scan", formData, {
    timeout: 120_000,
  });
  return data;
}

export async function getInvoice(id: string): Promise<InvoiceStatusOut> {
  const { data } = await api.get<InvoiceStatusOut>(`/invoices/${id}`);
  return data;
}

export function getInvoicePdfUrl(id: string): string {
  return `${baseURL}/invoices/${id}/pdf`;
}

/** Admin/Director: list invoices (minimal fields). */
export type InvoiceListItem = {
  id: string;
  employee_email: string;
  invoice_number: string | null;
  supplier_name: string | null;
  total_ttc: number | null;
  status: string;
  created_at: string;
};

export async function listInvoices(params?: {
  status?: string;
  limit?: number;
}): Promise<InvoiceListItem[]> {
  const { data } = await api.get<InvoiceListItem[]>("/invoices", { params });
  return data;
}

/** Current user's invoices (employee / director / admin); same shape as admin list. */
export async function listMyInvoices(params?: {
  status?: string;
  limit?: number;
}): Promise<InvoiceListItem[]> {
  const { data } = await api.get<InvoiceListItem[]>("/invoices/me", { params });
  return data;
}

export async function approveInvoice(
  id: string
): Promise<{ invoice_id: string; status: string; purchase_id: string }> {
  const { data } = await api.post<{
    invoice_id: string;
    status: string;
    purchase_id: string;
  }>(`/invoices/${id}/approve`);
  return data;
}

export async function rejectInvoice(
  id: string,
  rejectionReason: string
): Promise<InvoiceStatusOut> {
  const { data } = await api.post<InvoiceStatusOut>(`/invoices/${id}/reject`, {
    rejection_reason: rejectionReason,
  });
  return data;
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
