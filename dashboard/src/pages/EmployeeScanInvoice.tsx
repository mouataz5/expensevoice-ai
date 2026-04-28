import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  scanInvoice,
  getInvoice,
  downloadInvoicePdf,
  getInvoicePreview,
  type InvoicePreview,
} from "../api/invoices";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { EmployeePage, EmployeeSectionCard } from "@/components/employee/EmployeeShell";
import { listFarms } from "../api/farms";

const POLL_INTERVAL = 3000;      // 3s between polls (OCR on CPU is slow)
const MAX_POLL_ATTEMPTS = 400;   // up to 20 minutes total

function fmtTND(val: number | null | undefined): string {
  if (val == null) return "—";
  return new Intl.NumberFormat("fr-TN", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  }).format(val);
}

export default function EmployeeScanInvoice() {
  const [transactionType, setTransactionType] = useState<"sell" | "buy" | null>(null);
  const [farmId, setFarmId] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [ready, setReady] = useState(false);
  const [preview, setPreview] = useState<InvoicePreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const farmsQ = useQuery({ queryKey: ["farms"], queryFn: listFarms });

  const reset = useCallback(() => {
    setImageFile(null);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
    setInvoiceId(null);
    setProcessing(false);
    setReady(false);
    setPreview(null);
  }, [imagePreview]);

  const fetchPreview = useCallback(async (id: string) => {
    setLoadingPreview(true);
    try {
      const data = await getInvoicePreview(id);
      setPreview(data);
    } catch {
      toast.error("فشل تحميل البيانات المستخرجة");
    } finally {
      setLoadingPreview(false);
    }
  }, []);

  const scanM = useMutation({
    mutationFn: async () => {
      if (!imageFile || !transactionType) throw new Error("اختر نوع العملية وارفع صورة الفاتورة");
      if (!farmId) throw new Error("اختر المزرعة قبل رفع الفاتورة");
      return scanInvoice(imageFile, transactionType, farmId);
    },
    onSuccess: (data) => {
      setInvoiceId(data.invoice_id);
      setProcessing(true);
      setReady(false);
      setPreview(null);
      toast.info("جارٍ معالجة الفاتورة...");
      let attempts = 0;
      const poll = () => {
        attempts += 1;
        getInvoice(data.invoice_id)
          .then((inv) => {
            if (inv.status === "ready") {
              setProcessing(false);
              setReady(true);
              toast.success("تمت المعالجة — راجع البيانات المستخرجة");
              fetchPreview(data.invoice_id);
              return;
            }
            if (inv.status === "failed") {
              setProcessing(false);
              toast.error(inv.error_message || "فشل معالجة الفاتورة");
              return;
            }
            if (attempts < MAX_POLL_ATTEMPTS) setTimeout(poll, POLL_INTERVAL);
            else {
              setProcessing(false);
              toast.warning("لم تكتمل المعالجة. حدّث الصفحة أو جرّب مرة أخرى.");
            }
          })
          .catch(() => {
            if (attempts < MAX_POLL_ATTEMPTS) setTimeout(poll, POLL_INTERVAL);
            else setProcessing(false);
          });
      };
      setTimeout(poll, POLL_INTERVAL);
    },
    onError: () => toast.error("فشل رفع الفاتورة"),
  });

  const handleDownloadPdf = useCallback(async () => {
    if (!invoiceId) return;
    try {
      await downloadInvoicePdf(invoiceId);
      toast.success("تم تحميل التقرير");
    } catch {
      toast.error("فشل تحميل PDF");
    }
  }, [invoiceId]);

  useEffect(() => {
    if (!imageFile) {
      setImagePreview(null);
      return;
    }
    const url = URL.createObjectURL(imageFile);
    setImagePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const ct = (f.type || "").toLowerCase();
    if (!ct.startsWith("image/")) {
      toast.error("استخدم صورة (jpg, png, heic)");
      return;
    }
    if (f.size > 8 * 1024 * 1024) {
      toast.error("حجم الملف أكبر من 8 ميجا");
      return;
    }
    setImageFile(f);
    setReady(false);
    setPreview(null);
  };

  const confLevel = preview?.confidence ?? 0;
  const confColor =
    confLevel >= 0.7 ? "bg-emerald-500" : confLevel >= 0.3 ? "bg-amber-500" : "bg-red-500";

  return (
    <EmployeePage className="space-y-8">
      <div className="rounded-2xl border border-emerald-100/70 bg-gradient-to-l from-emerald-100/70 via-emerald-50/60 to-white p-6 text-right shadow-sm">
        <div className="inline-flex items-center rounded-full bg-emerald-200/80 px-3 py-1 text-xs font-semibold text-emerald-900 mb-3">
          Scan Workspace • Modern UX
        </div>
        <h2 className="text-2xl font-bold text-emerald-900">مسح فاتورة</h2>
        <p className="mt-1 text-sm text-muted-foreground">اختر النوع → ارفع الصورة → راجع البيانات → حمّل PDF</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs text-emerald-900">
            {(farmsQ.data ?? []).find((f) => f.id === farmId)?.name ?? "غير محددة"}
          </span>
          <span className="rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs text-emerald-900">
            {transactionType === "sell" ? "بيع" : transactionType === "buy" ? "شراء" : "غير محدد"}
          </span>
          <span className="rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs text-emerald-900">
            {ready ? "جاهز" : processing ? "قيد المعالجة" : "بانتظار الرفع"}
          </span>
        </div>
      </div>
      <PageHeader
        title="مسح فاتورة"
        subtitle="اختر النوع → ارفع الصورة → راجع البيانات → حمّل PDF"
        actions={
          <Button variant="outline" className="rounded-xl" onClick={reset}>
            إعادة تعيين
          </Button>
        }
      />

      {/* Step 1: Transaction type */}
      <EmployeeSectionCard title="نوع العملية" subtitle="حدد نوع الفاتورة قبل الرفع" className="transition-shadow hover:shadow-md">
          <Label className="text-base">المزرعة</Label>
          <select
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm mb-3"
            value={farmId}
            onChange={(e) => setFarmId(e.target.value)}
          >
            <option value="">اختر المزرعة</option>
            {(farmsQ.data ?? []).map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
          <Label className="text-base">نوع العملية</Label>
          <div className="flex gap-3 flex-wrap">
            <Button
              type="button"
              variant={transactionType === "buy" ? "default" : "outline"}
              className="rounded-xl"
              onClick={() => setTransactionType("buy")}
            >
              شراء
            </Button>
            <Button
              type="button"
              variant={transactionType === "sell" ? "default" : "outline"}
              className="rounded-xl"
              onClick={() => setTransactionType("sell")}
            >
              بيع
            </Button>
          </div>
      </EmployeeSectionCard>

      {/* Step 2: Upload */}
      <EmployeeSectionCard title="رفع الفاتورة" subtitle="اختر من الملفات أو التقط صورة بالكاميرا" className="transition-shadow hover:shadow-md">
          <Label className="text-base">صورة الفاتورة (jpg, png, heic — حتى 8 ميجا)</Label>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/heic,image/heif"
            className="hidden"
            onChange={handleFileChange}
          />
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={handleFileChange}
          />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Button
              type="button"
              variant="outline"
              className="rounded-xl"
              onClick={() => fileInputRef.current?.click()}
              disabled={!transactionType || !farmId}
            >
              اختيار ملف
            </Button>
            <Button
              type="button"
              variant="outline"
              className="rounded-xl"
              onClick={() => cameraInputRef.current?.click()}
              disabled={!transactionType || !farmId}
            >
              فتح الكاميرا
            </Button>
            <Button
              className="rounded-xl"
              onClick={() => scanM.mutate()}
              disabled={!imageFile || !transactionType || !farmId || scanM.isPending || processing}
            >
              {scanM.isPending ? "جاري الرفع..." : "إرسال للمعالجة"}
            </Button>
          </div>

          {processing && (
            <div className="flex items-center gap-2 rounded-xl bg-primary/10 border border-primary/20 p-3 text-primary">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span>جارٍ معالجة الفاتورة (OCR + استخراج)...</span>
            </div>
          )}

          {imagePreview && !preview && (
            <div className="space-y-2">
              <Label>معاينة</Label>
              <img
                src={imagePreview}
                alt="فاتورة"
                className="w-full max-h-72 rounded-xl border border-border object-contain bg-muted/20"
              />
            </div>
          )}

          {!imageFile && !processing && !ready && (
            <EmptyState
              title="لم تُرفع صورة بعد"
              description="اختر نوع العملية ثم ارفع صورة الفاتورة (كاميرا أو ملف)."
            />
          )}
      </EmployeeSectionCard>

      {/* Step 3: Extraction Review Dashboard */}
      {loadingPreview && (
        <EmployeeSectionCard>
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span>جاري تحميل البيانات المستخرجة...</span>
            </div>
        </EmployeeSectionCard>
      )}

      {preview && (
        <>
          {/* Partial extraction warning — shown when items could not be read */}
          {preview.items.length === 0 && (preview.supplier_name || (preview.total_ttc ?? 0) > 0) && (
            <Card className="border-amber-400/60 bg-amber-50/70 dark:bg-amber-950/30">
              <CardContent className="p-4 flex items-start gap-3">
                <span className="text-amber-600 text-xl mt-0.5">⚠️</span>
                <div className="space-y-1">
                  <p className="font-semibold text-amber-800 dark:text-amber-300 text-sm">
                    استخراج جزئي — يرجى المراجعة اليدوية
                  </p>
                  <p className="text-xs text-amber-700 dark:text-amber-400">
                    تم استخراج بعض البيانات (المورد / رقم الفاتورة) لكن تعذّر قراءة جدول المنتجات
                    أو المبالغ بشكل كامل بسبب جودة الصورة أو النص العربي المختلط.
                    تحقّق من جميع الحقول وأدخل البنود يدوياً إن لزم.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Extraction partielle — vérifiez les montants et saisissez les articles manuellement.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Confidence + Summary Header */}
          <EmployeeSectionCard title="ملخص الاستخراج">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold">البيانات المستخرجة (Données extraites)</h2>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">الثقة:</span>
                  <div className="w-24 h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full ${confColor}`}
                      style={{ width: `${Math.round(confLevel * 100)}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium">{Math.round(confLevel * 100)}%</span>
                </div>
              </div>

              {/* Key fields */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-xl border border-border p-3 space-y-1">
                  <p className="text-xs text-muted-foreground">المورد (Fournisseur)</p>
                  <p className="font-medium text-sm">{preview.supplier_name || "—"}</p>
                </div>
                <div className="rounded-xl border border-border p-3 space-y-1">
                  <p className="text-xs text-muted-foreground">رقم الفاتورة (N° Facture)</p>
                  <p className="font-medium text-sm">{preview.invoice_number || "—"}</p>
                </div>
                <div className="rounded-xl border border-border p-3 space-y-1">
                  <p className="text-xs text-muted-foreground">التاريخ (Date)</p>
                  <p className="font-medium text-sm">{preview.invoice_date || "—"}</p>
                </div>
                <div className="rounded-xl border border-border p-3 space-y-1">
                  <p className="text-xs text-muted-foreground">النوع (Type)</p>
                  <Badge variant="secondary">
                    {preview.transaction_type === "sell" ? "بيع (Vente)" : "شراء (Achat)"}
                  </Badge>
                </div>
              </div>
          </EmployeeSectionCard>

          {/* Items Table */}
          {preview.items.length > 0 && (
            <EmployeeSectionCard title="تفاصيل المواد">
                <h3 className="font-semibold">تفاصيل المواد (Détails articles)</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground">
                        <th className="text-right py-2 px-2">الصنف (Désignation)</th>
                        <th className="text-center py-2 px-2">الكمية (Qté)</th>
                        <th className="text-center py-2 px-2">سعر الوحدة (PU)</th>
                        <th className="text-center py-2 px-2">المبلغ (Montant)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.items.map((item, i) => (
                        <tr key={i} className="border-b border-border/50">
                          <td className="py-2 px-2 font-medium">{item.designation}</td>
                          <td className="py-2 px-2 text-center">{item.quantity}</td>
                          <td className="py-2 px-2 text-center">{fmtTND(item.unit_price)}</td>
                          <td className="py-2 px-2 text-center">{fmtTND(item.line_total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
            </EmployeeSectionCard>
          )}

          {preview.items.length === 0 && (
            <EmployeeSectionCard>
                <p className="text-sm text-muted-foreground text-center">
                  {preview.extraction_error === "no_ocr_text"
                    ? "لم يتم العثور على نص في الصورة — تحقق من جودة الصورة أو إعدادات المسح (No text detected — check image quality or OCR)"
                    : "لم يتم استخراج مواد من الفاتورة (Aucun article extrait)"}
                </p>
            </EmployeeSectionCard>
          )}

          {/* Totals */}
          <EmployeeSectionCard title="الإجماليات">
              <h3 className="font-semibold">الإجماليات (Totaux)</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="rounded-xl bg-muted/30 border border-border p-3 text-center">
                  <p className="text-xs text-muted-foreground">HTVA</p>
                  <p className="text-lg font-bold">{fmtTND(preview.totals.htva)}</p>
                </div>
                <div className="rounded-xl bg-muted/30 border border-border p-3 text-center">
                  <p className="text-xs text-muted-foreground">TVA</p>
                  <p className="text-lg font-bold">{fmtTND(preview.totals.tva)}</p>
                </div>
                <div className="rounded-xl bg-primary/10 border border-primary/20 p-3 text-center">
                  <p className="text-xs text-primary">TTC</p>
                  <p className="text-xl font-bold text-primary">
                    {fmtTND(preview.totals.ttc ?? preview.total_ttc)}
                  </p>
                </div>
                <div className="rounded-xl bg-muted/30 border border-border p-3 text-center">
                  <p className="text-xs text-muted-foreground">العملة (Devise)</p>
                  <p className="text-lg font-bold">{preview.currency}</p>
                </div>
              </div>
          </EmployeeSectionCard>

          {/* PDF Download + Image */}
          <EmployeeSectionCard title="المخرجات" className="transition-shadow hover:shadow-md">
              <div className="flex items-center gap-3 flex-wrap">
                <Button className="rounded-xl" onClick={handleDownloadPdf}>
                  تحميل PDF (Télécharger PDF)
                </Button>
                <Button variant="outline" className="rounded-xl" onClick={reset}>
                  مسح فاتورة جديدة
                </Button>
              </div>
              {imagePreview && (
                <div className="space-y-2">
                  <Label>صورة الفاتورة</Label>
                  <img
                    src={imagePreview}
                    alt="فاتورة"
                    className="max-h-80 rounded-xl border border-border object-contain"
                  />
                </div>
              )}
          </EmployeeSectionCard>
        </>
      )}
    </EmployeePage>
  );
}
