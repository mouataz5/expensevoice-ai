import { useCallback, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Modal,
  TextInput,
  ScrollView,
  RefreshControl,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, shadow, space } from "../../src/theme/tokens";
import {
  EmptyState,
  ErrorState,
  InvoiceListSkeleton,
  PrimaryButton,
  ProductBrandMark,
  StatusPill,
  TextFieldInput,
  invoiceStatusTone,
} from "../../src/components/ui";
import { AdminAccentStripe, AdminErrorShell, AdminHeader } from "../../src/components/admin";
import { formatApiError } from "../../src/utils/apiError";
import {
  listInvoices,
  approveInvoice,
  rejectInvoice,
  fetchInvoicePdfBlob,
  type InvoiceListItem,
} from "../../src/api/invoices";
import Toast from "react-native-toast-message";

const STATUS_OPTIONS = [
  { value: "", labelKey: "invoiceStatusAll" },
  { value: "processing", labelKey: "invoiceStatusProcessing" },
  { value: "ready", labelKey: "invoiceStatusReady" },
  { value: "ready_for_review", labelKey: "invoiceStatusReadyForReview" },
  { value: "approved", labelKey: "invoiceStatusApproved" },
  { value: "rejected", labelKey: "invoiceStatusRejected" },
  { value: "failed", labelKey: "invoiceStatusFailed" },
];

function fmtAmount(val: number | null | undefined): string {
  if (val == null || Number.isNaN(val)) return "—";
  return new Intl.NumberFormat("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(val);
}

function InvoiceRow({
  item,
  t,
  formatStatus,
  onOpenDetail,
  onApprove,
  onReject,
  onDownload,
  approvePending,
}: {
  item: InvoiceListItem;
  t: (k: string) => string;
  formatStatus: (s: string) => string;
  onOpenDetail: () => void;
  onApprove: () => void;
  onReject: () => void;
  onDownload: () => void;
  approvePending: boolean;
}) {
  const canApprove = item.status === "ready" || item.status === "ready_for_review";
  const canReject = canApprove || item.status === "processing";
  const canDownload = item.status === "ready" || item.status === "approved";
  const needsReview = canApprove;
  const tone = invoiceStatusTone(item.status);
  const dateStr = item.created_at ? new Date(item.created_at).toLocaleString() : "—";

  return (
    <View style={styles.rowWrap}>
      <View style={[styles.row, needsReview && styles.rowPending]}>
        <TouchableOpacity
          style={styles.rowHeader}
          onPress={onOpenDetail}
          activeOpacity={0.92}
          accessibilityRole="button"
          accessibilityLabel={t("invoiceDetail")}
        >
          <View style={{ flex: 1, marginRight: space.sm }}>
            <Text style={styles.rowSupplier} numberOfLines={1}>
              {item.supplier_name ?? item.invoice_number ?? "—"}
            </Text>
            <Text style={styles.rowMeta} numberOfLines={1}>
              {item.employee_email} · #{item.invoice_number ?? "—"}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.textSubtle} />
        </TouchableOpacity>
        <View style={styles.rowMid}>
          <StatusPill label={formatStatus(item.status)} tone={tone} />
          <Text style={[styles.rowAmount, needsReview && styles.rowAmountEmphasis]}>
            {item.total_ttc != null ? `${fmtAmount(item.total_ttc)} TND` : "—"}
          </Text>
        </View>
        <Text style={styles.rowDate}>{dateStr}</Text>
        <View style={styles.rowActions}>
          {canDownload ? (
            <TouchableOpacity style={styles.actionBtn} onPress={onDownload}>
              <Text style={styles.actionBtnText} pointerEvents="none">
                {t("downloadPdf")}
              </Text>
            </TouchableOpacity>
          ) : null}
          {canApprove ? (
            <View style={styles.actionPrimaryWrap}>
              <PrimaryButton
                title={t("approve")}
                onPress={onApprove}
                loading={approvePending}
                disabled={approvePending}
                icon="checkmark-circle-outline"
              />
            </View>
          ) : null}
          {canReject ? (
            <TouchableOpacity style={styles.actionBtn} onPress={onReject}>
              <Text style={styles.actionBtnText} pointerEvents="none">
                {t("reject")}
              </Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </View>
    </View>
  );
}

export default function DirectorInvoicesScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [rejectId, setRejectId] = useState<string | null>(null);
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

  const { data: invoices = [], isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ["invoices-list", statusFilter],
    queryFn: () =>
      listInvoices({
        status: statusFilter || undefined,
        limit: 100,
      }),
  });

  const approveM = useMutation({
    mutationFn: (id: string) => approveInvoice(id),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("approveSuccess") });
      void qc.invalidateQueries({ queryKey: ["invoices-list"] });
    },
    onError: (e: unknown) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    },
  });

  const rejectM = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectInvoice(id, reason),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("rejectSuccess") });
      setRejectId(null);
      setRejectReason("");
      void qc.invalidateQueries({ queryKey: ["invoices-list"] });
    },
    onError: (e: unknown) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    },
  });

  const handleDownloadPdf = async (id: string) => {
    try {
      const blob = await fetchInvoicePdfBlob(id);
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64 = (reader.result as string)?.split(",")[1];
        if (!base64) return;
        const filename = `invoice_report_${id}.pdf`;
        const path = `${FileSystem.cacheDirectory}${filename}`;
        await FileSystem.writeAsStringAsync(path, base64, {
          encoding: FileSystem.EncodingType.Base64,
        });
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(path, {
            mimeType: "application/pdf",
            dialogTitle: filename,
          });
        }
      };
      reader.readAsDataURL(blob);
    } catch (e: unknown) {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    }
  };

  const displayedInvoices = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return invoices;
    return invoices.filter(
      (i) =>
        (i.supplier_name?.toLowerCase().includes(q) ?? false) ||
        (i.invoice_number?.toLowerCase().includes(q) ?? false) ||
        (i.employee_email?.toLowerCase().includes(q) ?? false)
    );
  }, [invoices, searchQuery]);

  const errFmt = error ? formatApiError(error, t) : null;

  const listHeader = (
    <View style={styles.listHeader}>
      <AdminAccentStripe />
      <ProductBrandMark title={t("appName")} subtitle={t("invoices")} />
      <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("adminInvoiceListSubtitle")} />
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.chipsScroll}
        contentContainerStyle={styles.chipsRow}
      >
        {STATUS_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.value || "all"}
            style={[styles.chip, statusFilter === opt.value && styles.chipOn]}
            onPress={() => setStatusFilter(opt.value)}
            accessibilityRole="button"
            accessibilityState={{ selected: statusFilter === opt.value }}
          >
            <Text style={[styles.chipTxt, statusFilter === opt.value && styles.chipTxtOn]}>
              {t(opt.labelKey)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <TextFieldInput
        value={searchQuery}
        onChangeText={setSearchQuery}
        placeholder={t("invoiceSearchPlaceholder")}
        accessibilityLabel={t("invoiceSearchPlaceholder")}
      />
    </View>
  );

  if (isLoading) {
    return (
      <View style={styles.container}>
        <View style={[styles.listHeader, { paddingBottom: 0 }]}>
          <AdminAccentStripe />
          <ProductBrandMark title={t("appName")} subtitle={t("invoices")} />
        </View>
        <InvoiceListSkeleton count={7} />
      </View>
    );
  }

  if (error && errFmt) {
    return (
      <AdminErrorShell>
        <ErrorState
          title={t("error")}
          message={errFmt.message}
          hint={errFmt.hint}
          onRetry={() => refetch()}
          retryLabel={t("retry")}
        />
      </AdminErrorShell>
    );
  }

  return (
    <>
      <FlatList
        data={displayedInvoices}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={listHeader}
        ListEmptyComponent={
          invoices.length === 0 ? (
            <EmptyState
              icon="receipt-outline"
              title={t("noInvoices")}
              subtitle={t("emptyDirectorInvoicesHint")}
              primaryCtaTitle={t("directorInvoicesEmptyCta")}
              onPrimaryCta={() => router.push("/(tabs-director)/alerts")}
              secondaryCtaTitle={t("directorEmptyAlertsCtaDashboard")}
              onSecondaryCta={() => router.push("/(tabs-director)")}
            />
          ) : (
            <EmptyState
              icon="search-outline"
              title={t("noSearchResults")}
              subtitle={t("noSearchResultsHint")}
            />
          )
        }
        contentContainerStyle={[styles.list, displayedInvoices.length === 0 && styles.listFlex]}
        style={styles.container}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }) => (
          <InvoiceRow
            item={item}
            t={t}
            formatStatus={formatStatus}
            onOpenDetail={() =>
              router.push({
                pathname: "/(tabs-director)/invoice/[id]",
                params: { id: item.id },
              })
            }
            onApprove={() => approveM.mutate(item.id)}
            onReject={() => setRejectId(item.id)}
            onDownload={() => handleDownloadPdf(item.id)}
            approvePending={approveM.isPending && approveM.variables === item.id}
          />
        )}
      />

      <Modal visible={!!rejectId} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>{t("rejectionReason")}</Text>
            <TextInput
              style={styles.input}
              value={rejectReason}
              onChangeText={setRejectReason}
              placeholder={t("rejectionReason")}
              placeholderTextColor={colors.textMuted}
              multiline
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnDanger]}
                onPress={() =>
                  rejectId &&
                  rejectReason.trim() &&
                  rejectM.mutate({ id: rejectId, reason: rejectReason.trim() })
                }
                disabled={!rejectReason.trim() || rejectM.isPending}
              >
                <Text style={styles.modalBtnText} pointerEvents="none">
                  {t("reject")}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnSecondary]}
                onPress={() => {
                  setRejectId(null);
                  setRejectReason("");
                }}
              >
                <Text style={styles.modalBtnTextSecondary} pointerEvents="none">
                  {t("cancel")}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { paddingHorizontal: space.lg, paddingBottom: space.xxxl },
  listFlex: { flexGrow: 1 },
  listHeader: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm, gap: space.md },
  chipsScroll: { marginHorizontal: -space.lg },
  chipsRow: { paddingHorizontal: space.lg, gap: space.sm, flexDirection: "row", alignItems: "center" },
  chip: {
    paddingHorizontal: space.md,
    paddingVertical: space.xs + 2,
    borderRadius: radius.full,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipOn: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  chipTxt: { fontSize: font.sm, fontWeight: font.semibold, color: colors.textSecondary },
  chipTxtOn: { color: colors.primaryDark },
  rowWrap: { marginBottom: space.md },
  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow.card,
  },
  rowPending: {
    borderLeftWidth: 4,
    borderLeftColor: colors.accent,
    borderColor: colors.borderStrong,
    backgroundColor: colors.backgroundElevated,
  },
  rowHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: space.xs },
  rowSupplier: { fontSize: font.md, fontWeight: font.bold, color: colors.text },
  rowMeta: { fontSize: font.sm, color: colors.textMuted, marginTop: space.xs },
  rowMid: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: space.sm,
    flexWrap: "wrap",
    gap: space.sm,
  },
  rowAmount: { fontSize: font.md, fontWeight: font.bold, color: colors.primary },
  rowAmountEmphasis: { fontSize: font.xl, color: colors.primaryDark },
  rowDate: { fontSize: font.xs, color: colors.textSubtle },
  rowActions: { flexDirection: "row", flexWrap: "wrap", gap: space.sm, marginTop: space.md },
  actionPrimaryWrap: { width: "100%", minWidth: 200 },
  actionBtn: {
    paddingHorizontal: space.md,
    paddingVertical: space.xs + 2,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionBtnText: { fontSize: font.sm, color: colors.text },
  actionBtnPrimary: { backgroundColor: colors.primary, borderColor: colors.primary },
  actionBtnTextPrimary: { fontSize: font.sm, color: "#fff", fontWeight: font.bold },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    padding: space.xl,
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: space.xl,
  },
  modalTitle: { fontSize: font.lg, fontWeight: font.bold, color: colors.primary, marginBottom: space.md },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: space.md,
    paddingVertical: space.md,
    fontSize: font.md,
    minHeight: 80,
    textAlignVertical: "top",
    marginBottom: space.md,
  },
  modalActions: { flexDirection: "row", gap: space.md },
  modalBtn: { flex: 1, paddingVertical: space.md, borderRadius: radius.lg, alignItems: "center" },
  modalBtnDanger: { backgroundColor: colors.error },
  modalBtnSecondary: { borderWidth: 1, borderColor: colors.border },
  modalBtnText: { color: "#fff", fontWeight: font.bold, fontSize: font.md },
  modalBtnTextSecondary: { color: colors.text, fontSize: font.md },
});
