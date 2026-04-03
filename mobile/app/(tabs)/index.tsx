import { useQuery } from "@tanstack/react-query";
import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from "react-native";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { listMyPurchases } from "../../src/api/purchases";
import { listMyAlerts } from "../../src/api/alerts";
import { queryKeys } from "../../src/queryKeys";

function todayISO() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

export default function HomeScreen() {
  const { user } = useAuth();
  const { t } = useLocale();

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

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.card}>
        <Text style={styles.welcome}>{t("appName")}</Text>
        <Text style={styles.subtitle}>{user?.email ?? ""}</Text>
      </View>
      <View style={styles.kpiRow}>
        <View style={styles.kpiCard}>
          <Text style={styles.kpiLabel}>{t("todaySales") || "Today"}</Text>
          <Text style={styles.kpiValue}>{todaySales.toFixed(0)}</Text>
          <Text style={styles.kpiHint}>TND</Text>
        </View>
        <View style={styles.kpiCard}>
          <Text style={styles.kpiLabel}>{t("pendingApprovals") || "Pending"}</Text>
          <Text style={styles.kpiValue}>{pendingCount}</Text>
          <Text style={styles.kpiHint}>{t("operations") || "ops"}</Text>
        </View>
        <View style={styles.kpiCard}>
          <Text style={styles.kpiLabel}>{t("alerts")}</Text>
          <Text style={styles.kpiValue}>{alertsCount}</Text>
          <Text style={styles.kpiHint}>{t("unresolved") || "unresolved"}</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
  },
  welcome: { fontSize: 22, fontWeight: "700", color: colors.primary, marginBottom: 8 },
  subtitle: { fontSize: 16, color: colors.textMuted, marginBottom: 12 },
  hint: { fontSize: 14, color: colors.textMuted },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  kpiRow: { flexDirection: "row", gap: 12, marginBottom: 12 },
  kpiCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  kpiLabel: { fontSize: 12, color: colors.textMuted, marginBottom: 4 },
  kpiValue: { fontSize: 20, fontWeight: "700", color: colors.primary },
  kpiHint: { fontSize: 12, color: colors.textMuted, marginTop: 4 },
});
