import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { toast } from "sonner";

import {
  getPurchase,
  fetchPurchaseAlerts,
  extractPurchase,
  confirmPurchase,
} from "../api/purchases";
import { fetchAllowedCategories } from "../api/policies_public";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function badgeVariant(status: string) {
  if (status === "approved") return "secondary";
  if (status === "pending") return "outline";
  return "secondary";
}

function sevVariant(sev: string): "destructive" | "secondary" | "outline" {
  if (sev === "critical") return "destructive";
  if (sev === "warning") return "secondary";
  return "outline";
}

type PurchaseDetail = {
  id: string;
  product_name: string;
  category: string | null;
  quantity: number;
  unit_price: number;
  total_amount: number;
  status: string;
  transcription: string | null;
  created_at: string | null;
};

type AlertItem = {
  id: string;
  alert_type: string;
  message: string;
  severity: string;
  status: string;
  created_at: string | null;
};

export default function PurchaseDetails() {
  const { id } = useParams();
  const purchaseId = id ?? "";
  const qc = useQueryClient();

  const purchaseQ = useQuery({
    queryKey: ["purchase", purchaseId],
    queryFn: () => getPurchase(purchaseId),
    enabled: !!purchaseId,
  });

  const alertsQ = useQuery({
    queryKey: ["purchase-alerts", purchaseId],
    queryFn: () => fetchPurchaseAlerts(purchaseId),
    enabled: !!purchaseId,
  });

  const categoriesQ = useQuery({
    queryKey: ["allowed-categories"],
    queryFn: fetchAllowedCategories,
  });

  const [form, setForm] = useState({
    product_name: "",
    category: "",
    quantity: 1,
    unit_price: 0,
  });

  useEffect(() => {
    const p = purchaseQ.data as PurchaseDetail | undefined;
    if (p && (p.product_name || p.category !== undefined)) {
      setForm({
        product_name: p.product_name ?? "",
        category: p.category ?? "",
        quantity: p.quantity ?? 1,
        unit_price: p.unit_price ?? 0,
      });
    }
  }, [purchaseQ.data]);

  const total = useMemo(
    () => Number(form.quantity) * Number(form.unit_price),
    [form]
  );

  const extractM = useMutation({
    mutationFn: () => extractPurchase(purchaseId),
    onSuccess: (data: { extracted: Record<string, unknown> }) => {
      const ex = data.extracted;
      setForm({
        product_name: (ex.product_name as string) ?? "",
        category: (ex.category as string) ?? "",
        quantity: (ex.quantity as number) ?? 1,
        unit_price: (ex.unit_price as number) ?? 0,
      });
      toast.success("تم استخراج البيانات من جديد");
      qc.invalidateQueries({ queryKey: ["purchase", purchaseId] });
    },
    onError: () => toast.error("فشل الاستخراج"),
  });

  const confirmM = useMutation({
    mutationFn: () =>
      confirmPurchase(purchaseId, {
        product_name: form.product_name,
        category: form.category || null,
        quantity: Number(form.quantity),
        unit_price: Number(form.unit_price),
        total_amount: total,
      }),
    onSuccess: (data: { alerts_created?: unknown[] }) => {
      toast.success("تم تأكيد العملية");
      const alerts = data.alerts_created ?? [];
      if (alerts.length)
        toast.warning(`تم إنشاء ${alerts.length} تنبيه(ات)`);
      qc.invalidateQueries({ queryKey: ["purchase", purchaseId] });
      qc.invalidateQueries({ queryKey: ["purchase-alerts", purchaseId] });
      qc.invalidateQueries({ queryKey: ["my-purchases"] });
    },
    onError: () => toast.error("فشل التأكيد"),
  });

  if (purchaseQ.isLoading)
    return (
      <div className="text-sm text-muted-foreground">
        جاري تحميل التفاصيل...
      </div>
    );
  if (purchaseQ.isError)
    return (
      <div className="text-sm text-destructive">تعذّر تحميل العملية</div>
    );

  const p = purchaseQ.data as PurchaseDetail;
  const allowed = categoriesQ.data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="text-2xl font-semibold">تفاصيل العملية</div>
          <div className="text-sm text-muted-foreground">
            رقم العملية: <b>{p.id}</b>
          </div>
        </div>
        <Badge variant={badgeVariant(p.status)}>{p.status}</Badge>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-3">
          <div className="font-medium">النص المستخرج (Transcription)</div>
          {p.transcription ? (
            <div className="text-sm bg-muted p-3 rounded-xl whitespace-pre-wrap">
              {p.transcription}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">
              لا يوجد نص مستخرج.
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            <Button
              className="rounded-xl"
              onClick={() => extractM.mutate()}
              disabled={extractM.isPending}
            >
              {extractM.isPending ? "جاري الاستخراج..." : "استخراج من جديد"}
            </Button>
            <Button
              variant="outline"
              className="rounded-xl"
              onClick={() => {
                qc.invalidateQueries({ queryKey: ["purchase", purchaseId] });
                qc.invalidateQueries({
                  queryKey: ["purchase-alerts", purchaseId],
                });
              }}
            >
              تحديث
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-4">
          <div className="font-medium">البيانات</div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>المنتج</Label>
              <Input
                className="rounded-xl"
                value={form.product_name}
                onChange={(e) =>
                  setForm({ ...form, product_name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>التصنيف</Label>
              <Input
                className="rounded-xl"
                list="cats"
                value={form.category}
                onChange={(e) =>
                  setForm({ ...form, category: e.target.value })
                }
              />
              <datalist id="cats">
                {allowed.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </div>
            <div className="space-y-2">
              <Label>الكمية</Label>
              <Input
                className="rounded-xl"
                type="number"
                min={1}
                value={form.quantity}
                onChange={(e) =>
                  setForm({ ...form, quantity: Number(e.target.value) })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>سعر الوحدة</Label>
              <Input
                className="rounded-xl"
                type="number"
                min={0}
                value={form.unit_price}
                onChange={(e) =>
                  setForm({ ...form, unit_price: Number(e.target.value) })
                }
              />
            </div>
          </div>

          <div className="text-sm text-muted-foreground">
            الإجمالي: <b>{total}</b>
          </div>

          <Button
            className="rounded-xl"
            onClick={() => confirmM.mutate()}
            disabled={p.status === "approved" || confirmM.isPending}
          >
            {p.status === "approved"
              ? "تم التأكيد مسبقًا"
              : confirmM.isPending
                ? "جاري التأكيد..."
                : "تأكيد العملية"}
          </Button>
        </CardContent>
      </Card>

      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-3">
          <div className="font-medium">التنبيهات المرتبطة</div>

          {alertsQ.isLoading && (
            <div className="text-sm text-muted-foreground">
              جاري تحميل التنبيهات...
            </div>
          )}
          {alertsQ.isError && (
            <div className="text-sm text-destructive">
              تعذّر تحميل التنبيهات
            </div>
          )}

          {alertsQ.data && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>الخطورة</TableHead>
                  <TableHead>الحالة</TableHead>
                  <TableHead>النوع</TableHead>
                  <TableHead>الرسالة</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(alertsQ.data as AlertItem[]).map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <Badge variant={sevVariant(a.severity)}>
                        {a.severity}
                      </Badge>
                    </TableCell>
                    <TableCell>{a.status}</TableCell>
                    <TableCell className="font-medium">{a.alert_type}</TableCell>
                    <TableCell className="max-w-[520px] truncate">
                      {a.message}
                    </TableCell>
                  </TableRow>
                ))}
                {(alertsQ.data as AlertItem[]).length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className="text-center text-muted-foreground"
                    >
                      لا توجد تنبيهات 🎉
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
