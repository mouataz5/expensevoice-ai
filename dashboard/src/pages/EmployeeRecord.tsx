import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { extractPurchase, confirmPurchase, uploadVoice, getPurchase, createPurchase, listMyPurchasesFiltered } from "../api/purchases";
import { fetchAllowedCategories } from "../api/policies_public";
import { listFarms } from "../api/farms";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
import { Stepper } from "@/components/Stepper";
import { EmployeePage, EmployeeSectionCard } from "@/components/employee/EmployeeShell";

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
  const farmsQ = useQuery({ queryKey: ["farms"], queryFn: listFarms });
  const recentPurchasesQ = useQuery({ queryKey: ["my-purchases", "record-options"], queryFn: () => listMyPurchasesFiltered({ limit: 100 }) });

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

  // Part 3: Transaction type (بيع / شراء) — must choose before recording
  const [transactionType, setTransactionType] = useState<"sell" | "buy" | null>("buy");
  const [entryMode, setEntryMode] = useState<"voice" | "manual">("voice");
  const [processing, setProcessing] = useState(false);
  const [farmId, setFarmId] = useState("");

  // Flow state
  const [purchaseId, setPurchaseId] = useState<string | null>(null);
  const [transcription, setTranscription] = useState<string>("");
  const reviewCardRef = useRef<HTMLDivElement>(null);

  const [form, setForm] = useState({
    supplier_name: "",
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

  const resetAll = useCallback(() => {
    setAudioFile(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setElapsedMs(0);
    setPurchaseId(null);
    setTranscription("");
    setProcessing(false);
    setTransactionType("buy");
    setForm({ supplier_name: "", product_name: "", category: "", quantity: 1, unit_price: 0 });
  }, [audioUrl]);

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!audioFile) throw new Error("no audio");
      if (!transactionType) throw new Error("اختر نوع العملية: بيع أو شراء");
      if (!farmId) throw new Error("اختر المزرعة أولاً");
      return uploadVoice(audioFile, "ar", transactionType, farmId);
    },
    onSuccess: (data: { purchase_id: string; processing_status?: string }) => {
      setPurchaseId(data.purchase_id);
      setProcessing(true);
      toast.info("جارٍ معالجة التسجيل...");
      let attempts = 0;
      // Allow more time for STT + LLM on slower machines/models.
      const maxAttempts = 80; // 80 * 1.5s ≈ 2 minutes
      const interval = 1500;
      const poll = () => {
        attempts += 1;
        getPurchase(data.purchase_id)
          .then((p: { processing_status?: string; transcription?: string; product_name?: string; category?: string; quantity?: number; unit_price?: number }) => {
            setTranscription((p.transcription as string) || "");
            if (p.processing_status === "ready_for_review" || p.processing_status === "approved") {
              setProcessing(false);
              if (p.product_name) {
                setForm({
                  supplier_name: "",
                  product_name: (p.product_name as string) ?? "",
                  category: (p.category as string) ?? "",
                  quantity: typeof p.quantity === "number" ? p.quantity : 1,
                  unit_price: typeof p.unit_price === "number" ? p.unit_price : 0,
                });
              }
              toast.success("تمت المعالجة. راجع البيانات وأكّد.");
              reviewCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
              return;
            }
            if (attempts < maxAttempts) setTimeout(poll, interval);
            else {
              setProcessing(false);
              toast.warning("لم تكتمل المعالجة بعد. حدّث الصفحة أو جرّب الاستخراج يدوياً.");
            }
          })
          .catch(() => {
            if (attempts < maxAttempts) setTimeout(poll, interval);
            else setProcessing(false);
          });
      };
      setTimeout(poll, interval);
    },
    onError: () => {
      setProcessing(false);
      toast.error("فشل رفع التسجيل");
    },
  });

  const extractM = useMutation({
    mutationFn: async () => {
      if (!purchaseId) throw new Error("no purchaseId");
      return extractPurchase(purchaseId);
    },
    onSuccess: (data: { extracted: Record<string, unknown>; fallback?: boolean }) => {
      const ex = data.extracted;
      setForm({
        supplier_name: "",
        product_name: (ex.product_name as string) ?? "",
        category: (ex.category as string) ?? "",
        quantity: (ex.quantity as number) ?? 1,
        unit_price: (ex.unit_price as number) ?? 0,
      });
      if (data.fallback) {
        toast.info("المحرك اللغوي غير متصل — راجع البيانات يدوياً وأكّد العملية");
      } else {
        toast.success("تم استخراج البيانات");
      }
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
      qc.invalidateQueries({ queryKey: ["my-alerts"] });
      resetAll();
    },
    onError: () => toast.error("فشل التأكيد"),
  });

  const createManualM = useMutation({
    mutationFn: async () => {
      if (!farmId) throw new Error("اختر المزرعة أولاً");
      if (!transactionType) throw new Error("اختر نوع العملية أولاً");
      if (!form.product_name.trim()) throw new Error("أدخل اسم المنتج");
      if (transactionType === "buy" && !form.category.trim()) throw new Error("اختر التصنيف");
      return createPurchase({
        farm_id: farmId,
        transaction_type: transactionType,
        product_name: form.product_name,
        category: transactionType === "buy" ? form.category || null : null,
        quantity: Number(form.quantity),
        unit_price: Number(form.unit_price),
      });
    },
    onSuccess: () => {
      toast.success("تم إنشاء العملية يدوياً");
      qc.invalidateQueries({ queryKey: ["my-purchases"] });
      qc.invalidateQueries({ queryKey: ["my-alerts"] });
      resetAll();
    },
    onError: (e) => {
      toast.error(String((e as Error)?.message ?? "فشل إنشاء العملية"));
    },
  });

  const allowed = categoriesQ.data ?? [];
  const BUY_CATEGORY_OPTIONS = [
    "charge_variable_electricite",
    "charge_variable_eau",
    "charge_variable_gaz",
    "charge_fixe_location",
    "achat_aliment",
  ];
  const SELL_PRODUCT_OPTIONS = ["nourriture", "poussins"];
  const supplierOptions = useMemo(() => {
    const set = new Set<string>();
    for (const p of recentPurchasesQ.data ?? []) {
      const v = p.supplier_name?.trim();
      if (v) set.add(v);
    }
    if (form.supplier_name.trim()) set.add(form.supplier_name.trim());
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [recentPurchasesQ.data, form.supplier_name]);
  const productOptions = useMemo(() => {
    const set = new Set<string>();
    if (transactionType === "sell") {
      SELL_PRODUCT_OPTIONS.forEach((v) => set.add(v));
    } else {
      for (const p of recentPurchasesQ.data ?? []) {
        const v = p.product_name?.trim();
        if (v) set.add(v);
      }
      set.add("nourriture");
    }
    if (form.product_name.trim()) set.add(form.product_name.trim());
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [recentPurchasesQ.data, form.product_name, transactionType]);
  const categoryOptions = useMemo(() => {
    if (transactionType !== "buy") return [];
    const set = new Set<string>([...BUY_CATEGORY_OPTIONS, ...allowed]);
    if (form.category.trim()) set.add(form.category.trim());
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [transactionType, allowed, form.category]);
  const farmName = useMemo(() => (farmsQ.data ?? []).find((f) => f.id === farmId)?.name ?? null, [farmsQ.data, farmId]);
  const canRunVoice = !!transactionType && !!farmId && !processing;

  const steps = [
    { key: "record", label: "تسجيل", done: !!audioFile, active: !audioFile },
    { key: "upload", label: "رفع", done: !!purchaseId, active: !!audioFile && !purchaseId },
    { key: "extract", label: "استخراج", done: !!form.product_name || !!transcription, active: !!purchaseId && !form.product_name && !transcription },
    { key: "confirm", label: "تأكيد", done: false, active: !!form.product_name && !!purchaseId },
  ];

  if (!supported) {
    return (
      <div className="space-y-3">
        <PageHeader title="تسجيل عملية بالصوت" />
        <div className="text-sm text-destructive rounded-2xl border border-destructive/20 bg-destructive/5 p-4">
          المتصفح لا يدعم التسجيل الصوتي. استعمل Chrome/Edge أو حدّث المتصفح.
        </div>
      </div>
    );
  }

  return (
    <EmployeePage className="space-y-8 pb-6">
      <div className="text-right rounded-xl border border-emerald-100/70 bg-gradient-to-l from-emerald-50/70 to-white p-5">
        <div className="inline-flex items-center rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 mb-3">
          واجهة حديثة • Smart workflow
        </div>
        <h2 className="text-2xl font-bold text-emerald-900">تسجيل عملية جديدة</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          قم بتوثيق النشاط الزراعي الحالي باستخدام الصوت أو الإدخال اليدوي لضمان دقة البيانات.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-4 space-y-5">
          <div className="rounded-xl border border-border/60 bg-card p-5 shadow-sm transition-all hover:shadow-md">
            <div className="flex items-center justify-between mb-3">
              <span className="rounded-full bg-emerald-100 text-emerald-800 px-2 py-1 text-xs font-semibold">نشط الآن</span>
              <Badge variant="secondary">{recording ? "REC" : "جاهز"}</Badge>
            </div>
            <h3 className="font-semibold text-foreground mb-3">وضع التسجيل</h3>
            <div className="rounded-lg bg-muted/40 p-3 flex items-center gap-3">
              <div className="h-11 w-11 rounded-full bg-emerald-900 text-white flex items-center justify-center">🎙️</div>
              <div>
                <p className="text-sm font-semibold text-emerald-900">{entryMode === "voice" ? "تسجيل صوتي ذكي" : "إدخال يدوي"}</p>
                <p className="text-xs text-muted-foreground">{processing ? "جاري معالجة اللغة الطبيعية" : "جاهز لبدء العملية"}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-border/60 bg-card p-5 shadow-sm space-y-3 transition-all hover:shadow-md">
            <h3 className="font-semibold text-foreground">تفاصيل بيئة العمل</h3>
            <div className="text-sm flex justify-between"><span className="text-muted-foreground">الموقع الحالي</span><span className="font-semibold">{farmName ?? "غير محددة"}</span></div>
            <div className="text-sm flex justify-between"><span className="text-muted-foreground">نوع العملية</span><span className="font-semibold">{transactionType === "sell" ? "بيع" : "شراء"}</span></div>
            <div className="text-sm flex justify-between"><span className="text-muted-foreground">الوضع</span><span className="font-semibold">{entryMode === "voice" ? "صوتي" : "يدوي"}</span></div>
          </div>
        </div>

        <div className="lg:col-span-8">
          <div className="rounded-xl border border-border/60 bg-card p-8 shadow-sm text-center relative overflow-hidden transition-all hover:shadow-md">
            <div className="pointer-events-none absolute -top-16 -right-16 h-48 w-48 rounded-full bg-emerald-200/30 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-emerald-900/10 blur-3xl" />
            <div className="relative space-y-4">
              <div className="mx-auto flex items-end gap-1 h-10 justify-center">
                {[4, 8, 12, 6, 10, 12, 8, 4].map((h, idx) => (
                  <div key={idx} className="w-1 rounded-full bg-emerald-500/60" style={{ height: `${h * 4}px` }} />
                ))}
              </div>
              <button
                type="button"
                className="mx-auto h-28 w-28 rounded-full bg-emerald-800 text-white flex items-center justify-center shadow-lg transition-transform active:scale-95"
                onClick={() => {
                  if (entryMode !== "voice") return;
                  if (!recording) void startRecording();
                  else stopRecording();
                }}
                disabled={entryMode !== "voice" || (!recording && !canRunVoice)}
              >
                <span className="text-4xl">🎤</span>
              </button>
              <h3 className="text-xl font-semibold text-foreground">{recording ? "جاري التسجيل..." : "اضغط للبدء"}</h3>
              <p className="text-sm text-muted-foreground max-w-xl mx-auto">
                تحدث بشكل طبيعي لوصف العملية الزراعية أو استخدم الإدخال اليدوي حسب حاجتك.
              </p>
              <div className="text-sm text-muted-foreground">المدة: <b>{msToTime(elapsedMs)}</b></div>
              <div className="flex flex-wrap justify-center gap-2">
                <span className="rounded-full border border-border bg-muted/40 px-3 py-1 text-xs">UX Moderne</span>
                <span className="rounded-full border border-border bg-muted/40 px-3 py-1 text-xs">RTL Ready</span>
                <span className="rounded-full border border-border bg-muted/40 px-3 py-1 text-xs">Voice + Manual</span>
              </div>
              <div className="flex gap-3 justify-center flex-wrap">
                {entryMode === "voice" ? (
                  <Button
                    className="rounded-xl min-w-36"
                    onClick={() => uploadM.mutate()}
                    disabled={!audioFile || !farmId || uploadM.isPending || processing}
                  >
                    {uploadM.isPending ? "جاري الرفع..." : "إرسال التسجيل"}
                  </Button>
                ) : null}
                <Button variant={entryMode === "manual" ? "default" : "outline"} className="rounded-xl" onClick={() => setEntryMode("manual")}>
                  إدخال يدوي
                </Button>
                <Button variant={entryMode === "voice" ? "default" : "outline"} className="rounded-xl" onClick={() => setEntryMode("voice")}>
                  تسجيل صوتي
                </Button>
                <Button variant="outline" className="rounded-xl" onClick={resetAll}>إعادة تعيين</Button>
              </div>
              {processing ? (
                <div className="flex items-center justify-center gap-2 rounded-xl bg-primary/10 border border-primary/20 p-3 text-primary">
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  <span>جارٍ معالجة التسجيل...</span>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {entryMode === "voice" ? (
        <div className="rounded-xl border border-border/60 bg-card p-5 shadow-sm">
          <Stepper steps={steps} className="mb-2" />
        </div>
      ) : null}

      <EmployeeSectionCard title="إعداد العملية" subtitle="اختر المزرعة ونوع العملية قبل المتابعة" className="transition-shadow hover:shadow-md border-emerald-100/60">
        <div className="space-y-4">
          <Label className="text-base">المزرعة</Label>
          <select
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
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
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Button type="button" variant={transactionType === "sell" ? "default" : "outline"} className="rounded-xl justify-start" onClick={() => setTransactionType("sell")}>بيع</Button>
            <Button type="button" variant={transactionType === "buy" ? "default" : "outline"} className="rounded-xl justify-start" onClick={() => setTransactionType("buy")}>شراء</Button>
          </div>
          {entryMode === "voice" ? (
            <div className="flex items-center gap-3 flex-wrap">
              <Button variant="outline" className="rounded-xl" onClick={() => extractM.mutate()} disabled={!purchaseId || extractM.isPending}>
                {extractM.isPending ? "جاري الاستخراج..." : "استخراج"}
              </Button>
              {permissionError ? <div className="text-sm text-destructive">{permissionError}</div> : null}
            </div>
          ) : null}
          {audioUrl ? <audio controls src={audioUrl} className="w-full" /> : null}
          {purchaseId ? <div className="text-sm text-muted-foreground">رقم العملية: <b>{purchaseId}</b></div> : null}
          {transcription ? <div className="text-sm bg-muted p-3 rounded-xl whitespace-pre-wrap"><b>النص المستخرج:</b> {transcription}</div> : null}
        </div>
      </EmployeeSectionCard>

      <div ref={reviewCardRef}>
        <EmployeeSectionCard
          title={entryMode === "manual" && !purchaseId ? "إدخال يدوي" : "مراجعة وتأكيد"}
          subtitle="تحقق من الحقول قبل تأكيد العملية"
          className="transition-shadow hover:shadow-md border-emerald-100/60"
        >
          <div className="font-medium">مراجعة البيانات</div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>المورد</Label>
              <Input
                list="suppliers"
                value={form.supplier_name}
                onChange={(e) => setForm({ ...form, supplier_name: e.target.value })}
                className="rounded-xl"
                placeholder="اختر أو اكتب المورد"
              />
              <datalist id="suppliers">
                {supplierOptions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>

            <div className="space-y-2">
              <Label>المنتج</Label>
              <Input
                list="products"
                value={form.product_name}
                onChange={(e) => setForm({ ...form, product_name: e.target.value })}
                className="rounded-xl"
                placeholder="مثال: بيع دجاج"
              />
              <datalist id="products">
                {productOptions.map((p) => (
                  <option key={p} value={p} />
                ))}
              </datalist>
            </div>

            {transactionType === "buy" ? (
              <div className="space-y-2">
                <Label>التصنيف</Label>
                <Input
                  list="cats-buy"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  className="rounded-xl"
                  placeholder="اختَر تصنيف"
                />
                <datalist id="cats-buy">
                  {categoryOptions.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
                <div className="text-xs text-muted-foreground">
                  التصنيفات المسموحة تأتي من سياسات الأدمن.
                </div>
              </div>
            ) : null}

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
          <div className="space-y-2">
            <Label>الإجمالي</Label>
            <Input value={String(total)} readOnly className="rounded-xl bg-muted/40" />
          </div>

          <Button className="rounded-xl" onClick={() => (purchaseId ? confirmM.mutate() : createManualM.mutate())} disabled={confirmM.isPending || createManualM.isPending}>
            {purchaseId
              ? confirmM.isPending
                ? "جاري التأكيد..."
                : "تأكيد العملية"
              : createManualM.isPending
              ? "جاري الحفظ..."
              : "حفظ العملية يدوياً"}
          </Button>
          {purchaseId ? (
            <Button variant="outline" className="rounded-xl mt-2" onClick={resetAll}>
              إعادة المحاولة
            </Button>
          ) : null}
        </EmployeeSectionCard>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="rounded-xl bg-emerald-900 p-4 text-white flex items-center justify-between">
          <div>
            <p className="text-xs text-emerald-200">العمليات اليوم</p>
            <p className="text-xl font-bold">{recentPurchasesQ.data?.length ?? 0}</p>
          </div>
          <span className="text-2xl opacity-70">📊</span>
        </div>
        <div className="rounded-xl border border-border/60 bg-card p-4 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">إجمالي العملية الحالية</p>
            <p className="text-xl font-bold text-emerald-900">{total}</p>
          </div>
          <span className="text-2xl">💰</span>
        </div>
        <div className="rounded-xl border border-border/60 bg-card p-4 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">جاهزية الاستخراج</p>
            <p className="text-xl font-bold text-emerald-900">{purchaseId ? "مرتفعة" : "بانتظار الإدخال"}</p>
          </div>
          <span className="text-2xl">✅</span>
        </div>
      </div>
    </EmployeePage>
  );
}
