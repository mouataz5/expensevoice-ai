import { useQuery } from "@tanstack/react-query";
import { View, Text, StyleSheet, FlatList, ActivityIndicator } from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { listMyPurchases, type PurchaseOut } from "../../src/api/purchases";

function PurchaseRow({ item }: { item: PurchaseOut }) {
  const { t } = useLocale();
  return (
    <View style={styles.row}>
      <Text style={styles.rowTitle} numberOfLines={1}>{item.product_name || "—"}</Text>
      <Text style={styles.rowMeta}>{item.category ?? ""} · {item.quantity} × {item.unit_price}</Text>
      <Text style={styles.rowAmount}>{item.total_amount} TND</Text>
      <Text style={styles.rowStatus}>{item.status}</Text>
    </View>
  );
}

export default function PurchasesScreen() {
  const { t } = useLocale();
  const { data: purchases, isLoading, error, refetch } = useQuery({
    queryKey: ["purchases"],
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
      <View style={styles.centered}>
        <Text style={styles.emptyTitle}>{t("noPurchases")}</Text>
        <Text style={styles.emptySub}>{t("emptyList")}</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={purchases}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <PurchaseRow item={item} />}
      contentContainerStyle={styles.list}
      style={styles.container}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { padding: 16, paddingBottom: 40 },
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
  rowStatus: { fontSize: 12, color: colors.textMuted, marginTop: 4 },
  errorText: { fontSize: 18, color: colors.error, marginBottom: 8 },
  errorSub: { fontSize: 14, color: colors.textMuted },
  emptyTitle: { fontSize: 18, fontWeight: "600", color: colors.text, marginBottom: 8 },
  emptySub: { fontSize: 14, color: colors.textMuted },
});
