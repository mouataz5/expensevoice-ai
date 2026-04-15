import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { View, Text, StyleSheet, FlatList, RefreshControl, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, shadow, space } from "../../src/theme/tokens";
import { listMyPurchases, type PurchaseFilterParams, type PurchaseOut } from "../../src/api/purchases";
import { queryKeys } from "../../src/queryKeys";
import {
  EmptyState,
  ErrorState,
  StatusPill,
  InvoiceListSkeleton,
  ProductBrandMark,
  FilterSheet,
  type ListFilterState,
} from "../../src/components/ui";
import { formatApiError } from "../../src/utils/apiError";
function purchaseChipMeta(item: PurchaseOut): { label: string; tone: "neutral" | "success" | "warning" | "danger" | "info" } {
  if (item.processing_status === "processing") {
    return { label: "__voiceSttProcessing__", tone: "info" };
  }
  if (item.processing_status === "ready_for_review" && item.status === "pending") {
    return { label: "__readyForReview__", tone: "warning" };
  }
  if (item.status === "pending_approval") return { label: "__pendingApproval__", tone: "info" };
  if (item.status === "approved") return { label: "__approved__", tone: "success" };
  if (item.status === "rejected") return { label: "__rejected__", tone: "danger" };
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
  const labelMap: Record<string, string> = {
    "__voiceSttProcessing__": t("voiceSttProcessing"),
    "__readyForReview__": t("readyForReview"),
    "__pendingApproval__": t("pendingApproval"),
    "__approved__": t("approved"),
    "__rejected__": t("rejected"),
  };
  const chipText = labelMap[meta.label] ?? meta.label;
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
  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<ListFilterState>({});
  const [debouncedQ, setDebouncedQ] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ((filters.q ?? "").trim()), 300);
    return () => clearTimeout(timer);
  }, [filters.q]);

  const apiParams = useMemo<PurchaseFilterParams>(() => {
    const toNum = (v?: string) => (v && v.trim() ? Number(v.replace(",", ".")) : undefined);
    const toInt = (v?: string) => (v && v.trim() ? Number.parseInt(v, 10) : undefined);
    return {
      q: debouncedQ || undefined,
      transaction_type: (filters.transaction_type || undefined) as "buy" | "sell" | undefined,
      status: filters.status || undefined,
      source: (filters.source || undefined) as "voice" | "manual" | "scan" | undefined,
      qty_min: toInt(filters.qty_min),
      qty_max: toInt(filters.qty_max),
      unit_price_min: toNum(filters.unit_price_min),
      unit_price_max: toNum(filters.unit_price_max),
      ht_min: toNum(filters.ht_min),
      ht_max: toNum(filters.ht_max),
      tva_min: toNum(filters.tva_min),
      tva_max: toNum(filters.tva_max),
      ttc_min: toNum(filters.ttc_min),
      ttc_max: toNum(filters.ttc_max),
      limit: 200,
    };
  }, [debouncedQ, filters]);

  const hasActiveFilters = Object.values(filters).some((v) => !!v);
  const { data: purchases, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.purchasesMeFiltered(apiParams),
    queryFn: () => listMyPurchases(apiParams),
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
      <>
        <FlatList
          data={[]}
          renderItem={() => <View />}
          ListHeaderComponent={
            <View style={styles.listPad}>
              <ProductBrandMark title={t("appName")} subtitle={t("myPurchases")} />
              <TouchableOpacity style={styles.filterBtn} onPress={() => setFilterVisible(true)}>
                <Text style={styles.filterBtnText}>
                  {hasActiveFilters ? "Filtres actifs" : "Filtres"}
                </Text>
              </TouchableOpacity>
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
              onSecondaryCta={() => router.push("/(tabs)/record")}
            />
          }
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
          contentContainerStyle={[styles.list, styles.listFlex]}
          style={styles.container}
        />
        <FilterSheet
          title="Filtres achats"
          visible={filterVisible}
          onClose={() => setFilterVisible(false)}
          value={filters}
          onApply={setFilters}
          allowQuantity
          statusOptions={[]}
        />
      </>
    );
  }

  return (
    <>
      <FlatList
        data={purchases}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={
          <View style={styles.listPad}>
            <ProductBrandMark title={t("appName")} subtitle={t("myPurchases")} />
            <TouchableOpacity style={styles.filterBtn} onPress={() => setFilterVisible(true)}>
              <Text style={styles.filterBtnText}>
                {hasActiveFilters ? "Filtres actifs" : "Filtres"}
              </Text>
            </TouchableOpacity>
          </View>
        }
        renderItem={({ item }) => (
          <PurchaseRow item={item} onPress={() => router.push(`/(tabs)/purchases/${item.id}`)} t={t} />
        )}
        contentContainerStyle={styles.list}
        style={styles.container}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      />
      <FilterSheet
        title="Filtres achats"
        visible={filterVisible}
        onClose={() => setFilterVisible(false)}
        value={filters}
        onApply={setFilters}
        allowQuantity
        statusOptions={Array.from(new Set((purchases ?? []).map((p) => p.status).filter(Boolean)))}
      />
    </>
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
  filterBtn: {
    alignSelf: "flex-start",
    marginTop: space.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: space.md,
    paddingVertical: space.xs + 2,
  },
  filterBtnText: { color: colors.primaryDark, fontWeight: font.semibold, fontSize: font.sm },
});
