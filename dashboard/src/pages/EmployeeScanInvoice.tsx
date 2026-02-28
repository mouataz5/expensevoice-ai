import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { scanInvoice, getInvoice, downloadInvoicePdf } from "../api/invoices";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

const POLL_INTERVAL = 1500;
const MAX_POLL_ATTEMPTS = 60;

export default function EmployeeScanInvoice() {
  const [transactionType, setTransactionType] = useState<"sell" | "buy" | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [ready, setReady] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setImageFile(null);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
    setInvoiceId(null);
    setProcessing(false);
    setReady(false);
  }, [imagePreview]);

  const scanM = useMutation({
    mutationFn: async () => {
      if (!imageFile || !transactionType) throw new Error("اختر نوع العملية وارفع صورة الفاتورة");
      return scanInvoice(imageFile, transactionType);
    },
    onSuccess: (data) => {
      setInvoiceId(data.invoice_id);
      setProcessing(true);
      setReady(false);
      toast.info("جارٍ إنشاء تقرير PDF...");
      let attempts = 0;
      const poll = () => {
        attempts += 1;
        getInvoice(data.invoice_id)
          .then((inv) => {
            if (inv.status === "ready") {
              setProcessing(false);
              setReady(true);
              toast.success("تم إنشاء تقرير PDF. يمكنك تحميله الآن.");
              return;
            }
            if (inv.status === "failed") {
              setProcessing(false);
              toast.error(inv.error_message || "فشل إنشاء التقرير");
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
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="مسح فاتورة"
        subtitle="اختر النوع → ارفع الصورة → انتظر التقرير → حمّل PDF"
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

      {/* Step 2 & 3: Upload + Preview */}
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
              <span>جارٍ إنشاء تقرير PDF...</span>
            </div>
          )}

          {ready && invoiceId && (
            <div className="rounded-xl border border-border bg-muted/30 p-4 space-y-2">
              <p className="text-sm font-medium">تم إنشاء تقرير الفاتورة.</p>
              <Button className="rounded-xl" onClick={handleDownloadPdf}>
                تحميل PDF (Télécharger PDF)
              </Button>
            </div>
          )}

          {imagePreview && (
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
    </div>
  );
}
