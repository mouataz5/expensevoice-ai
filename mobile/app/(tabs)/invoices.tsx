import { useCallback, useMemo, useState } from "react";
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
import { listMyInvoices, type InvoiceListItem } from "../../src/api/invoices";
import { queryKeys } from "../../src/queryKeys";
import {
  EmptyState,
  ErrorState,
  StatusPill,
  invoiceStatusTone,
  TextFieldInput,
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

  const statusOptions = useMemo(() => {
    const uniq = new Set<string>();
    (invoices ?? []).forEach((i) => uniq.add(i.status));
    return ["", ...Array.from(uniq).sort()];
  }, [invoices]);

  const filteredInvoices = useMemo(() => {
    let list = invoices ?? [];
    if (statusFilter) list = list.filter((i) => i.status === statusFilter);
    const q = query.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (i) =>
          (i.supplier_name?.toLowerCase().includes(q) ?? false) ||
          (i.invoice_number?.toLowerCase().includes(q) ?? false) ||
          (i.employee_email?.toLowerCase().includes(q) ?? false)
      );
    }
    return list;
  }, [invoices, statusFilter, query]);

  const errFmt = error ? formatApiError(error, t) : null;

  const listHeader = (
    <View style={styles.listHeader}>
      <ProductBrandMark title={t("appName")} subtitle={t("myInvoices")} />
      <TextFieldInput
        value={query}
        onChangeText={setQuery}
        placeholder={t("invoiceSearchPlaceholder")}
        accessibilityLabel={t("invoiceSearchPlaceholder")}
      />
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
