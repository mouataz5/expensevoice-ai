import { useQuery } from "@tanstack/react-query";
import { View, Text, StyleSheet, TouchableOpacity, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, space } from "../../src/theme/tokens";
import { listMyPurchases } from "../../src/api/purchases";
import { listMyAlerts } from "../../src/api/alerts";
import { queryKeys } from "../../src/queryKeys";
import {
  ScreenScroll,
  Card,
  MetricCard,
  QuickActionTile,
  SectionTitle,
  HomeOverviewSkeleton,
  ProductBrandMark,
  UserAvatar,
} from "../../src/components/ui";
import { Ionicons } from "@expo/vector-icons";

function todayISO() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

export default function HomeScreen() {
  const { user } = useAuth();
  const { t } = useLocale();
  const router = useRouter();

  const { data: purchases, isLoading: loadingPurchases } = useQuery({
    queryKey: queryKeys.purchasesMe,
    queryFn: listMyPurchases,
  });
  const { data: alerts, isLoading: loadingAlerts } = useQuery({
    queryKey: queryKeys.alertsMe,
    queryFn: listMyAlerts,
  });

  const today = todayISO();
  const todayPurchases = purchases?.filter((p) => p.created_at?.startsWith(today)) ?? [];
  const todaySales = todayPurchases.reduce((s, p) => s + (p.total_amount ?? 0), 0);
  const pendingCount = purchases?.filter((p) => p.status === "ready_for_review").length ?? 0;
  const alertsCount = alerts?.filter((a) => a.status !== "resolved").length ?? 0;

  const isLoading = loadingPurchases || loadingAlerts;

  return (
    <ScreenScroll>
      <View style={styles.homeHeaderRow}>
        <View style={styles.homeBrandCol}>
          <ProductBrandMark title={t("appName")} subtitle={t("homeTagline")} />
        </View>
        {user?.email ? (
          <Pressable
            onPress={() => router.push("/profile")}
            style={({ pressed }) => [styles.avatarTap, pressed && styles.avatarTapPressed]}
            accessibilityRole="button"
            accessibilityLabel={t("profile")}
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

      {isLoading ? (
        <>
          <HomeOverviewSkeleton />
          <Text style={styles.loadingHint}>{t("loadingApp")}</Text>
        </>
      ) : (
        <>
          {user?.email ? <Text style={styles.heroEmail}>{user.email}</Text> : null}
          {(pendingCount > 0 || alertsCount > 0) && (
            <Card style={styles.priorityCard}>
              <Text style={styles.priorityTitle}>{t("homeAttentionTitle")}</Text>
              <Text style={styles.prioritySub}>{t("homeAttentionSubtitle")}</Text>
              {pendingCount > 0 ? (
                <TouchableOpacity
                  style={styles.priorityRow}
                  onPress={() => router.push("/purchases")}
                  accessibilityRole="button"
                  accessibilityLabel={t("myPurchases")}
                >
                  <Ionicons name="list-outline" size={22} color={colors.primary} />
                  <Text style={styles.priorityRowTxt}>
                    {t("myPurchases")} · {pendingCount}
                  </Text>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSubtle} />
                </TouchableOpacity>
              ) : null}
              {alertsCount > 0 ? (
                <TouchableOpacity
                  style={styles.priorityRow}
                  onPress={() => router.push("/alerts")}
                  accessibilityRole="button"
                  accessibilityLabel={t("alerts")}
                >
                  <Ionicons name="notifications-outline" size={22} color={colors.warning} />
                  <Text style={styles.priorityRowTxt}>
                    {t("alerts")} · {alertsCount}
                  </Text>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSubtle} />
                </TouchableOpacity>
              ) : null}
            </Card>
          )}
          <SectionTitle title={t("homeOverview")} />
          <View style={styles.kpiRow}>
            <MetricCard label={t("todaySales")} value={todaySales.toFixed(0)} hint="TND" />
            <MetricCard label={t("pendingApprovals")} value={String(pendingCount)} hint={t("myPurchases")} />
            <MetricCard label={t("alerts")} value={String(alertsCount)} hint={t("unresolved")} />
          </View>
        </>
      )}

      <SectionTitle title={t("quickActions")} />
      <QuickActionTile
        title={t("scanInvoice")}
        subtitle={t("quickScanDesc")}
        icon="document-text-outline"
        onPress={() => router.push("/scan")}
      />
      <QuickActionTile
        title={t("voiceStudio")}
        subtitle={t("quickVoiceDesc")}
        icon="mic-outline"
        onPress={() => router.push("/voice-studio")}
      />
      <QuickActionTile
        title={t("record")}
        subtitle={t("quickVoiceDesc")}
        icon="radio-outline"
        onPress={() => router.push("/record")}
      />
      <QuickActionTile
        title={t("myInvoices")}
        subtitle={t("quickInvoicesDesc")}
        icon="receipt-outline"
        onPress={() => router.push("/invoices")}
      />
      <QuickActionTile
        title={t("myPurchases")}
        subtitle={t("quickPurchasesDesc")}
        icon="list-outline"
        onPress={() => router.push("/purchases")}
      />
      <QuickActionTile
        title={t("alerts")}
        subtitle={t("quickAlertsDesc")}
        icon="notifications-outline"
        onPress={() => router.push("/alerts")}
      />

      <Card style={styles.hintCard}>
        <Text style={styles.hintText}>{t("scanWorkflowHint")}</Text>
      </Card>
    </ScreenScroll>
  );
}

const styles = StyleSheet.create({
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
  priorityCard: {
    marginBottom: space.lg,
    borderLeftWidth: 4,
    borderLeftColor: colors.primary,
    gap: space.sm,
  },
  priorityTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.primaryDark },
  prioritySub: { fontSize: font.sm, color: colors.textMuted, lineHeight: 20, marginBottom: space.xs },
  priorityRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    paddingVertical: space.sm,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  priorityRowTxt: { flex: 1, fontSize: font.md, fontWeight: font.semibold, color: colors.text },
  loadingHint: { fontSize: font.sm, color: colors.textMuted, marginTop: space.md, marginBottom: space.lg },
  heroEmail: { fontSize: font.sm, color: colors.textSecondary, marginTop: space.sm, marginBottom: space.md, fontWeight: font.medium },
  kpiRow: { flexDirection: "row", gap: space.sm, marginBottom: space.xl },
  hintCard: { marginTop: space.md, backgroundColor: colors.surfaceMuted, borderStyle: "dashed" },
  hintText: { fontSize: font.sm, color: colors.textSecondary, lineHeight: 20 },
});
