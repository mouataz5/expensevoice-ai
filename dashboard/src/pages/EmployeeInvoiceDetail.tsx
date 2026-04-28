import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  applyInvoiceCorrections,
  downloadInvoicePdf,
  getInvoicePreview,
  retryInvoiceExtraction,
  type InvoicePreview,
} from "../api/invoices";
import { EmployeeHero, EmployeePage, EmployeeSectionCard } from "@/components/employee/EmployeeShell";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function fmtTnd(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "-";
  return new Intl.NumberFormat("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(v);
}

export default function EmployeeInvoiceDetail() {
  const { id } = useParams();
  const invoiceId = id ?? "";
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState({
    supplier_name: "",
    invoice_number: "",
    invoice_date: "",
    total_amount: "",
    currency: "TND",
  });

  const previewQ = useQuery({
    queryKey: ["employee-invoice-preview", invoiceId],
    queryFn: () => getInvoicePreview(invoiceId),
    enabled: !!invoiceId,
    retry: 1,
  });

  useEffect(() => {
    const p = previewQ.data;
    if (!p) return;
    setForm({
      supplier_name: p.supplier_name ?? "",
      invoice_number: p.invoice_number ?? "",
      invoice_date: p.invoice_date ?? "",
      total_amount: p.total_ttc != null ? String(p.total_ttc) : "",
      currency: p.currency ?? "TND",
    });
  }, [previewQ.data]);

  const retryM = useMutation({
    mutationFn: () => retryInvoiceExtraction(invoiceId),
    onSuccess: () => {
      toast.success("تمت إعادة المحاولة");
      previewQ.refetch();
    },
    onError: () => toast.error("فشلت إعادة الاستخراج"),
  });

  const patchM = useMutation({
    mutationFn: async () => {
      const patch: Record<string, unknown> = {};
      if (form.supplier_name.trim()) patch.supplier_name = form.supplier_name.trim();
      if (form.invoice_number.trim()) patch.invoice_number = form.invoice_number.trim();
      if (form.invoice_date.trim()) patch.invoice_date = form.invoice_date.trim();
      if (form.currency.trim()) patch.currency = form.currency.trim().toUpperCase();
      const parsed = Number(String(form.total_amount).replace(",", "."));
      if (form.total_amount.trim() && !Number.isNaN(parsed)) patch.total_amount = parsed;
      return applyInvoiceCorrections(invoiceId, patch);
    },
    onSuccess: () => {
      toast.success("تم حفظ التصحيحات");
      setEditOpen(false);
      previewQ.refetch();
    },
    onError: () => toast.error("فشل حفظ التصحيحات"),
  });

  const p = previewQ.data as InvoicePreview | undefined;
  const conf = useMemo(() => Math.round((p?.confidence ?? 0) * 100), [p?.confidence]);

  return (
    <EmployeePage>
      <EmployeeHero
        eyebrow="Employee Workspace"
        title="تفاصيل الفاتورة"
        subtitle="مراجعة الاستخراج، التصحيح اليدوي، وإعادة المعالجة عند الحاجة."
        meta={[
          { label: "Invoice", value: invoiceId || "-" },
          { label: "الثقة", value: `${conf}%` },
        ]}
      />
      <PageHeader
        title="تفاصيل الفاتورة"
        subtitle={invoiceId ? `ID: ${invoiceId}` : "—"}
        actions={
          <div className="flex gap-2">
            <Button variant="outline" className="rounded-xl" onClick={() => previewQ.refetch()}>
              تحديث
            </Button>
            <Button className="rounded-xl" onClick={() => void downloadInvoicePdf(invoiceId)} disabled={!invoiceId}>
              PDF
            </Button>
          </div>
        }
      />

      <EmployeeSectionCard title="المعاينة">
        {previewQ.isLoading ? <div className="text-sm text-muted-foreground">جاري التحميل...</div> : null}
        {previewQ.isError ? <div className="text-sm text-destructive">تعذّر تحميل المعاينة</div> : null}
        {p ? (
          <div className="space-y-3">
            <div className="text-sm text-muted-foreground">الثقة: <b>{conf}%</b></div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded-xl border border-border p-3"><b>المورد:</b> {p.supplier_name || "-"}</div>
              <div className="rounded-xl border border-border p-3"><b>رقم الفاتورة:</b> {p.invoice_number || "-"}</div>
              <div className="rounded-xl border border-border p-3"><b>التاريخ:</b> {p.invoice_date || "-"}</div>
              <div className="rounded-xl border border-border p-3"><b>TTC:</b> {fmtTnd(p.total_ttc ?? p.totals?.ttc)} {p.currency}</div>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button variant="outline" className="rounded-xl" onClick={() => setEditOpen((v) => !v)}>
                {editOpen ? "إغلاق التعديل" : "تعديل يدوي"}
              </Button>
              <Button variant="outline" className="rounded-xl" onClick={() => retryM.mutate()} disabled={retryM.isPending}>
                {retryM.isPending ? "..." : "إعادة الاستخراج"}
              </Button>
            </div>
          </div>
        ) : null}
      </EmployeeSectionCard>

      {editOpen ? (
        <EmployeeSectionCard title="تصحيح يدوي">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Supplier</Label>
              <Input className="rounded-xl" value={form.supplier_name} onChange={(e) => setForm({ ...form, supplier_name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Invoice Number</Label>
              <Input className="rounded-xl" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Invoice Date (YYYY-MM-DD)</Label>
              <Input className="rounded-xl" value={form.invoice_date} onChange={(e) => setForm({ ...form, invoice_date: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Total</Label>
              <Input className="rounded-xl" value={form.total_amount} onChange={(e) => setForm({ ...form, total_amount: e.target.value })} />
            </div>
          </div>
          <Button className="rounded-xl" onClick={() => patchM.mutate()} disabled={patchM.isPending}>
            {patchM.isPending ? "جاري الحفظ..." : "حفظ التصحيحات"}
          </Button>
        </EmployeeSectionCard>
      ) : null}
    </EmployeePage>
  );
}
