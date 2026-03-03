import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
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

const POLL_INTERVAL = 1500;
const MAX_POLL_ATTEMPTS = 80;

function fmtTND(val: number | null | undefined): string {
  if (val == null) return "—";
  return new Intl.NumberFormat("fr-TN", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  }).format(val);
}

export default function EmployeeScanInvoice() {
  const [transactionType, setTransactionType] = useState<"sell" | "buy" | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [ready, setReady] = useState(false);
  const [preview, setPreview] = useState<InvoicePreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

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
      return scanInvoice(imageFile, transactionType);
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
    <div className="space-y-6">
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
      <Card>
        <CardContent className="p-5 space-y-4">
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
        </CardContent>
      </Card>

      {/* Step 2: Upload */}
      <Card>
        <CardContent className="p-5 space-y-4">
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
          <div className="flex gap-3 flex-wrap">
            <Button
              type="button"
              variant="outline"
              className="rounded-xl"
              onClick={() => fileInputRef.current?.click()}
              disabled={!transactionType}
            >
              اختيار ملف
            </Button>
            <Button
              type="button"
              variant="outline"
              className="rounded-xl"
              onClick={() => cameraInputRef.current?.click()}
              disabled={!transactionType}
            >
              فتح الكاميرا
            </Button>
            <Button
              className="rounded-xl"
              onClick={() => scanM.mutate()}
              disabled={!imageFile || !transactionType || scanM.isPending || processing}
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
                className="max-h-64 rounded-xl border border-border object-contain"
              />
            </div>
          )}

          {!imageFile && !processing && !ready && (
            <EmptyState
              title="لم تُرفع صورة بعد"
              description="اختر نوع العملية ثم ارفع صورة الفاتورة (كاميرا أو ملف)."
            />
          )}
        </CardContent>
      </Card>

      {/* Step 3: Extraction Review Dashboard */}
      {loadingPreview && (
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span>جاري تحميل البيانات المستخرجة...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {preview && (
        <>
          {/* Confidence + Summary Header */}
          <Card>
            <CardContent className="p-5 space-y-4">
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
            </CardContent>
          </Card>

          {/* Items Table */}
          {preview.items.length > 0 && (
            <Card>
              <CardContent className="p-5 space-y-3">
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
              </CardContent>
            </Card>
          )}

          {preview.items.length === 0 && (
            <Card>
              <CardContent className="p-5">
                <p className="text-sm text-muted-foreground text-center">
                  لم يتم استخراج مواد من الفاتورة (Aucun article extrait)
                </p>
              </CardContent>
            </Card>
          )}

          {/* Totals */}
          <Card>
            <CardContent className="p-5 space-y-3">
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
            </CardContent>
          </Card>

          {/* PDF Download + Image */}
          <Card>
            <CardContent className="p-5 space-y-4">
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
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
