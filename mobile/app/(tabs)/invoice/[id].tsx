import { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Linking,
  Modal,
  TextInput,
} from "react-native";
import { useLocalSearchParams, useRouter, useSegments } from "expo-router";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { useLocale } from "../../../src/context/LocaleContext";
import { colors } from "../../../src/theme/colors";
import { font, radius, shadow, space } from "../../../src/theme/tokens";
import {
  Card,
  PrimaryButton,
  SecondaryButton,
  StatusPill,
  SectionTitle,
  invoiceStatusTone,
  ConfidenceBar,
  InvoiceListSkeleton,
  ProductBrandMark,
  DestructiveOutlineButton,
} from "../../../src/components/ui";
import { AdminAccentStripe, AdminDecisionCard, AdminSectionLabel } from "../../../src/components/admin";
import {
  getInvoice,
  getInvoicePreview,
  getInvoicePdfUrl,
  approveInvoice,
  rejectInvoice,
  type InvoicePreview,
} from "../../../src/api/invoices";
import { getStoredToken } from "../../../src/lib/secure-store";
import { queryKeys } from "../../../src/queryKeys";
import { formatApiError } from "../../../src/utils/apiError";
import Toast from "react-native-toast-message";

function DefRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.defRow}>
      <Text style={styles.defLabel}>{label}</Text>
      <Text style={styles.defValue}>{value}</Text>
    </View>
  );
}

function fmtTn(val: number | null | undefined): string {
  if (val == null || Number.isNaN(val)) return "—";
  return new Intl.NumberFormat("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(val);
}

function InvoiceTimeline({
  status,
  createdAt,
  hasPreview,
  t,
}: {
  status: string;
  createdAt: string;
  hasPreview: boolean;
  t: (k: string) => string;
}) {
  const terminal = status === "approved" || status === "rejected" || status === "failed";
  const processing = status === "processing";
  const processingDone = !processing;
  const extractedDone =
    status === "ready" ||
    status === "ready_for_review" ||
    status === "approved" ||
    status === "rejected" ||
    (status === "failed" && hasPreview);

  const steps = [
    {
      key: "received",
      label: t("invoiceTimelineReceived"),
      done: true,
      current: false,
    },
    {
      key: "processing",
      label: t("invoiceTimelineProcessing"),
      done: processingDone,
      current: processing,
    },
    {
      key: "extracted",
      label: t("invoiceTimelineExtracted"),
      done: extractedDone,
      current: processingDone && !extractedDone && !terminal,
    },
    {
      key: "outcome",
      label: t("invoiceTimelineOutcome"),
      done: terminal,
      current: terminal,
    },
  ];

  return (
    <Card style={styles.timelineCard}>
      <Text style={styles.timelineTitle}>{t("invoiceTimelineTitle")}</Text>
      <Text style={styles.timelineMeta}>
        {t("invoiceCreatedAt")} {new Date(createdAt).toLocaleString()}
      </Text>
      <View style={styles.timelineTrack}>
        {steps.map((s, i) => (
          <View key={s.key} style={styles.timelineStep}>
            <View style={styles.timelineCol}>
              <View
                style={[
                  styles.timelineDot,
                  s.done && styles.timelineDotDone,
                  s.current && !s.done && styles.timelineDotCurrent,
                ]}
              >
                {s.done ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
              </View>
              {i < steps.length - 1 ? (
                <View style={[styles.timelineLine, steps[i + 1]!.done && styles.timelineLineDone]} />
              ) : null}
            </View>
            <View style={styles.timelineBody}>
              <Text style={[styles.timelineLabel, s.current && styles.timelineLabelCurrent]}>{s.label}</Text>
            </View>
          </View>
        ))}
      </View>
    </Card>
  );
}

function InvoiceSummaryCard({
  preview,
  conf,
  t,
}: {
  preview: InvoicePreview;
  conf: number;
  t: (k: string) => string;
}) {
  return (
    <Card style={styles.detailCard}>
      <SectionTitle title={t("invoiceDetailSummary")} subtitle={t("invoiceDetailSummarySub")} />
      {conf > 0 ? (
        <View style={styles.confBlock}>
          <Text style={styles.confLbl}>{t("confidence")}</Text>
          <ConfidenceBar value={conf} />
        </View>
      ) : null}
      <DefRow label={t("supplierLabel")} value={preview.supplier_name || "—"} />
      <DefRow label={t("invoiceNumber")} value={preview.invoice_number || "—"} />
      <DefRow label={t("invoiceDate")} value={preview.invoice_date || "—"} />
      <DefRow
        label={t("totalAmount")}
        value={
          preview.total_ttc != null || preview.totals?.ttc != null
            ? `${fmtTn(preview.total_ttc ?? preview.totals?.ttc ?? null)} ${preview.currency}`
            : "—"
        }
      />
      <DefRow
        label={t("netToPay")}
        value={`${fmtTn(preview.total_ttc ?? preview.totals?.ttc ?? null)} ${preview.currency}`}
      />
    </Card>
  );
}

export default function InvoiceDetailScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const segments = useSegments();
  const isDirectorContext = segments.includes("(tabs-director)");
  const { id } = useLocalSearchParams<{ id: string }>();
  const invoiceId = typeof id === "string" ? id : id?.[0] ?? "";
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<InvoicePreview | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const formatStatus = useCallback(
    (s: string) => {
      const map: Record<string, string> = {
        processing: t("invoiceStatusProcessing"),
        ready: t("invoiceStatusReady"),
        ready_for_review: t("invoiceStatusReadyForReview"),
        approved: t("invoiceStatusApproved"),
        rejected: t("invoiceStatusRejected"),
        failed: t("invoiceStatusFailed"),
      };
      return map[s] || s;
    },
    [t]
  );

  const { data: inv, isLoading } = useQuery({
    queryKey: queryKeys.invoiceDetail(invoiceId),
    queryFn: () => getInvoice(invoiceId),
    enabled: !!invoiceId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "processing" ? 2000 : false;
    },
  });

  const approveM = useMutation({
    mutationFn: (iid: string) => approveInvoice(iid),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("approveSuccess") });
      void queryClient.invalidateQueries({ queryKey: queryKeys.invoiceDetail(invoiceId) });
      void queryClient.invalidateQueries({ queryKey: ["invoices-list"] });
    },
    onError: (e: unknown) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    },
  });

  const rejectM = useMutation({
    mutationFn: ({ iid, reason }: { iid: string; reason: string }) => rejectInvoice(iid, reason),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("rejectSuccess") });
      setRejectOpen(false);
      setRejectReason("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.invoiceDetail(invoiceId) });
      void queryClient.invalidateQueries({ queryKey: ["invoices-list"] });
    },
    onError: (e: unknown) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    },
  });

  useEffect(() => {
    if (!inv || !invoiceId) return;
    const loadPreview = async () => {
      if (inv.status !== "ready" && inv.status !== "ready_for_review" && inv.status !== "approved") {
        setPreview(null);
        return;
      }
      try {
        const p = await getInvoicePreview(invoiceId);
        setPreview(p);
      } catch {
        setPreview(null);
      }
    };
    void loadPreview();
  }, [invoiceId, inv]);

  const downloadPdf = async () => {
    if (!invoiceId) return;
    try {
      const token = await getStoredToken();
      const url = getInvoicePdfUrl(invoiceId);
      const path = `${FileSystem.cacheDirectory}invoice_${invoiceId}.pdf`;
      await FileSystem.downloadAsync(url, path, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(path, { mimeType: "application/pdf", dialogTitle: t("downloadPdf") });
      } else {
        Linking.openURL(path);
      }
    } catch (e: unknown) {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    }
  };

  const canPdf =
    inv && (inv.status === "ready" || inv.status === "ready_for_review" || inv.status === "approved");

  const canApprove = inv && (inv.status === "ready" || inv.status === "ready_for_review");
  const canReject = inv && (canApprove || inv.status === "processing");

  const conf = useMemo(
    () => (preview ? preview.global_confidence ?? preview.confidence ?? 0 : 0),
    [preview]
  );

  const invalidateBack = () => {
    if (isDirectorContext) {
      void queryClient.invalidateQueries({ queryKey: ["invoices-list"] });
    } else {
      void queryClient.invalidateQueries({ queryKey: queryKeys.invoicesMe });
    }
  };

  if (!invoiceId) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{t("error")}</Text>
      </View>
    );
  }

  if (isLoading || !inv) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.skeletonContent}>
        {isDirectorContext ? <AdminAccentStripe /> : null}
        <ProductBrandMark title={t("appName")} subtitle={t("invoiceDetail")} />
        <InvoiceListSkeleton count={4} />
      </ScrollView>
    );
  }

  const summaryBlock =
    preview ? <InvoiceSummaryCard preview={preview} conf={conf} t={t} /> : null;

  const decisionBlock =
    isDirectorContext && (canApprove || canReject) ? (
      <AdminDecisionCard title={t("adminReviewTitle")} subtitle={t("adminReviewSubtitle")}>
        {canApprove ? (
          <PrimaryButton
            title={t("approve")}
            onPress={() => approveM.mutate(invoiceId)}
            loading={approveM.isPending}
            disabled={approveM.isPending || rejectM.isPending}
            icon="checkmark-circle-outline"
          />
        ) : null}
        {canReject ? (
          <DestructiveOutlineButton
            title={t("reject")}
            onPress={() => setRejectOpen(true)}
            icon="close-circle-outline"
          />
        ) : null}
      </AdminDecisionCard>
    ) : null;

  const timelineBlock = <InvoiceTimeline status={inv.status} createdAt={inv.created_at} hasPreview={!!preview} t={t} />;

  const errorBlock =
    inv.error_message ? (
      <Card style={styles.errorCard}>
        <View style={styles.errorRow}>
          <Ionicons name="alert-circle" size={22} color={colors.error} />
          <Text style={styles.errorTxt}>{inv.error_message}</Text>
        </View>
      </Card>
    ) : null;

  const processingBlock =
    inv.status === "processing" ? (
      <Card style={styles.processingCard}>
        <View style={styles.loadingRow}>
          <ActivityIndicator color={colors.primary} />
          <Text style={styles.processingTxt}>{t("invoiceDetailProcessingHint")}</Text>
        </View>
      </Card>
    ) : null;

  const warningsBlock =
    isDirectorContext && preview?.warnings?.length ? (
      <Card style={styles.warnCard}>
        <AdminSectionLabel>{t("alerts")}</AdminSectionLabel>
        {preview.warnings.map((w, i) => (
          <Text key={`${i}-${w.slice(0, 24)}`} style={styles.warnLine}>
            • {w}
          </Text>
        ))}
      </Card>
    ) : null;

  return (
    <>
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {isDirectorContext ? <AdminAccentStripe /> : null}
        <TouchableOpacity
          style={styles.backRow}
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel={t("back")}
        >
          <Ionicons name="arrow-back" size={22} color={colors.primary} />
          <Text style={styles.backText}>{t("back")}</Text>
        </TouchableOpacity>

        <ProductBrandMark title={t("appName")} subtitle={t("invoiceDetail")} />

        <View style={[styles.heroRow, isDirectorContext && styles.heroRowAdmin]}>
          <View style={styles.heroTextCol}>
            <Text style={[styles.heroTitle, isDirectorContext && styles.heroTitleAdmin]}>
              {preview?.supplier_name || preview?.invoice_number || t("invoiceDetail")}
            </Text>
            {preview?.invoice_number ? <Text style={styles.heroSub}>N° {preview.invoice_number}</Text> : null}
          </View>
          <StatusPill label={formatStatus(inv.status)} tone={invoiceStatusTone(inv.status)} />
        </View>

        {isDirectorContext ? (
          <>
            {summaryBlock}
            {warningsBlock}
            {decisionBlock}
            {timelineBlock}
            {errorBlock}
            {processingBlock}
          </>
        ) : (
          <>
            {timelineBlock}
            {errorBlock}
            {processingBlock}
            {summaryBlock}
          </>
        )}

        <View style={[styles.actionsCard, isDirectorContext && styles.actionsCardAdmin]}>
          <Text style={styles.actionsTitle}>{t("invoiceDetailActions")}</Text>
          {canPdf ? (
            <PrimaryButton title={t("downloadPdf")} onPress={() => void downloadPdf()} icon="document-attach-outline" />
          ) : (
            <View style={styles.actionDisabledWrap}>
              <Ionicons name="lock-closed-outline" size={18} color={colors.textMuted} />
              <Text style={styles.actionDisabledTxt}>{t("invoiceDetailPdfLocked")}</Text>
            </View>
          )}
          <SecondaryButton
            title={t("invoiceDetailBackToList")}
            onPress={() => {
              invalidateBack();
              router.back();
            }}
            icon="receipt-outline"
          />
        </View>
      </ScrollView>

      <Modal visible={rejectOpen} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>{t("rejectionReason")}</Text>
            <TextInput
              style={styles.modalInput}
              value={rejectReason}
              onChangeText={setRejectReason}
              placeholder={t("rejectionReason")}
              placeholderTextColor={colors.textMuted}
              multiline
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnDanger, (!rejectReason.trim() || rejectM.isPending) && styles.modalBtnDim]}
                onPress={() => {
                  const r = rejectReason.trim();
                  if (r) rejectM.mutate({ iid: invoiceId, reason: r });
                }}
                disabled={!rejectReason.trim() || rejectM.isPending}
                accessibilityRole="button"
              >
                {rejectM.isPending ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.modalBtnTxt}>{t("reject")}</Text>
                )}
              </TouchableOpacity>
              <SecondaryButton
                title={t("cancel")}
                onPress={() => {
                  setRejectOpen(false);
                  setRejectReason("");
                }}
              />
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, paddingBottom: space.xxxl, gap: space.md },
  skeletonContent: { padding: space.lg, paddingBottom: space.xxxl },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  backRow: { flexDirection: "row", alignItems: "center", gap: space.sm, marginBottom: space.xs },
  backText: { fontSize: font.md, color: colors.primary, fontWeight: font.semibold },
  heroRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: space.md,
    marginBottom: space.sm,
  },
  heroRowAdmin: {
    padding: space.md,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    ...shadow.card,
  },
  heroTextCol: { flex: 1, minWidth: 0 },
  heroTitle: { fontSize: font.xxl, fontWeight: font.bold, color: colors.primaryDark, letterSpacing: -0.3 },
  heroTitleAdmin: { fontSize: font.display, letterSpacing: -0.6 },
  heroSub: { fontSize: font.sm, color: colors.textMuted, marginTop: space.xs },
  timelineCard: { ...shadow.soft },
  timelineTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.text, marginBottom: space.xs },
  timelineMeta: { fontSize: font.xs, color: colors.textMuted, marginBottom: space.md },
  timelineTrack: { marginTop: space.xs },
  timelineStep: { flexDirection: "row", minHeight: 56 },
  timelineCol: { width: 28, alignItems: "center" },
  timelineDot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  timelineDotDone: { backgroundColor: colors.primary, borderColor: colors.primary },
  timelineDotCurrent: { borderColor: colors.accent, backgroundColor: colors.accentSoft },
  timelineLine: { flex: 1, width: 2, backgroundColor: colors.border, marginVertical: 2, minHeight: 20 },
  timelineLineDone: { backgroundColor: colors.primaryMuted },
  timelineBody: { flex: 1, paddingLeft: space.sm, paddingBottom: space.sm },
  timelineLabel: { fontSize: font.sm, color: colors.textMuted, fontWeight: font.medium },
  timelineLabelCurrent: { color: colors.text, fontWeight: font.bold },
  errorCard: { borderColor: colors.error, backgroundColor: colors.errorSoft },
  errorRow: { flexDirection: "row", gap: space.sm, alignItems: "flex-start" },
  errorTxt: { flex: 1, fontSize: font.sm, color: colors.error, lineHeight: 20 },
  processingCard: { backgroundColor: colors.infoSoft, borderColor: colors.info },
  loadingRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  processingTxt: { flex: 1, fontSize: font.sm, color: colors.textSecondary, lineHeight: 20 },
  warnCard: { borderColor: colors.warning, backgroundColor: colors.warningSoft },
  warnLine: { fontSize: font.sm, color: colors.textSecondary, marginTop: space.xs, lineHeight: 20 },
  detailCard: { gap: 0 },
  confBlock: { marginBottom: space.md },
  confLbl: { fontSize: font.xs, fontWeight: font.bold, color: colors.textMuted, marginBottom: space.xs },
  defRow: {
    paddingVertical: space.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  defLabel: { fontSize: font.xs, fontWeight: font.bold, color: colors.textMuted, marginBottom: 4 },
  defValue: { fontSize: font.md, color: colors.text, fontWeight: font.semibold },
  actionsCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: 1,
    borderColor: colors.border,
    gap: space.md,
    ...shadow.card,
  },
  actionsCardAdmin: { borderColor: colors.borderStrong },
  actionsTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.primaryDark },
  actionDisabledWrap: { flexDirection: "row", alignItems: "center", gap: space.sm, paddingVertical: space.sm },
  actionDisabledTxt: { fontSize: font.sm, color: colors.textMuted, flex: 1 },
  muted: { color: colors.textMuted, fontSize: font.sm },
  modalOverlay: {
    flex: 1,
    backgroundColor: colors.overlay,
    justifyContent: "center",
    padding: space.lg,
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: space.xl,
  },
  modalTitle: { fontSize: font.lg, fontWeight: font.bold, color: colors.primaryDark, marginBottom: space.md },
  modalInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: space.md,
    fontSize: font.md,
    minHeight: 88,
    textAlignVertical: "top",
    marginBottom: space.md,
  },
  modalActions: { gap: space.sm },
  modalBtn: {
    paddingVertical: space.md,
    borderRadius: radius.lg,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  modalBtnDanger: { backgroundColor: colors.error },
  modalBtnDim: { opacity: 0.55 },
  modalBtnTxt: { color: "#fff", fontWeight: font.bold, fontSize: font.md },
});
