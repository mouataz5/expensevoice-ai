import { useQuery } from "@tanstack/react-query";
import { View, Text, StyleSheet, FlatList, ActivityIndicator, RefreshControl, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { listMyPurchases, type PurchaseOut } from "../../src/api/purchases";
import { queryKeys } from "../../src/queryKeys";

function purchaseStatusColors(status: string): { bg: string; fg: string } {
  switch (status) {
    case "approved":
      return { bg: "#DCFCE7", fg: colors.success };
    case "ready_for_review":
      return { bg: "#FEF3C7", fg: colors.warning };
    case "rejected":
      return { bg: "#FEE2E2", fg: colors.error };
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted };
  }
}

function purchaseRowChip(item: PurchaseOut): { bg: string; fg: string; label: string } {
  if (item.processing_status === "processing") {
    return { bg: "#E0E7FF", fg: "#3730A3", label: "__voiceSttProcessing__" };
  }
  if (item.processing_status === "ready_for_review" && item.status === "pending") {
    const c = purchaseStatusColors("ready_for_review");
    return { ...c, label: "__readyForReview__" };
  }
  const c = purchaseStatusColors(item.status);
  return { ...c, label: item.status };
}

function PurchaseRow({
  item,
  onPress,
  t,
}: {
  item: PurchaseOut;
  onPress: () => void;
  t: (k: string) => string;
}) {
  const chip = purchaseRowChip(item);
  const chipText =
    chip.label === "__voiceSttProcessing__"
      ? t("voiceSttProcessing")
      : chip.label === "__readyForReview__"
        ? t("readyForReview")
        : chip.label;
  return (
    <TouchableOpacity style={styles.row} onPress={onPress} activeOpacity={0.85}>
      <Text style={styles.rowTitle} numberOfLines={1}>{item.product_name || "—"}</Text>
      <Text style={styles.rowMeta}>{item.category ?? ""} · {item.quantity} × {item.unit_price}</Text>
      <Text style={styles.rowAmount}>{item.total_amount} TND</Text>
      <View style={[styles.statusChip, { backgroundColor: chip.bg }]}>
        <Text style={[styles.statusChipText, { color: chip.fg }]}>{chipText}</Text>
      </View>
    </TouchableOpacity>
  );
}

export default function PurchasesScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const { data: purchases, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.purchasesMe,
    queryFn: listMyPurchases,
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
      </View>
    );
  }

  if (!purchases?.length) {
    return (
      <FlatList
        data={[]}
        renderItem={() => null}
        ListEmptyComponent={
          <View style={styles.centered}>
            <Text style={styles.emptyTitle}>{t("noPurchases")}</Text>
            <Text style={styles.emptySub}>{t("emptyList")}</Text>
          </View>
        }
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        contentContainerStyle={[styles.list, styles.listFlex]}
        style={styles.container}
      />
    );
  }

  return (
    <FlatList
      data={purchases}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <PurchaseRow item={item} onPress={() => router.push(`/(tabs)/purchases/${item.id}`)} t={t} />
      )}
      contentContainerStyle={styles.list}
      style={styles.container}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { padding: 16, paddingBottom: 40 },
  listFlex: { flexGrow: 1 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, backgroundColor: colors.background },
  row: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowTitle: { fontSize: 16, fontWeight: "600", color: colors.text, marginBottom: 4 },
  rowMeta: { fontSize: 14, color: colors.textMuted, marginBottom: 4 },
  rowAmount: { fontSize: 15, fontWeight: "600", color: colors.primary },
  statusChip: { alignSelf: "flex-start", marginTop: 8, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusChipText: { fontSize: 12, fontWeight: "600" },
  errorText: { fontSize: 18, color: colors.error, marginBottom: 8 },
  errorSub: { fontSize: 14, color: colors.textMuted },
  emptyTitle: { fontSize: 18, fontWeight: "600", color: colors.text, marginBottom: 8 },
  emptySub: { fontSize: 14, color: colors.textMuted },
});
