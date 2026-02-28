import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "../api/client";
import {
  listInvoices,
  approveInvoice,
  rejectInvoice,
  downloadInvoicePdf,
} from "../api/invoices";
import { fetchMe } from "../api/me";
import type { InvoiceListItem } from "../api/invoices";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
import { FilterToolbar } from "@/components/FilterToolbar";
import { EmptyState } from "@/components/EmptyState";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function InvoiceReview() {
  const qc = useQueryClient();
  const meQ = useQuery({ queryKey: ["me"], queryFn: fetchMe });
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [rejectReason, setRejectReason] = useState("");
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);

  const invoicesQ = useQuery({
    queryKey: ["invoices", statusFilter],
    queryFn: () =>
      listInvoices({
        status: statusFilter || undefined,
        limit: 100,
      }),
    enabled: meQ.data?.role === "admin" || meQ.data?.role === "director",
  });

  const approveM = useMutation({
    mutationFn: (id: string) => approveInvoice(id),
    onSuccess: () => {
      toast.success("تمت الموافقة على الفاتورة");
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["my-purchases"] });
    },
    onError: () => toast.error("فشل الموافقة"),
  });

  const rejectM = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectInvoice(id, reason),
    onSuccess: () => {
      toast.success("تم رفض الفاتورة");
      setRejectId(null);
      setRejectReason("");
      qc.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: () => toast.error("فشل الرفض"),
  });

  const invoices: InvoiceListItem[] = invoicesQ.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="تقارير الفواتير"
        subtitle="تحميل تقارير PDF والاعتماد أو الرفض"
      />

      <FilterToolbar
        statusOptions={[
          { value: "", label: "جميع الحالات" },
          { value: "processing", label: "قيد المعالجة" },
          { value: "ready", label: "جاهز" },
          { value: "approved", label: "معتمدة" },
          { value: "rejected", label: "مرفوضة" },
          { value: "failed", label: "فشل" },
        ]}
        status={statusFilter}
        onStatusChange={setStatusFilter}
        onClear={() => setStatusFilter("")}
      />

      {invoicesQ.isLoading && (
        <div className="rounded-xl border border-border p-8 text-center text-muted-foreground">
          جاري التحميل...
        </div>
      )}

      {invoicesQ.isSuccess && invoices.length === 0 && (
        <EmptyState
          title="لا توجد فواتير"
          description="لم يُرفع أي فاتورة حتى الآن أو لا تطابق الفلاتر."
        />
      )}

      {invoicesQ.isSuccess && invoices.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/50">
                  <TableHead>الموظف</TableHead>
                  <TableHead>رقم الفاتورة</TableHead>
                  <TableHead>المورد</TableHead>
                  <TableHead>الإجمالي TTC</TableHead>
                  <TableHead>الحالة</TableHead>
                  <TableHead>التاريخ</TableHead>
                  <TableHead className="text-right">إجراءات</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((inv) => (
                  <TableRow key={inv.id}>
                    <TableCell className="font-medium">{inv.employee_email}</TableCell>
                    <TableCell>{inv.invoice_number ?? "—"}</TableCell>
                    <TableCell>{inv.supplier_name ?? "—"}</TableCell>
                    <TableCell>
                      {inv.total_ttc != null
                        ? new Intl.NumberFormat("ar-TN", { minimumFractionDigits: 2 }).format(inv.total_ttc)
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusBadgeVariant(inv.status)}>{inv.status}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {inv.created_at ? new Date(inv.created_at).toLocaleDateString("ar-TN") : "—"}
                    </TableCell>
                    <TableCell className="text-left">
                      <div className="flex gap-2 flex-wrap">
                        {(inv.status === "ready" || inv.status === "approved") && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              className="rounded-xl"
                              onClick={() => downloadInvoicePdf(inv.id).then(() => toast.success("تم التحميل")).catch(() => toast.error("فشل التحميل"))}
                            >
                              تحميل PDF (Télécharger PDF)
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="rounded-xl"
                              onClick={() => {
                                setPreviewId(inv.id);
                                const token = localStorage.getItem("access_token");
                                fetch(`${api.defaults.baseURL ?? ""}/invoices/${inv.id}/pdf`, {
                                  headers: token ? { Authorization: `Bearer ${token}` } : {},
                                })
                                  .then((r) => r.blob())
                                  .then((blob) => setPreviewBlobUrl(URL.createObjectURL(blob)))
                                  .catch(() => toast.error("فشل تحميل المعاينة"));
                              }}
                            >
                              معاينة
                            </Button>
                          </>
                        )}
                        {inv.status === "ready" && (
                          <>
                            <Button
                              size="sm"
                              className="rounded-xl"
                              onClick={() => approveM.mutate(inv.id)}
                              disabled={approveM.isPending}
                            >
                              اعتماد
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              className="rounded-xl"
                              onClick={() => setRejectId(inv.id)}
                              disabled={rejectM.isPending}
                            >
                              رفض
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {rejectId && (
        <RejectDialog
          open={!!rejectId}
          onOpenChange={(open) => !open && setRejectId(null)}
          reason={rejectReason}
          onReasonChange={setRejectReason}
          onConfirm={() => {
            if (rejectReason.trim()) rejectM.mutate({ id: rejectId!, reason: rejectReason.trim() });
            else toast.error("أدخل سبب الرفض");
          }}
          onCancel={() => { setRejectId(null); setRejectReason(""); }}
          isLoading={rejectM.isPending}
        />
      )}

      {previewId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => {
            if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl);
            setPreviewBlobUrl(null);
            setPreviewId(null);
          }}
          role="presentation"
        >
          <div
            className="bg-card rounded-2xl shadow-lg max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="معاينة تقرير الفاتورة"
          >
            <div className="p-3 border-b border-border font-medium">معاينة تقرير الفاتورة</div>
            <div className="flex-1 overflow-auto p-3 min-h-[70vh]">
              {previewBlobUrl && (
                <iframe
                  title="PDF preview"
                  src={previewBlobUrl}
                  className="w-full h-[75vh] rounded-lg border border-border"
                />
              )}
              {!previewBlobUrl && (
                <div className="flex items-center justify-center min-h-[70vh] text-muted-foreground">
                  جاري تحميل المعاينة...
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 p-3 border-t border-border">
              <Button
                variant="outline"
                className="rounded-xl"
                onClick={() => {
                  if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl);
                  setPreviewBlobUrl(null);
                  setPreviewId(null);
                }}
              >
                إغلاق
              </Button>
              <Button
                className="rounded-xl"
                onClick={() => {
                  downloadInvoicePdf(previewId!);
                  if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl);
                  setPreviewBlobUrl(null);
                  setPreviewId(null);
                }}
              >
                تحميل PDF (Télécharger PDF)
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function statusBadgeVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" | "warning" | "info" {
  if (status === "approved") return "info";
  if (status === "rejected" || status === "failed") return "destructive";
  if (status === "ready") return "default";
  return "secondary";
}

function RejectDialog({
  open,
  onOpenChange,
  reason,
  onReasonChange,
  onConfirm,
  onCancel,
  isLoading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reason: string;
  onReasonChange: (v: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading: boolean;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => onOpenChange(false)}
      role="presentation"
    >
      <div
        className="bg-card rounded-2xl shadow-lg max-w-md w-full p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="سبب الرفض"
      >
        <div className="font-medium">سبب الرفض</div>
        <Label>أدخل سبب الرفض</Label>
        <Input
          className="rounded-xl"
          value={reason}
          onChange={(e) => onReasonChange(e.target.value)}
          placeholder="سبب الرفض"
        />
        <div className="flex gap-2 justify-end">
          <Button variant="outline" className="rounded-xl" onClick={onCancel}>
            إلغاء
          </Button>
          <Button
            variant="destructive"
            className="rounded-xl"
            onClick={onConfirm}
            disabled={isLoading || !reason.trim()}
          >
            تأكيد الرفض
          </Button>
        </div>
      </div>
    </div>
  );
}
