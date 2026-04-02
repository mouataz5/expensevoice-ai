import { api } from "./client";

/** Response from GET /invoices/{id} — status only (no JSON extraction). */
export type InvoiceStatusOut = {
  id: string;
  status: string;
  created_at: string;
  error_message?: string | null;
};

/** Response from GET /invoices — admin list (minimal fields). */
export type InvoiceListItem = {
  id: string;
  employee_email: string;
  invoice_number: string | null;
  supplier_name: string | null;
  total_ttc: number | null;
  status: string;
  created_at: string;
};

export async function scanInvoice(
  image: File,
  transactionType: "sell" | "buy"
): Promise<{ invoice_id: string; status: string }> {
  const fd = new FormData();
  fd.append("image", image);
  fd.append("transaction_type", transactionType);
  const res = await api.post("/invoices/scan", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function getInvoice(id: string): Promise<InvoiceStatusOut> {
  const res = await api.get(`/invoices/${id}`);
  return res.data;
}

/** Returns URL to download PDF (use with fetch + token for actual download). */
export function getInvoicePdfUrl(id: string): string {
  const base = api.defaults.baseURL ?? "";
  return `${base}/invoices/${id}/pdf`;
}

/** Download invoice PDF and trigger browser save. */
export async function downloadInvoicePdf(id: string, filename?: string): Promise<void> {
  const token = localStorage.getItem("access_token");
  const url = getInvoicePdfUrl(id);
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Failed to download PDF");
  const blob = await res.blob();
  const name = filename ?? `invoice_report_${id}.pdf`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

export type InvoicePreview = {
  id: string;
  status: string;
  created_at: string;
  ocr_text: string;
  supplier_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  currency: string;
  items: { designation: string; quantity: number; unit_price: number; line_total: number }[];
  totals: { htva: number | null; tva: number | null; ttc: number | null };
  confidence: number;
  transaction_type: string;
  total_ttc: number | null;
  extraction_error?: string | null;
};

export async function getInvoicePreview(id: string): Promise<InvoicePreview> {
  const res = await api.get(`/invoices/${id}/preview`);
  return res.data;
}

export async function approveInvoice(id: string): Promise<{ invoice_id: string; status: string; purchase_id: string }> {
  const res = await api.post(`/invoices/${id}/approve`);
  return res.data;
}

export async function rejectInvoice(id: string, rejectionReason: string): Promise<InvoiceStatusOut> {
  const res = await api.post(`/invoices/${id}/reject`, { rejection_reason: rejectionReason });
  return res.data;
}

export async function listInvoices(params?: {
  status?: string;
  limit?: number;
}): Promise<InvoiceListItem[]> {
  const res = await api.get("/invoices", { params });
  return res.data;
}
