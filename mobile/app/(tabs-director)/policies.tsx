import { useQuery } from "@tanstack/react-query";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { queryKeys } from "../../src/queryKeys";
import { fetchActivePolicies } from "../../src/api/policies-read";

export default function DirectorPoliciesScreen() {
  const { t } = useLocale();
  const q = useQuery({
    queryKey: queryKeys.policiesActive,
    queryFn: fetchActivePolicies,
  });

  if (q.isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (q.isError) {
    return (
      <View style={styles.centered}>
        <Text style={styles.err}>{t("error")}</Text>
      </View>
    );
  }

  const rows = q.data ?? [];
  const limits = rows.find((p) => p.policy_type === "limits");
  const categories = rows.find((p) => p.policy_type === "categories");

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} />}
    >
      <Text style={styles.title}>{t("policiesTitle")}</Text>
      <Text style={styles.sub}>{t("policiesSubtitle")}</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t("limitsLabel")}</Text>
        {limits ? (
          <>
            <Text style={styles.row}>
              {t("limitsMaxPerPurchase")}:{" "}
              {String((limits.rule as { max_per_purchase?: number })?.max_per_purchase ?? "—")}
            </Text>
            <Text style={styles.row}>
              {t("limitsDailyDefault")}:{" "}
              {String((limits.rule as { daily_limit_default?: number })?.daily_limit_default ?? "—")}
            </Text>
            <Text style={styles.meta}>{limits.is_active ? t("usersActive") : t("usersDisabled")}</Text>
          </>
        ) : (
          <Text style={styles.muted}>—</Text>
        )}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t("categoriesLabel")}</Text>
        {categories ? (
          <>
            <Text style={styles.catText}>
              {Array.isArray((categories.rule as { allowed?: string[] })?.allowed)
                ? (categories.rule as { allowed: string[] }).allowed.join(", ")
                : "—"}
            </Text>
            <Text style={styles.meta}>{categories.is_active ? t("usersActive") : t("usersDisabled")}</Text>
          </>
        ) : (
          <Text style={styles.muted}>—</Text>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  title: { fontSize: 22, fontWeight: "700", color: colors.text, marginBottom: 6 },
  sub: { fontSize: 14, color: colors.textMuted, marginBottom: 20 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardTitle: { fontSize: 16, fontWeight: "700", color: colors.primary, marginBottom: 10 },
  row: { fontSize: 15, color: colors.text, marginBottom: 6 },
  catText: { fontSize: 14, color: colors.text, lineHeight: 20 },
  meta: { fontSize: 12, color: colors.textMuted, marginTop: 8 },
  muted: { color: colors.textMuted },
  err: { color: colors.error },
});
