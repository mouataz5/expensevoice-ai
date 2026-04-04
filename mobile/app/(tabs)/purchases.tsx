import { useQuery } from "@tanstack/react-query";
import { View, Text, StyleSheet, FlatList, RefreshControl, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, shadow, space } from "../../src/theme/tokens";
import { listMyPurchases, type PurchaseOut } from "../../src/api/purchases";
import { queryKeys } from "../../src/queryKeys";
import {
  EmptyState,
  ErrorState,
  StatusPill,
  InvoiceListSkeleton,
  ProductBrandMark,
} from "../../src/components/ui";
import { formatApiError } from "../../src/utils/apiError";
function purchaseChipMeta(item: PurchaseOut): { label: string; tone: "neutral" | "success" | "warning" | "danger" | "info" } {
  if (item.processing_status === "processing") {
    return { label: "__voiceSttProcessing__", tone: "info" };
  }
  if (item.processing_status === "ready_for_review" && item.status === "pending") {
    return { label: "__readyForReview__", tone: "warning" };
  }
  if (item.status === "approved") return { label: item.status, tone: "success" };
  if (item.status === "rejected") return { label: item.status, tone: "danger" };
  if (item.status === "ready_for_review") return { label: item.status, tone: "warning" };
  return { label: item.status, tone: "neutral" };
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
  const meta = purchaseChipMeta(item);
  const chipText =
    meta.label === "__voiceSttProcessing__"
      ? t("voiceSttProcessing")
      : meta.label === "__readyForReview__"
        ? t("readyForReview")
        : meta.label;
  return (
    <TouchableOpacity style={styles.rowWrap} onPress={onPress} activeOpacity={0.92}>
      <View style={styles.row}>
        <Text style={styles.rowTitle} numberOfLines={1}>
          {item.product_name || "—"}
        </Text>
        <Text style={styles.rowMeta}>
          {item.category ?? "—"} · {item.quantity} × {item.unit_price}
        </Text>
        <View style={styles.rowBottom}>
          <Text style={styles.rowAmount}>{item.total_amount} TND</Text>
          <StatusPill label={chipText} tone={meta.tone} />
        </View>
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

  const errFmt = error ? formatApiError(error, t) : null;

  if (isLoading) {
    return (
      <View style={styles.container}>
        <View style={styles.listPad}>
          <ProductBrandMark title={t("appName")} subtitle={t("myPurchases")} />
        </View>
        <InvoiceListSkeleton count={6} />
      </View>
    );
  }

  if (error && errFmt) {
    return (
      <ErrorState
        title={t("error")}
        message={errFmt.message}
        hint={errFmt.hint}
        onRetry={() => refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  if (!purchases?.length) {
    return (
      <FlatList
        data={[]}
        renderItem={() => <View />}
        ListHeaderComponent={
          <View style={styles.listPad}>
            <ProductBrandMark title={t("appName")} subtitle={t("myPurchases")} />
          </View>
        }
        ListEmptyComponent={
          <EmptyState
            icon="cart-outline"
            title={t("noPurchases")}
            subtitle={t("emptyPurchasesBody")}
            primaryCtaTitle={t("emptyPurchasesCtaPrimary")}
            onPrimaryCta={() => router.push("/(tabs)/record")}
            secondaryCtaTitle={t("emptyPurchasesCtaSecondary")}
            onSecondaryCta={() => router.push("/(tabs)/voice-studio")}
          />
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
      ListHeaderComponent={
        <View style={styles.listPad}>
          <ProductBrandMark title={t("appName")} subtitle={t("myPurchases")} />
        </View>
      }
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
  listPad: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm },
  list: { padding: space.lg, paddingBottom: space.xxxl },
  listFlex: { flexGrow: 1 },
  rowWrap: { marginBottom: space.md },
  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow.card,
  },
  rowTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.text, marginBottom: space.xs },
  rowMeta: { fontSize: font.sm, color: colors.textMuted, marginBottom: space.sm },
  rowBottom: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: space.sm },
  rowAmount: { fontSize: font.lg, fontWeight: font.bold, color: colors.primary },
});
