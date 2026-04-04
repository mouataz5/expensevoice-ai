import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  View,
  Text,
  StyleSheet,
  SectionList,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, shadow, space } from "../../src/theme/tokens";
import { listMyAlerts, resolveAlert, type AlertOut } from "../../src/api/alerts";
import { queryKeys } from "../../src/queryKeys";
import {
  EmptyState,
  ErrorState,
  StatusPill,
  AlertListSkeleton,
  ProductBrandMark,
} from "../../src/components/ui";
import { formatApiError } from "../../src/utils/apiError";
import Toast from "react-native-toast-message";

function sortByDateDesc(a: AlertOut, b: AlertOut) {
  return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
}

function AlertRow({
  item,
  t,
  onResolve,
  resolving,
  onOpenPurchase,
}: {
  item: AlertOut;
  t: (k: string) => string;
  onResolve: () => void;
  resolving: boolean;
  onOpenPurchase: () => void;
}) {
  const isCritical = item.severity === "critical";
  const isHigh = item.severity === "high";
  const tone = isCritical ? "danger" : isHigh ? "warning" : "info";
  const statusLabel = `${item.severity} · ${item.status}`;
  const canResolve = item.status !== "resolved";
  const priorityLabel =
    isCritical ? t("alertsPriorityCritical") : isHigh ? t("alertsPriorityHigh") : null;

  return (
    <View style={[styles.row, isCritical && styles.rowCritical, isHigh && !isCritical && styles.rowHigh]}>
      <View style={styles.rowTop}>
        <View style={[styles.iconWrap, isCritical && styles.iconWrapUrgent]}>
          <Ionicons name={isCritical ? "warning" : "notifications-outline"} size={22} color={colors.primary} />
        </View>
        <View style={styles.rowBody}>
          <View style={styles.rowTitleRow}>
            <Text style={styles.rowType} numberOfLines={1}>
              {item.alert_type}
            </Text>
            {priorityLabel ? (
              <View style={styles.priorityTag}>
                <Text style={styles.priorityTagTxt}>{priorityLabel}</Text>
              </View>
            ) : null}
          </View>
          <Text style={styles.rowMessage} numberOfLines={3}>
            {item.message}
          </Text>
          <View style={styles.pillRow}>
            <StatusPill label={statusLabel} tone={tone} />
          </View>
          <View style={styles.actionsRow}>
            {item.purchase_id ? (
              <TouchableOpacity style={styles.linkBtn} onPress={onOpenPurchase} accessibilityRole="button">
                <Ionicons name="open-outline" size={16} color={colors.primary} />
                <Text style={styles.linkTxt}>{t("alertsOpenPurchase")}</Text>
              </TouchableOpacity>
            ) : null}
            {canResolve ? (
              <TouchableOpacity
                style={[styles.resolveBtn, resolving && styles.resolveBtnDim]}
                onPress={onResolve}
                disabled={resolving}
                accessibilityRole="button"
                accessibilityLabel={t("alertsResolve")}
              >
                {resolving ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.resolveBtnTxt}>{t("alertsResolve")}</Text>
                )}
              </TouchableOpacity>
            ) : null}
          </View>
        </View>
      </View>
    </View>
  );
}

export default function AlertsScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const qc = useQueryClient();
  const { data: alerts, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.alertsMe,
    queryFn: listMyAlerts,
  });

  const resolveM = useMutation({
    mutationFn: (id: string) => resolveAlert(id),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("alertsResolved") });
      void qc.invalidateQueries({ queryKey: queryKeys.alertsMe });
      void qc.invalidateQueries({ queryKey: queryKeys.purchasesMe });
    },
    onError: (e) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    },
  });

  const sections = useMemo(() => {
    if (!alerts?.length) return [];
    const open = alerts.filter((a) => a.status !== "resolved");
    const urgent = open
      .filter((a) => a.severity === "critical" || a.severity === "high")
      .sort(sortByDateDesc);
    const otherOpen = open
      .filter((a) => a.severity !== "critical" && a.severity !== "high")
      .sort(sortByDateDesc);
    const resolved = alerts.filter((a) => a.status === "resolved").sort(sortByDateDesc);
    const out: { title: string; data: AlertOut[] }[] = [];
    if (urgent.length)
      out.push({ title: `${t("alertsSectionUrgent")} (${urgent.length})`, data: urgent });
    if (otherOpen.length)
      out.push({ title: `${t("alertsSectionOpen")} (${otherOpen.length})`, data: otherOpen });
    if (resolved.length)
      out.push({ title: `${t("alertsSectionResolved")} (${resolved.length})`, data: resolved });
    return out;
  }, [alerts, t]);

  const errFmt = error ? formatApiError(error, t) : null;

  if (isLoading) {
    return (
      <View style={styles.container}>
        <View style={styles.listHeaderPad}>
          <ProductBrandMark title={t("appName")} subtitle={t("alerts")} />
        </View>
        <AlertListSkeleton count={6} />
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

  if (!alerts?.length) {
    return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.list, styles.listFlex]}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      >
        <View style={styles.listHeaderPad}>
          <ProductBrandMark title={t("appName")} subtitle={t("alerts")} />
        </View>
        <EmptyState
          icon="notifications-off-outline"
          title={t("noAlerts")}
          subtitle={t("emptyAlertsBody")}
          primaryCtaTitle={t("emptyAlertsCtaPrimary")}
          onPrimaryCta={() => router.push("/(tabs)/scan")}
          secondaryCtaTitle={t("emptyAlertsCtaSecondary")}
          onSecondaryCta={() => router.push("/(tabs)/purchases")}
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
        <AlertRow
          item={item}
          t={t}
          resolving={resolveM.isPending && resolveM.variables === item.id}
          onResolve={() => resolveM.mutate(item.id)}
          onOpenPurchase={() =>
            router.push({ pathname: "/purchases/[id]", params: { id: item.purchase_id } })
          }
        />
      )}
      ListHeaderComponent={
        <View style={styles.listHeaderPad}>
          <ProductBrandMark title={t("appName")} subtitle={t("alertsGroupedHint")} />
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
  list: { paddingHorizontal: space.lg, paddingBottom: space.xxxl },
  listFlex: { flexGrow: 1 },
  listHeaderPad: { paddingTop: space.md, paddingBottom: space.sm },
  sectionHeader: {
    backgroundColor: colors.background,
    paddingVertical: space.sm,
    marginTop: space.xs,
  },
  sectionTitle: { fontSize: font.sm, fontWeight: font.bold, color: colors.primaryDark, letterSpacing: 0.3 },
  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.md,
    marginBottom: space.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderLeftColor: colors.warning,
    ...shadow.soft,
  },
  rowCritical: { borderLeftColor: colors.critical, backgroundColor: colors.errorSoft },
  rowHigh: { borderLeftColor: colors.warning, backgroundColor: colors.warningSoft },
  rowTop: { flexDirection: "row", alignItems: "flex-start" },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginRight: space.md,
  },
  iconWrapUrgent: { backgroundColor: colors.errorSoft },
  rowBody: { flex: 1 },
  rowTitleRow: { flexDirection: "row", alignItems: "center", gap: space.sm, marginBottom: space.xs, flexWrap: "wrap" },
  rowType: { fontSize: font.sm, fontWeight: font.bold, color: colors.text, flexShrink: 1 },
  priorityTag: {
    backgroundColor: colors.primaryDark,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  priorityTagTxt: { fontSize: font.xs, fontWeight: font.bold, color: "#fff" },
  rowMessage: { fontSize: font.md, color: colors.textSecondary, lineHeight: 22, marginBottom: space.sm },
  pillRow: { flexDirection: "row", flexWrap: "wrap", marginBottom: space.sm },
  actionsRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: space.sm },
  linkBtn: { flexDirection: "row", alignItems: "center", gap: 4 },
  linkTxt: { fontSize: font.sm, fontWeight: font.semibold, color: colors.primary },
  resolveBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: space.md,
    paddingVertical: space.xs + 2,
    borderRadius: radius.md,
    minWidth: 100,
    alignItems: "center",
    justifyContent: "center",
  },
  resolveBtnDim: { opacity: 0.7 },
  resolveBtnTxt: { color: "#fff", fontSize: font.sm, fontWeight: font.bold },
});
