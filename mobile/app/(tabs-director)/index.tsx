import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { View, Text, StyleSheet, ScrollView, RefreshControl, Pressable, Modal, TextInput } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, space } from "../../src/theme/tokens";
import { api } from "../../src/api/client";
import { listInvoices, type InvoiceListItem } from "../../src/api/invoices";
import { createFarm, listFarms } from "../../src/api/farms";
import { listAllAlerts } from "../../src/api/alerts";
import Toast from "react-native-toast-message";
import {
  Card,
  DirectorKpiSkeleton,
  EmptyState,
  ErrorState,
  ProductBrandMark,
  QuickActionTile,
  AdminAttentionPairSkeleton,
  AdminMiniRowsSkeleton,
  UserAvatar,
} from "../../src/components/ui";
import {
  AdminAccentStripe,
  AdminAttentionCard,
  AdminErrorShell,
  AdminHeader,
  AdminKpiStatCard,
  AdminMiniRow,
  AdminQueueClearCard,
  AdminSectionLabel,
} from "../../src/components/admin";
import { formatApiError } from "../../src/utils/apiError";

type DashboardStats = {
  total_amount_today: number;
  total_amount_month: number;
  purchases_today: number;
  purchases_month: number;
  inflow_today: number;
  outflow_today: number;
  inflow_month: number;
  outflow_month: number;
  gross_margin_month: number;
  net_profit_month: number;
  fixed_expenses_month: number;
  variable_expenses_month: number;
  poussins_sales_month: number;
  nourriture_sales_month: number;
};

function isPendingReview(status: string) {
  return status === "ready" || status === "ready_for_review";
}

export default function DirectorDashboardScreen() {
  const [selectedFarmId, setSelectedFarmId] = useState<string>("");
  const [farmModalOpen, setFarmModalOpen] = useState(false);
  const [newFarmName, setNewFarmName] = useState("");
  const { user } = useAuth();
  const { t } = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();

  const statsQ = useQuery({
    queryKey: ["dashboard-stats", selectedFarmId || "all"],
    queryFn: async () => {
      const { data: res } = await api.get<DashboardStats>("/dashboard/stats", {
        params: selectedFarmId ? { farm_id: selectedFarmId } : undefined,
      });
      return res;
    },
  });

  const invoicesQ = useQuery({
    queryKey: ["invoices-list", selectedFarmId || "all"],
    queryFn: () => listInvoices({ limit: 100, ...(selectedFarmId ? { farm_id: selectedFarmId } : {}) }),
  });
  const farmsQ = useQuery({
    queryKey: ["farms"],
    queryFn: listFarms,
  });

  const alertsQ = useQuery({
    queryKey: ["alerts-director"],
    queryFn: listAllAlerts,
  });

  const createFarmM = useMutation({
    mutationFn: (name: string) => createFarm({ name }),
    onSuccess: async (farm) => {
      setFarmModalOpen(false);
      setNewFarmName("");
      setSelectedFarmId(farm.id);
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      Toast.show({ type: "success", text1: t("successGenericTitle"), text2: t("farmCreateSuccess") });
    },
    onError: (e) => {
      const formatted = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: formatted.message || t("farmCreateError") });
    },
  });

  const errFmt = statsQ.error ? formatApiError(statsQ.error, t) : null;

  const pendingInvoices = useMemo(() => {
    const list = invoicesQ.data ?? [];
    return list.filter((i) => isPendingReview(i.status));
  }, [invoicesQ.data]);

  const urgentOpenAlerts = useMemo(() => {
    const list = alertsQ.data ?? [];
    return list.filter(
      (a) =>
        a.status !== "resolved" && (a.severity === "critical" || a.severity === "high")
    );
  }, [alertsQ.data]);

  const recentInvoices = useMemo(() => {
    const list = [...(invoicesQ.data ?? [])];
    list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    return list.slice(0, 5);
  }, [invoicesQ.data]);

  const formatStatus = (s: string) => {
    const map: Record<string, string> = {
      processing: t("invoiceStatusProcessing"),
      ready: t("invoiceStatusReady"),
      ready_for_review: t("invoiceStatusReadyForReview"),
      approved: t("invoiceStatusApproved"),
      rejected: t("invoiceStatusRejected"),
      failed: t("invoiceStatusFailed"),
    };
    return map[s] || s;
  };

  const fmtAmount = (v: number | null) => {
    if (v == null || Number.isNaN(v)) return "—";
    return new Intl.NumberFormat("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(v);
  };

  const refreshing = statsQ.isRefetching || invoicesQ.isRefetching || alertsQ.isRefetching;

  const onRefresh = () => {
    void statsQ.refetch();
    void invoicesQ.refetch();
    void alertsQ.refetch();
  };

  const onCreateFarm = () => {
    const name = newFarmName.trim();
    if (name.length < 2) {
      Toast.show({ type: "error", text1: t("error"), text2: t("farmNameMinChars") });
      return;
    }
    createFarmM.mutate(name);
  };

  if (statsQ.error && errFmt && !statsQ.isLoading) {
    return (
      <AdminErrorShell>
        <ErrorState
          title={t("error")}
          message={errFmt.message}
          hint={errFmt.hint}
          onRetry={() => statsQ.refetch()}
          retryLabel={t("retry")}
        />
      </AdminErrorShell>
    );
  }

  const listsLoading = invoicesQ.isLoading || alertsQ.isLoading;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <AdminAccentStripe />
      <View style={styles.homeHeaderRow}>
        <View style={styles.homeBrandCol}>
          <ProductBrandMark title={t("appName")} subtitle={t("dashboard")} />
        </View>
        {user?.email ? (
          <Pressable
            onPress={() => router.push("/(tabs-director)/settings")}
            style={({ pressed }) => [styles.avatarTap, pressed && styles.avatarTapPressed]}
            accessibilityRole="button"
            accessibilityLabel={t("settings")}
          >
            <UserAvatar
              email={user.email}
              size="md"
              role={user.role}
              showRoleBadge
              accessible={false}
            />
          </Pressable>
        ) : null}
      </View>
      {user?.email ? <Text style={styles.email}>{user.email}</Text> : null}

      <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("directorDashboardSubtitle")} />
      <View style={styles.farmRow}>
        <Pressable
          onPress={() => setSelectedFarmId("")}
          style={[styles.farmChip, !selectedFarmId && styles.farmChipOn]}
        >
          <Text style={[styles.farmChipText, !selectedFarmId && styles.farmChipTextOn]}>Global</Text>
        </Pressable>
        {(farmsQ.data ?? []).map((farm) => (
          <Pressable
            key={farm.id}
            onPress={() => setSelectedFarmId(farm.id)}
            style={[styles.farmChip, selectedFarmId === farm.id && styles.farmChipOn]}
          >
            <Text style={[styles.farmChipText, selectedFarmId === farm.id && styles.farmChipTextOn]}>
              {farm.name}
            </Text>
          </Pressable>
        ))}
        <Pressable onPress={() => setFarmModalOpen(true)} style={[styles.farmChip, styles.addFarmChip]}>
          <Text style={[styles.farmChipText, styles.addFarmChipText]}>+ {t("farmAddAction")}</Text>
        </Pressable>
      </View>

      <AdminSectionLabel>{t("directorSectionAction")}</AdminSectionLabel>
      {listsLoading ? (
        <AdminAttentionPairSkeleton />
      ) : (
        <>
          {pendingInvoices.length > 0 ? (
            <AdminAttentionCard
              icon="shield-checkmark-outline"
              title={t("directorPendingReviewsTitle")}
              subtitle={t("directorPendingReviewsSubtitle")}
              count={pendingInvoices.length}
              tone="warning"
              onPress={() => router.push("/(tabs-director)/invoices")}
            />
          ) : (
            <AdminQueueClearCard
              title={t("directorQueueClearInvoices")}
              subtitle={t("directorQueueClearInvoicesSub")}
            />
          )}
          {urgentOpenAlerts.length > 0 ? (
            <AdminAttentionCard
              icon="notifications-outline"
              title={t("directorUrgentAlertsTitle")}
              subtitle={t("directorUrgentAlertsSubtitle")}
              count={urgentOpenAlerts.length}
              tone="danger"
              onPress={() => router.push("/(tabs-director)/alerts")}
            />
          ) : (
            <AdminQueueClearCard
              title={t("directorQueueClearAlerts")}
              subtitle={t("directorQueueClearAlertsSub")}
            />
          )}
        </>
      )}

      <AdminSectionLabel>{t("directorSectionKpis")}</AdminSectionLabel>
      {statsQ.isLoading ? (
        <DirectorKpiSkeleton />
      ) : (
        <>
          <View style={styles.kpiRow}>
            <AdminKpiStatCard
              label={t("directorKpiCashInToday")}
              value={(statsQ.data?.inflow_today ?? 0).toFixed(0)}
              hint={t("myPurchases")}
            />
            <AdminKpiStatCard
              label={t("directorKpiCashOutToday")}
              value={(statsQ.data?.outflow_today ?? 0).toFixed(0)}
              hint="TND"
              variant="emphasis"
            />
          </View>
          <View style={styles.kpiRow}>
            <AdminKpiStatCard
              label={t("directorKpiGrossMargin")}
              value={(statsQ.data?.gross_margin_month ?? 0).toFixed(0)}
              hint="TND"
            />
            <AdminKpiStatCard
              label={t("directorKpiNetProfit")}
              value={(statsQ.data?.net_profit_month ?? 0).toFixed(0)}
              hint="TND"
            />
          </View>
          <View style={styles.kpiRow}>
            <AdminKpiStatCard
              label={t("directorKpiFixedExpenses")}
              value={(statsQ.data?.fixed_expenses_month ?? 0).toFixed(0)}
              hint="TND"
            />
            <AdminKpiStatCard
              label={t("directorKpiVariableExpenses")}
              value={(statsQ.data?.variable_expenses_month ?? 0).toFixed(0)}
              hint="TND"
            />
          </View>
          <View style={styles.kpiRow}>
            <AdminKpiStatCard
              label={t("directorKpiPoussinsSales")}
              value={(statsQ.data?.poussins_sales_month ?? 0).toFixed(0)}
              hint="TND"
            />
            <AdminKpiStatCard
              label={t("directorKpiNourritureSales")}
              value={(statsQ.data?.nourriture_sales_month ?? 0).toFixed(0)}
              hint="TND"
            />
          </View>
        </>
      )}

      <AdminSectionLabel>{t("directorSectionRecent")}</AdminSectionLabel>
      {listsLoading ? (
        <AdminMiniRowsSkeleton count={4} />
      ) : recentInvoices.length === 0 ? (
        <EmptyState
          icon="receipt-outline"
          title={t("noInvoices")}
          subtitle={t("emptyDirectorInvoicesHint")}
          primaryCtaTitle={t("directorViewQueue")}
          onPrimaryCta={() => router.push("/(tabs-director)/invoices")}
        />
      ) : (
        <View style={styles.recentBlock}>
          {recentInvoices.map((row: InvoiceListItem) => (
            <AdminMiniRow
              key={row.id}
              title={row.supplier_name || row.invoice_number || "—"}
              meta={`${formatStatus(row.status)} · ${row.employee_email ?? ""}`}
              right={row.total_ttc != null ? `${fmtAmount(row.total_ttc)} TND` : undefined}
              onPress={() =>
                router.push({ pathname: "/(tabs-director)/invoice/[id]", params: { id: row.id } })
              }
            />
          ))}
          <Text style={styles.recentHint}>{t("directorViewQueue")}</Text>
        </View>
      )}

      <AdminSectionLabel>{t("directorSectionTools")}</AdminSectionLabel>
      <View style={styles.toolsBlock}>
        <QuickActionTile
          title={t("reports")}
          subtitle={t("directorToolReportsSub")}
          icon="download-outline"
          onPress={() => router.push("/(tabs-director)/reports")}
        />
        <QuickActionTile
          title={t("policiesTab")}
          subtitle={t("directorToolPoliciesSub")}
          icon="shield-checkmark-outline"
          onPress={() => router.push("/(tabs-director)/policies")}
        />
        <QuickActionTile
          title={t("auditTab")}
          subtitle={t("directorToolAuditSub")}
          icon="reader-outline"
          onPress={() => router.push("/(tabs-director)/audit")}
        />
      </View>

      <Card style={styles.hintCard}>
        <Text style={styles.hintText}>{t("directorDashboardFooterHint")}</Text>
      </Card>

      <Modal
        visible={farmModalOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setFarmModalOpen(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>{t("farmAddTitle")}</Text>
            <Text style={styles.modalSubtitle}>{t("farmAddSubtitle")}</Text>
            <TextInput
              value={newFarmName}
              onChangeText={setNewFarmName}
              placeholder={t("farmNamePlaceholder")}
              style={styles.modalInput}
              autoCapitalize="words"
            />
            <View style={styles.modalButtons}>
              <Pressable style={styles.modalBtnGhost} onPress={() => setFarmModalOpen(false)}>
                <Text style={styles.modalBtnGhostText}>{t("cancel")}</Text>
              </Pressable>
              <Pressable
                style={[styles.modalBtnPrimary, createFarmM.isPending && styles.modalBtnDisabled]}
                onPress={onCreateFarm}
                disabled={createFarmM.isPending}
              >
                <Text style={styles.modalBtnPrimaryText}>
                  {createFarmM.isPending ? t("processing") : t("farmCreateCta")}
                </Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: space.lg, paddingBottom: space.xxxl, paddingTop: space.sm },
  homeHeaderRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: space.md,
    marginBottom: space.xs,
  },
  homeBrandCol: { flex: 1, minWidth: 0 },
  avatarTap: { padding: space.xs, marginTop: 2, marginRight: -space.xs },
  avatarTapPressed: { opacity: 0.85 },
  email: { fontSize: font.sm, color: colors.textSecondary, marginBottom: space.sm, fontWeight: font.medium },
  farmRow: { flexDirection: "row", flexWrap: "wrap", gap: space.xs, marginBottom: space.md },
  farmChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
    backgroundColor: colors.surface,
  },
  farmChipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  farmChipText: { fontSize: font.xs, fontWeight: font.semibold, color: colors.textSecondary },
  farmChipTextOn: { color: "#fff" },
  addFarmChip: { borderStyle: "dashed", borderColor: colors.primary },
  addFarmChipText: { color: colors.primary },
  kpiRow: { flexDirection: "row", gap: space.sm, marginBottom: space.sm },
  toolsBlock: { marginBottom: space.md },
  recentBlock: { marginBottom: space.md },
  recentHint: {
    marginTop: space.xs,
    fontSize: font.xs,
    fontWeight: font.semibold,
    color: colors.primary,
  },
  hintCard: { marginTop: space.lg, backgroundColor: colors.surfaceMuted, borderStyle: "dashed" },
  hintText: { fontSize: font.sm, color: colors.textSecondary, lineHeight: 20 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.45)",
    alignItems: "center",
    justifyContent: "center",
    padding: space.lg,
  },
  modalCard: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: space.lg,
    gap: space.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  modalTitle: { fontSize: font.lg, fontWeight: font.bold, color: colors.primaryDark },
  modalSubtitle: { fontSize: font.sm, color: colors.textSecondary },
  modalInput: {
    minHeight: 46,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: space.md,
    backgroundColor: colors.backgroundElevated,
    color: colors.text,
  },
  modalButtons: { flexDirection: "row", justifyContent: "flex-end", gap: space.sm, marginTop: space.xs },
  modalBtnGhost: { paddingHorizontal: space.md, paddingVertical: space.sm },
  modalBtnGhostText: { color: colors.textSecondary, fontSize: font.sm, fontWeight: font.semibold },
  modalBtnPrimary: {
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: 10,
    backgroundColor: colors.primary,
  },
  modalBtnPrimaryText: { color: "#fff", fontSize: font.sm, fontWeight: font.semibold },
  modalBtnDisabled: { opacity: 0.6 },
});
