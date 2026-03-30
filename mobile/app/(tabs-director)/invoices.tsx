import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  TouchableOpacity,
  Modal,
  TextInput,
  ScrollView,
} from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
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

export default function DirectorInvoicesScreen() {
  const { t } = useLocale();
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const { data: invoices = [], isLoading, error, refetch } = useQuery({
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
      Toast.show({ type: "success", text1: t("alertsResolved") });
      qc.invalidateQueries({ queryKey: ["invoices-list"] });
    },
    onError: () => Toast.show({ type: "error", text1: t("error") }),
  });

  const rejectM = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      rejectInvoice(id, reason),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("alertsResolved") });
      setRejectId(null);
      setRejectReason("");
      qc.invalidateQueries({ queryKey: ["invoices-list"] });
    },
    onError: () => Toast.show({ type: "error", text1: t("error") }),
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
    } catch (e) {
      Toast.show({ type: "error", text1: t("error") });
    }
  };

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{t("error")}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryBtnText} pointerEvents="none">
            {t("retry")}
          </Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{t("invoices")}</Text>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filterScroll}
        contentContainerStyle={styles.filterContent}
      >
        {STATUS_OPTIONS.map((opt) => (
            <TouchableOpacity
              key={opt.value || "all"}
              style={[
                styles.filterChip,
                statusFilter === opt.value && styles.filterChipActive,
              ]}
              onPress={() => setStatusFilter(opt.value)}
            >
              <Text
                style={[
                  styles.filterChipText,
                  statusFilter === opt.value && styles.filterChipTextActive,
                ]}
                pointerEvents="none"
              >
                {t(opt.labelKey)}
              </Text>
            </TouchableOpacity>
          ))}
      </ScrollView>

      {invoices.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>{t("noInvoices")}</Text>
        </View>
      ) : (
        <FlatList
          data={invoices}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <InvoiceRow
              item={item}
              t={t}
              onApprove={() => approveM.mutate(item.id)}
              onReject={() => setRejectId(item.id)}
              onDownload={() => handleDownloadPdf(item.id)}
              approvePending={approveM.isPending}
            />
          )}
        />
      )}

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
    </View>
  );
}

function InvoiceRow({
  item,
  t,
  onApprove,
  onReject,
  onDownload,
  approvePending,
}: {
  item: InvoiceListItem;
  t: (k: string) => string;
  onApprove: () => void;
  onReject: () => void;
  onDownload: () => void;
  approvePending: boolean;
}) {
  const canApprove =
    item.status === "ready" || item.status === "ready_for_review";
  const canReject = canApprove || item.status === "processing";
  const canDownload =
    item.status === "ready" || item.status === "approved";

  const dateStr = item.created_at
    ? new Date(item.created_at).toLocaleDateString()
    : "—";
  const totalStr =
    item.total_ttc != null
      ? new Intl.NumberFormat(undefined, {
          minimumFractionDigits: 2,
        }).format(item.total_ttc)
      : "—";

  return (
    <View style={styles.row}>
      <View style={styles.rowMain}>
        <Text style={styles.rowSupplier} numberOfLines={1}>
          {item.supplier_name ?? "—"}
        </Text>
        <Text style={styles.rowMeta}>
          {item.employee_email} · #{item.invoice_number ?? "—"}
        </Text>
        <View style={styles.rowFooter}>
          <Text style={styles.rowTotal}>{totalStr} TND</Text>
          <View style={[styles.badge, styles[`badge_${item.status}` as keyof typeof styles] || styles.badge]}>
            <Text style={styles.badgeText}>{item.status}</Text>
          </View>
        </View>
        <Text style={styles.rowDate}>{dateStr}</Text>
      </View>
      <View style={styles.rowActions}>
        {canDownload && (
          <TouchableOpacity style={styles.actionBtn} onPress={onDownload}>
            <Text style={styles.actionBtnText} pointerEvents="none">
              {t("downloadPdf")}
            </Text>
          </TouchableOpacity>
        )}
        {canApprove && (
          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnPrimary]}
            onPress={onApprove}
            disabled={approvePending}
          >
            <Text style={styles.actionBtnTextPrimary} pointerEvents="none">
              {t("approve")}
            </Text>
          </TouchableOpacity>
        )}
        {canReject && (
          <TouchableOpacity style={styles.actionBtn} onPress={onReject}>
            <Text style={styles.actionBtnText} pointerEvents="none">
              {t("reject")}
            </Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background,
    padding: 24,
  },
  errorText: { fontSize: 18, color: colors.error, marginBottom: 12 },
  retryBtn: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: colors.primary,
    borderRadius: 12,
  },
  retryBtnText: { color: "#fff", fontWeight: "600" },
  header: { padding: 16, paddingBottom: 8 },
  title: { fontSize: 20, fontWeight: "700", color: colors.primary },
  filterScroll: { maxHeight: 44 },
  filterContent: {
    paddingHorizontal: 16,
    gap: 8,
    flexDirection: "row",
    paddingBottom: 12,
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.surfaceMuted,
  },
  filterChipActive: { backgroundColor: colors.primary },
  filterChipText: { fontSize: 14, color: colors.text },
  filterChipTextActive: { color: "#fff", fontWeight: "600" },
  list: { padding: 16, paddingBottom: 40 },
  empty: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  emptyTitle: { fontSize: 16, color: colors.textMuted },
  row: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowMain: { marginBottom: 12 },
  rowSupplier: { fontSize: 16, fontWeight: "600", color: colors.text },
  rowMeta: { fontSize: 14, color: colors.textMuted, marginTop: 4 },
  rowFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 8,
  },
  rowTotal: { fontSize: 15, fontWeight: "600", color: colors.primary },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    backgroundColor: colors.surfaceMuted,
  },
  badgeText: { fontSize: 12, color: colors.text },
  badge_ready: { backgroundColor: colors.accentMuted },
  badge_approved: { backgroundColor: colors.success },
  badge_rejected: { backgroundColor: "#FEE2E2" },
  badge_failed: { backgroundColor: "#FEE2E2" },
  badge_processing: { backgroundColor: "#FEF3C7" },
  rowDate: { fontSize: 12, color: colors.textMuted, marginTop: 4 },
  rowActions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  actionBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionBtnText: { fontSize: 14, color: colors.text },
  actionBtnPrimary: { backgroundColor: colors.primary, borderColor: colors.primary },
  actionBtnTextPrimary: { fontSize: 14, color: "#fff", fontWeight: "600" },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    padding: 24,
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: 24,
  },
  modalTitle: { fontSize: 18, fontWeight: "700", color: colors.primary, marginBottom: 16 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    minHeight: 80,
    textAlignVertical: "top",
    marginBottom: 16,
  },
  modalActions: { flexDirection: "row", gap: 12 },
  modalBtn: { flex: 1, paddingVertical: 14, borderRadius: 12, alignItems: "center" },
  modalBtnDanger: { backgroundColor: colors.error },
  modalBtnSecondary: { borderWidth: 1, borderColor: colors.border },
  modalBtnText: { color: "#fff", fontWeight: "600", fontSize: 16 },
  modalBtnTextSecondary: { color: colors.text, fontSize: 16 },
});
