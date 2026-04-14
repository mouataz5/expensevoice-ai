import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  View,
  Text,
  StyleSheet,
  SectionList,
  ScrollView,
  RefreshControl,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, shadow, space } from "../../src/theme/tokens";
import {
  listAllPurchases,
  approvePurchase,
  rejectPurchase,
  type PurchaseAllOut,
} from "../../src/api/purchases";
import { queryKeys } from "../../src/queryKeys";
import {
  EmptyState,
  ErrorState,
  StatusPill,
  InvoiceListSkeleton,
  ProductBrandMark,
  PrimaryButton,
  GhostButton,
} from "../../src/components/ui";
import {
  AdminAccentStripe,
  AdminErrorShell,
  AdminHeader,
} from "../../src/components/admin";
import { formatApiError } from "../../src/utils/apiError";
import Toast from "react-native-toast-message";

function statusTone(status: string): "success" | "warning" | "danger" | "neutral" | "info" {
  if (status === "approved") return "success";
  if (status === "rejected") return "danger";
  if (status === "pending_approval") return "warning";
  if (status === "pending") return "info";
  return "neutral";
}

function statusLabel(status: string, t: (k: string) => string): string {
  if (status === "pending_approval") return t("pendingApproval");
  if (status === "approved") return t("approved");
  if (status === "rejected") return t("rejected");
  return status;
}

function PurchaseRow({
  item,
  t,
  onApprove,
  onReject,
  approving,
  rejecting,
}: {
  item: PurchaseAllOut;
  t: (k: string) => string;
  onApprove: () => void;
  onReject: () => void;
  approving: boolean;
  rejecting: boolean;
}) {
  const email = item.employee_email ?? "—";
  const shortEmail = email.includes("@") ? email.split("@")[0] : email;
  const isPending = item.status === "pending_approval" || item.status === "pending";

  return (
    <View style={[styles.row, isPending && styles.rowPending]}>
      <View style={styles.rowTop}>
        <View style={[styles.avatarWrap, isPending && styles.avatarPending]}>
          <Ionicons
            name={isPending ? "time-outline" : "person-circle-outline"}
            size={36}
            color={isPending ? colors.warning : colors.primary}
          />
        </View>
        <View style={styles.rowBody}>
          <Text style={styles.rowProduct} numberOfLines={1}>
            {item.product_name || "—"}
          </Text>
          <Text style={styles.rowEmployee} numberOfLines={1}>
            {t("employeeLabel")}: {shortEmail}
          </Text>
          <Text style={styles.rowMeta}>
            {item.category ?? "—"} · {item.quantity} × {Number(item.unit_price).toFixed(2)}
          </Text>
        </View>
        <View style={styles.rowRight}>
          <Text style={styles.rowAmount}>{Number(item.total_amount).toFixed(2)}</Text>
          <Text style={styles.rowCurrency}>TND</Text>
        </View>
      </View>

      <View style={styles.rowFooter}>
        <StatusPill label={statusLabel(item.status, t)} tone={statusTone(item.status)} />
        <Text style={styles.rowDate}>
          {item.created_at ? new Date(item.created_at).toLocaleDateString() : ""}
        </Text>
      </View>

      {isPending && (
        <View style={styles.actionRow}>
          <View style={styles.actionBtn}>
            <PrimaryButton
              title={t("approve")}
              onPress={onApprove}
              loading={approving}
              disabled={approving || rejecting}
              icon="checkmark-circle-outline"
            />
          </View>
          <View style={styles.actionBtn}>
            <GhostButton
              title={t("reject")}
              onPress={onReject}
              loading={rejecting}
              disabled={approving || rejecting}
            />
          </View>
        </View>
      )}
    </View>
  );
}

export default function DirectorPurchasesScreen() {
  const { t } = useLocale();
  const qc = useQueryClient();
  const { data: purchases, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.purchasesAll,
    queryFn: listAllPurchases,
  });

  const approveM = useMutation({
    mutationFn: (id: string) => approvePurchase(id),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("purchaseApproved") });
      void qc.invalidateQueries({ queryKey: queryKeys.purchasesAll });
    },
    onError: (e) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    },
  });

  const rejectM = useMutation({
    mutationFn: (id: string) => rejectPurchase(id),
    onSuccess: () => {
      Toast.show({ type: "info", text1: t("purchaseRejected") });
      void qc.invalidateQueries({ queryKey: queryKeys.purchasesAll });
    },
    onError: (e) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    },
  });

  const sections = useMemo(() => {
    if (!purchases?.length) return [];
    const pending = purchases.filter(
      (p) => p.status === "pending_approval" || p.status === "pending"
    );
    const approved = purchases.filter((p) => p.status === "approved");
    const rejected = purchases.filter((p) => p.status === "rejected");
    const other = purchases.filter(
      (p) => !["pending_approval", "pending", "approved", "rejected"].includes(p.status)
    );
    const out: { title: string; data: PurchaseAllOut[] }[] = [];
    if (pending.length)
      out.push({ title: `${t("pendingApproval")} (${pending.length})`, data: pending });
    if (approved.length)
      out.push({ title: `${t("approved")} (${approved.length})`, data: approved });
    if (rejected.length)
      out.push({ title: `${t("rejected")} (${rejected.length})`, data: rejected });
    if (other.length)
      out.push({ title: `Autre (${other.length})`, data: other });
    return out;
  }, [purchases, t]);

  const pendingCount = useMemo(
    () => (purchases ?? []).filter((p) => p.status === "pending_approval" || p.status === "pending").length,
    [purchases]
  );

  const errFmt = error ? formatApiError(error, t) : null;

  if (isLoading) {
    return (
      <View style={styles.container}>
        <View style={styles.headerPad}>
          <AdminAccentStripe />
          <ProductBrandMark title={t("appName")} subtitle={t("myPurchases")} />
          <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("adminPurchasesSubtitle")} />
        </View>
        <InvoiceListSkeleton count={6} />
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

  if (!purchases?.length) {
    return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.list, styles.listFlex]}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      >
        <View style={styles.headerPad}>
          <AdminAccentStripe />
          <ProductBrandMark title={t("appName")} subtitle={t("myPurchases")} />
          <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("adminPurchasesSubtitle")} />
        </View>
        <EmptyState
          icon="cart-outline"
          title={t("adminNoPurchases")}
          subtitle={t("adminNoPurchasesBody")}
        />
      </ScrollView>
    );
  }

  return (
    <SectionList
      sections={sections}
      keyExtractor={(item) => item.id}
      renderSectionHeader={({ section: { title } }) => (
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{title}</Text>
        </View>
      )}
      renderItem={({ item }) => (
        <PurchaseRow
          item={item}
          t={t}
          onApprove={() => approveM.mutate(item.id)}
          onReject={() => rejectM.mutate(item.id)}
          approving={approveM.isPending && approveM.variables === item.id}
          rejecting={rejectM.isPending && rejectM.variables === item.id}
        />
      )}
      ListHeaderComponent={
        <View style={styles.headerPad}>
          <AdminAccentStripe />
          <ProductBrandMark title={t("appName")} subtitle={t("myPurchases")} />
          <AdminHeader
            eyebrow={t("adminEyebrow")}
            subtitle={
              pendingCount > 0
                ? `${pendingCount} ${t("pendingApproval").toLowerCase()}`
                : t("adminPurchasesSubtitle")
            }
          />
        </View>
      }
      contentContainerStyle={styles.list}
      style={styles.container}
      stickySectionHeadersEnabled={false}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  headerPad: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm },
  list: { padding: space.lg, paddingBottom: space.xxxl },
  listFlex: { flexGrow: 1 },

  sectionHeader: {
    backgroundColor: colors.background,
    paddingVertical: space.sm,
    marginTop: space.xs,
  },
  sectionTitle: {
    fontSize: font.md,
    fontWeight: font.bold,
    color: colors.primaryDark,
    letterSpacing: 0.2,
  },

  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    marginBottom: space.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderLeftColor: colors.primary,
    ...shadow.soft,
  },
  rowPending: {
    borderLeftColor: colors.warning,
    backgroundColor: colors.warningSoft ?? "#FFF8E1",
  },
  rowTop: { flexDirection: "row", alignItems: "flex-start" },
  avatarWrap: { marginRight: space.sm, marginTop: 2 },
  avatarPending: { opacity: 0.9 },
  rowBody: { flex: 1 },
  rowProduct: { fontSize: font.md, fontWeight: font.bold, color: colors.text, marginBottom: 2 },
  rowEmployee: { fontSize: font.sm, color: colors.primary, fontWeight: font.semibold, marginBottom: 2 },
  rowMeta: { fontSize: font.xs, color: colors.textMuted },
  rowRight: { alignItems: "flex-end", marginLeft: space.sm },
  rowAmount: { fontSize: font.lg, fontWeight: font.bold, color: colors.primaryDark },
  rowCurrency: { fontSize: font.xs, color: colors.textMuted },
  rowFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: space.sm,
    paddingTop: space.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  rowDate: { fontSize: font.xs, color: colors.textMuted },
  actionRow: {
    flexDirection: "row",
    gap: space.sm,
    marginTop: space.md,
    paddingTop: space.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  actionBtn: { flex: 1 },
});
