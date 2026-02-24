import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { extractPurchase, confirmPurchase, uploadVoice } from "../api/purchases";
import { fetchAllowedCategories } from "../api/policies_public";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

function pickMimeType(): string {
  const preferred = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];
  if (typeof window === "undefined" || !(window as unknown as { MediaRecorder?: unknown }).MediaRecorder) return "";
  const MR = (window as unknown as { MediaRecorder: { isTypeSupported?: (t: string) => boolean } }).MediaRecorder;
  for (const t of preferred) {
    try {
      if (MR.isTypeSupported && MR.isTypeSupported(t)) return t;
    } catch {
      // ignore
    }
  }
  return "";
}

function msToTime(ms: number) {
  const s = Math.floor(ms / 1000);
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function EmployeeRecord() {
  const qc = useQueryClient();
  const categoriesQ = useQuery({ queryKey: ["allowed-categories"], queryFn: fetchAllowedCategories });

  // Recorder state
  const [supported, setSupported] = useState(true);
  const [permissionError, setPermissionError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);

  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<number | null>(null);

  // Flow state
  const [purchaseId, setPurchaseId] = useState<string | null>(null);
  const [transcription, setTranscription] = useState<string>("");

  const [form, setForm] = useState({
    product_name: "",
    category: "",
    quantity: 1,
    unit_price: 0,
  });

  const total = useMemo(() => Number(form.quantity) * Number(form.unit_price), [form]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!(window as unknown as { MediaRecorder?: unknown }).MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
      setSupported(false);
    }
    return () => cleanup();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cleanup = () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    recorderRef.current?.stop?.();
    recorderRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
    chunksRef.current = [];
  };

  const startRecording = async () => {
    setPermissionError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const mime = pickMimeType();
      const MR = (window as unknown as { MediaRecorder: new (s: MediaStream, o?: MediaRecorderOptions) => MediaRecorder }).MediaRecorder;
      const rec = new MR(stream, mime ? { mimeType: mime } : undefined);

      chunksRef.current = [];
      rec.ondataavailable = (e: BlobEvent) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };

      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        const ext = rec.mimeType?.includes("mp4") ? "mp4" : rec.mimeType?.includes("ogg") ? "ogg" : "webm";
        const file = new File([blob], `recording.${ext}`, { type: rec.mimeType || "audio/webm" });
        setAudioFile(file);
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
      };

      recorderRef.current = rec;
      rec.start();

      setElapsedMs(0);
      timerRef.current = window.setInterval(() => setElapsedMs((v) => v + 250), 250);
      setRecording(true);
      toast.success("بدأ التسجيل");
    } catch {
      setPermissionError("لم يتم السماح بالميكروفون. فعّل الإذن من المتصفح.");
      toast.error("تعذّر تشغيل الميكروفون");
    }
  };

  const stopRecording = () => {
    if (!recorderRef.current) return;
    recorderRef.current.stop();
    setRecording(false);

    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;

    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;

    toast.success("تم إيقاف التسجيل");
  };

  const resetAll = () => {
    setAudioFile(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setElapsedMs(0);
    setPurchaseId(null);
    setTranscription("");
    setForm({ product_name: "", category: "", quantity: 1, unit_price: 0 });
  };

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!audioFile) throw new Error("no audio");
      return uploadVoice(audioFile, "ar");
    },
    onSuccess: (data: { purchase_id: string; transcription?: string; transcription_failed?: boolean }) => {
      setPurchaseId(data.purchase_id);
      setTranscription(data.transcription || "");
      if (data.transcription_failed) {
        toast.warning("تم الرفع لكن تعذّر تحويل الصوت إلى نص. تحقق من صيغة الملف أو الخدمة.");
      } else {
        toast.success("تم رفع التسجيل وتحويله إلى نص");
      }
    },
    onError: () => toast.error("فشل رفع التسجيل"),
  });

  const extractM = useMutation({
    mutationFn: async () => {
      if (!purchaseId) throw new Error("no purchaseId");
      return extractPurchase(purchaseId);
    },
    onSuccess: (data: { extracted: Record<string, unknown> }) => {
      const ex = data.extracted;
      setForm({
        product_name: (ex.product_name as string) ?? "",
        category: (ex.category as string) ?? "",
        quantity: (ex.quantity as number) ?? 1,
        unit_price: (ex.unit_price as number) ?? 0,
      });
      toast.success("تم استخراج البيانات");
    },
    onError: () => toast.error("فشل استخراج البيانات"),
  });

  const confirmM = useMutation({
    mutationFn: async () => {
      if (!purchaseId) throw new Error("no purchaseId");
      return confirmPurchase(purchaseId, {
        product_name: form.product_name,
        category: form.category || null,
        quantity: Number(form.quantity),
        unit_price: Number(form.unit_price),
        total_amount: total,
      });
    },
    onSuccess: (data: { alerts_created?: unknown[] }) => {
      toast.success("تم تأكيد العملية");
      const alerts = data.alerts_created ?? [];
      if (alerts.length) toast.warning(`تم إنشاء ${alerts.length} تنبيه(ات)`);
      qc.invalidateQueries({ queryKey: ["my-purchases"] });
      resetAll();
    },
    onError: () => toast.error("فشل التأكيد"),
  });

  const allowed = categoriesQ.data ?? [];

  if (!supported) {
    return (
      <div className="space-y-3">
        <div className="text-2xl font-semibold">تسجيل عملية بالصوت</div>
        <div className="text-sm text-destructive">
          المتصفح لا يدعم التسجيل الصوتي. استعمل Chrome/Edge أو حدّث المتصفح.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="text-2xl font-semibold">تسجيل عملية بالصوت</div>
          <div className="text-sm text-muted-foreground">تسجيل → رفع → استخراج → تأكيد</div>
        </div>
        <Button variant="outline" className="rounded-xl" onClick={resetAll}>
          إعادة تعيين
        </Button>
      </div>

      {/* Recorder */}
      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="font-medium">المسجّل</div>
              <div className="text-sm text-muted-foreground">
                {recording ? "جاري التسجيل..." : "جاهز"}
              </div>
            </div>
            <Badge variant={recording ? "destructive" : "secondary"}>
              {recording ? "REC" : "STOP"}
            </Badge>
          </div>

          {permissionError && (
            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-xl">
              {permissionError}
            </div>
          )}

          <div className="flex items-center gap-3 flex-wrap">
            <div className="text-sm text-muted-foreground">
              المدة: <b>{msToTime(elapsedMs)}</b>
            </div>

            {!recording ? (
              <Button className="rounded-xl" onClick={startRecording}>
                ابدأ التسجيل
              </Button>
            ) : (
              <Button className="rounded-xl" variant="destructive" onClick={stopRecording}>
                إيقاف
              </Button>
            )}

            <Button
              className="rounded-xl"
              onClick={() => uploadM.mutate()}
              disabled={!audioFile || uploadM.isPending}
            >
              {uploadM.isPending ? "جاري الرفع..." : "إرسال التسجيل"}
            </Button>

            <Button
              variant="outline"
              className="rounded-xl"
              onClick={() => extractM.mutate()}
              disabled={!purchaseId || extractM.isPending}
            >
              {extractM.isPending ? "جاري الاستخراج..." : "استخراج"}
            </Button>
          </div>

          {audioUrl && (
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">معاينة التسجيل:</div>
              <audio controls src={audioUrl} className="w-full" />
            </div>
          )}

          {purchaseId && (
            <div className="text-sm text-muted-foreground">
              رقم العملية: <b>{purchaseId}</b>
            </div>
          )}

          {transcription && (
            <div className="text-sm bg-muted p-3 rounded-xl whitespace-pre-wrap">
              <b>النص المستخرج:</b> {transcription}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Review + Confirm */}
      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-4">
          <div className="font-medium">مراجعة البيانات</div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>المنتج</Label>
              <Input
                value={form.product_name}
                onChange={(e) => setForm({ ...form, product_name: e.target.value })}
                className="rounded-xl"
                placeholder="مثال: بيع دجاج"
              />
            </div>

            <div className="space-y-2">
              <Label>التصنيف</Label>
              <Input
                list="cats"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="rounded-xl"
                placeholder="اختَر تصنيف"
              />
              <datalist id="cats">
                {allowed.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
              <div className="text-xs text-muted-foreground">
                التصنيفات المسموحة تأتي من سياسات الأدمن.
              </div>
            </div>

            <div className="space-y-2">
              <Label>الكمية</Label>
              <Input
                type="number"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
                className="rounded-xl"
                min={1}
              />
            </div>

            <div className="space-y-2">
              <Label>سعر الوحدة</Label>
              <Input
                type="number"
                value={form.unit_price}
                onChange={(e) => setForm({ ...form, unit_price: Number(e.target.value) })}
                className="rounded-xl"
                min={0}
              />
            </div>
          </div>

          <div className="text-sm text-muted-foreground">
            الإجمالي: <b>{total}</b>
          </div>

          <Button
            className="rounded-xl"
            onClick={() => confirmM.mutate()}
            disabled={!purchaseId || confirmM.isPending}
          >
            {confirmM.isPending ? "جاري التأكيد..." : "تأكيد العملية"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
