import { useQuery } from "@tanstack/react-query";
import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from "react-native";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { api } from "../../src/api/client";

type DashboardStats = {
  total_amount_today: number;
  total_amount_month: number;
  purchases_today: number;
  purchases_month: number;
};

export default function DirectorDashboardScreen() {
  const { user } = useAuth();
  const { t } = useLocale();
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const { data: res } = await api.get<DashboardStats>("/dashboard/stats");
      return res;
    },
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
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.card}>
        <Text style={styles.title}>{t("dashboard")}</Text>
        <Text style={styles.subtitle}>{user?.email ?? ""}</Text>
      </View>
      <View style={styles.kpiRow}>
        <View style={styles.kpiCard}>
          <Text style={styles.kpiLabel}>Today</Text>
          <Text style={styles.kpiValue}>{data?.purchases_today ?? 0}</Text>
          <Text style={styles.kpiHint}>operations</Text>
        </View>
        <View style={styles.kpiCard}>
          <Text style={styles.kpiLabel}>Amount today</Text>
          <Text style={styles.kpiValue}>{(data?.total_amount_today ?? 0).toFixed(0)}</Text>
          <Text style={styles.kpiHint}>TND</Text>
        </View>
      </View>
      <View style={styles.kpiRow}>
        <View style={styles.kpiCard}>
          <Text style={styles.kpiLabel}>Month</Text>
          <Text style={styles.kpiValue}>{data?.purchases_month ?? 0}</Text>
          <Text style={styles.kpiHint}>operations</Text>
        </View>
        <View style={styles.kpiCard}>
          <Text style={styles.kpiLabel}>Amount month</Text>
          <Text style={styles.kpiValue}>{(data?.total_amount_month ?? 0).toFixed(0)}</Text>
          <Text style={styles.kpiHint}>TND</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  errorText: { fontSize: 18, color: colors.error },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: 24,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
  },
  title: { fontSize: 22, fontWeight: "700", color: colors.primary, marginBottom: 8 },
  subtitle: { fontSize: 16, color: colors.textMuted },
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
