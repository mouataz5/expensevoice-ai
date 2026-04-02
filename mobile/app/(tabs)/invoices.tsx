import { useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { listMyInvoices, type InvoiceListItem } from "../../src/api/invoices";
import { queryKeys } from "../../src/queryKeys";

function invoiceStatusColors(status: string): { bg: string; fg: string } {
  switch (status) {
    case "ready":
    case "ready_for_review":
      return { bg: colors.surfaceMuted, fg: colors.primary };
    case "approved":
      return { bg: "#DCFCE7", fg: colors.success };
    case "rejected":
    case "failed":
      return { bg: "#FEE2E2", fg: colors.error };
    case "processing":
      return { bg: "#FEF3C7", fg: colors.warning };
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted };
  }
}

function InvoiceRow({
  item,
  onPress,
  formatStatus,
}: {
  item: InvoiceListItem;
  onPress: () => void;
  formatStatus: (s: string) => string;
}) {
  const chip = invoiceStatusColors(item.status);
  return (
    <TouchableOpacity
      style={styles.row}
      onPress={onPress}
      accessibilityLabel={`Invoice ${item.invoice_number ?? item.id}`}
      accessibilityRole="button"
    >
      <View style={styles.rowTop}>
        <Text style={styles.rowTitle} numberOfLines={1}>
          {item.supplier_name || item.invoice_number || "—"}
        </Text>
        <Ionicons name="chevron-forward" size={20} color={colors.textMuted} />
      </View>
      {item.invoice_number ? <Text style={styles.rowMeta}>N° {item.invoice_number}</Text> : null}
      <View style={styles.rowBottom}>
        <View style={[styles.statusChip, { backgroundColor: chip.bg }]}>
          <Text style={[styles.statusChipText, { color: chip.fg }]}>{formatStatus(item.status)}</Text>
        </View>
        {item.total_ttc != null ? (
          <Text style={styles.rowAmount}>{item.total_ttc} TND</Text>
        ) : (
          <Text style={styles.rowAmountMuted}>—</Text>
        )}
      </View>
      <Text style={styles.rowDate}>{new Date(item.created_at).toLocaleString()}</Text>
    </TouchableOpacity>
  );
}

export default function EmployeeInvoicesScreen() {
  const { t } = useLocale();
  const router = useRouter();

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

  const { data: invoices, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.invoicesMe,
    queryFn: () => listMyInvoices({ limit: 100 }),
  });

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
        <Text style={styles.errorSub}>{String(error)}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()} accessibilityRole="button">
          <Text style={styles.retryBtnText}>{t("retry")}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!invoices?.length) {
    return (
      <ScrollView
        contentContainerStyle={styles.centeredGrow}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      >
        <Text style={styles.emptyTitle}>{t("noInvoices")}</Text>
        <Text style={styles.emptySub}>{t("emptyList")}</Text>
      </ScrollView>
    );
  }

  return (
    <FlatList
      data={invoices}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.list}
      style={styles.container}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      renderItem={({ item }) => (
        <InvoiceRow
          item={item}
          formatStatus={formatStatus}
          onPress={() =>
            router.push({
              pathname: "/invoice/[id]",
              params: { id: item.id },
            })
          }
        />
      )}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { padding: 16, paddingBottom: 40 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, backgroundColor: colors.background },
  centeredGrow: { flexGrow: 1, justifyContent: "center", alignItems: "center", padding: 24, backgroundColor: colors.background },
  row: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 6 },
  rowTitle: { fontSize: 16, fontWeight: "600", color: colors.text, flex: 1, marginRight: 8 },
  rowMeta: { fontSize: 14, color: colors.textMuted, marginBottom: 10 },
  rowBottom: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 8 },
  statusChip: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusChipText: { fontSize: 12, fontWeight: "600" },
  rowAmount: { fontSize: 15, fontWeight: "600", color: colors.primary },
  rowAmountMuted: { fontSize: 14, color: colors.textMuted },
  rowDate: { fontSize: 12, color: colors.textMuted },
  errorText: { fontSize: 18, color: colors.error, marginBottom: 8 },
  errorSub: { fontSize: 14, color: colors.textMuted, textAlign: "center", marginBottom: 16 },
  retryBtn: { backgroundColor: colors.primary, paddingHorizontal: 20, paddingVertical: 12, borderRadius: 12 },
  retryBtnText: { color: "#fff", fontWeight: "600" },
  emptyTitle: { fontSize: 18, fontWeight: "600", color: colors.text, marginBottom: 8 },
  emptySub: { fontSize: 14, color: colors.textMuted },
});
