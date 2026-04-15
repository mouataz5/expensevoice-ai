import { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, shadow, space } from "../../src/theme/tokens";
import { listMyInvoices, type InvoiceFilterParams, type InvoiceListItem } from "../../src/api/invoices";
import { queryKeys } from "../../src/queryKeys";
import {
  EmptyState,
  ErrorState,
  StatusPill,
  invoiceStatusTone,
  TextFieldInput,
  FilterSheet,
  type ListFilterState,
  InvoiceListSkeleton,
  ProductBrandMark,
} from "../../src/components/ui";
import { formatApiError } from "../../src/utils/apiError";

function fmtAmount(val: number | null | undefined): string {
  if (val == null || Number.isNaN(val)) return "—";
  return new Intl.NumberFormat("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(val);
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
  const tone = invoiceStatusTone(item.status);
  return (
    <TouchableOpacity
      style={styles.rowWrap}
      onPress={onPress}
      activeOpacity={0.92}
      accessibilityLabel={`Invoice ${item.invoice_number ?? item.id}`}
      accessibilityRole="button"
    >
      <View style={styles.row}>
        <View style={styles.rowHeader}>
          <Text style={styles.rowTitle} numberOfLines={1}>
            {item.supplier_name || item.invoice_number || "—"}
          </Text>
          <Ionicons name="chevron-forward" size={20} color={colors.textSubtle} />
        </View>
        {item.invoice_number ? <Text style={styles.rowMeta}>N° {item.invoice_number}</Text> : null}
        <View style={styles.rowMid}>
          <StatusPill label={formatStatus(item.status)} tone={tone} />
          <Text style={styles.rowAmount}>
            {item.total_ttc != null ? `${fmtAmount(item.total_ttc)} TND` : "—"}
          </Text>
        </View>
        <Text style={styles.rowDate}>{new Date(item.created_at).toLocaleString()}</Text>
      </View>
    </TouchableOpacity>
  );
}

export default function EmployeeInvoicesScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<ListFilterState>({});
  const [debouncedQ, setDebouncedQ] = useState("");
  useEffect(() => {
    const timer = setTimeout(
      () => setDebouncedQ((filters.q ?? query ?? "").trim()),
      300
    );
    return () => clearTimeout(timer);
  }, [filters.q, query]);

  const apiParams = useMemo<InvoiceFilterParams>(() => {
    const toNum = (v?: string) => (v && v.trim() ? Number(v.replace(",", ".")) : undefined);
    return {
      q: debouncedQ || undefined,
      status: filters.status || statusFilter || undefined,
      transaction_type: (filters.transaction_type || undefined) as "buy" | "sell" | undefined,
      source: (filters.source || undefined) as "scan" | "voice" | "manual" | undefined,
      ht_min: toNum(filters.ht_min),
      ht_max: toNum(filters.ht_max),
      tva_min: toNum(filters.tva_min),
      tva_max: toNum(filters.tva_max),
      ttc_min: toNum(filters.ttc_min),
      ttc_max: toNum(filters.ttc_max),
      limit: 200,
    };
  }, [debouncedQ, filters, statusFilter]);

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
    queryKey: queryKeys.invoicesMeFiltered(apiParams),
    queryFn: () => listMyInvoices(apiParams),
  });

  const statusOptions = useMemo(() => {
    const uniq = new Set<string>();
    (invoices ?? []).forEach((i) => uniq.add(i.status));
    return ["", ...Array.from(uniq).sort()];
  }, [invoices]);

  const filteredInvoices = useMemo(() => invoices ?? [], [invoices]);

  const errFmt = error ? formatApiError(error, t) : null;

  const listHeader = (
    <View style={styles.listHeader}>
      <ProductBrandMark title={t("appName")} subtitle={t("myInvoices")} />
      <TextFieldInput
        value={query}
        onChangeText={(v) => {
          setQuery(v);
          setFilters((prev) => ({ ...prev, q: v }));
        }}
        placeholder={t("invoiceSearchPlaceholder")}
        accessibilityLabel={t("invoiceSearchPlaceholder")}
      />
      <TouchableOpacity style={styles.filterBtn} onPress={() => setFilterVisible(true)}>
        <Text style={styles.filterBtnText}>Filtres avancés</Text>
      </TouchableOpacity>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipsRow}
        style={styles.chipsScroll}
      >
        {statusOptions.map((st) => (
          <TouchableOpacity
            key={st || "all"}
            style={[styles.chip, statusFilter === st && styles.chipOn]}
            onPress={() => setStatusFilter(st)}
            accessibilityRole="button"
            accessibilityState={{ selected: statusFilter === st }}
          >
            <Text style={[styles.chipTxt, statusFilter === st && styles.chipTxtOn]}>
              {st ? formatStatus(st) : t("invoiceStatusAll")}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );

  if (isLoading) {
    return (
      <View style={styles.container}>
        <View style={[styles.listHeader, { paddingBottom: 0 }]}>
          <ProductBrandMark title={t("appName")} subtitle={t("myInvoices")} />
        </View>
        <InvoiceListSkeleton count={7} />
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

  if (!invoices?.length) {
    return (
      <FlatList
        data={[]}
        renderItem={() => null}
        ListHeaderComponent={
          <View style={styles.listHeader}>
            <ProductBrandMark title={t("appName")} subtitle={t("myInvoices")} />
          </View>
        }
        ListEmptyComponent={
          <EmptyState
            icon="receipt-outline"
            title={t("noInvoices")}
            subtitle={t("emptyInvoicesBody")}
            primaryCtaTitle={t("emptyInvoicesCtaPrimary")}
            onPrimaryCta={() => router.push("/(tabs)/scan")}
            secondaryCtaTitle={t("emptyInvoicesCtaSecondary")}
            onSecondaryCta={() => router.push("/(tabs)/record")}
          />
        }
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        contentContainerStyle={styles.listFlex}
        style={styles.container}
      />
    );
  }

  return (
    <>
      <FlatList
        data={filteredInvoices}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={listHeader}
        ListEmptyComponent={
          <EmptyState icon="search-outline" title={t("noSearchResults")} subtitle={t("noSearchResultsHint")} />
        }
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
      <FilterSheet
        title="Filtres factures"
        visible={filterVisible}
        onClose={() => setFilterVisible(false)}
        value={filters}
        onApply={setFilters}
        statusOptions={statusOptions.filter(Boolean)}
      />
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { paddingHorizontal: space.lg, paddingBottom: space.xxxl },
  listFlex: { flexGrow: 1, backgroundColor: colors.background },
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
  filterBtn: {
    alignSelf: "flex-start",
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: space.md,
    paddingVertical: space.xs + 2,
  },
  filterBtnText: { color: colors.primaryDark, fontWeight: font.semibold, fontSize: font.sm },
  rowWrap: { marginBottom: space.md },
  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow.card,
  },
  rowHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: space.xs },
  rowTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.text, flex: 1, marginRight: space.sm },
  rowMeta: { fontSize: font.sm, color: colors.textMuted, marginBottom: space.sm },
  rowMid: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: space.sm,
    flexWrap: "wrap",
    gap: space.sm,
  },
  rowAmount: { fontSize: font.md, fontWeight: font.bold, color: colors.primary },
  rowDate: { fontSize: font.xs, color: colors.textSubtle },
});
