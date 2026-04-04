import { useQuery } from "@tanstack/react-query";
import { Text, StyleSheet, ScrollView, RefreshControl } from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, shadow, space } from "../../src/theme/tokens";
import { queryKeys } from "../../src/queryKeys";
import { fetchActivePolicies } from "../../src/api/policies-read";
import {
  Card,
  ErrorState,
  ProductBrandMark,
  SectionTitle,
  PolicyCardsSkeleton,
} from "../../src/components/ui";
import { AdminAccentStripe, AdminErrorShell, AdminHeader } from "../../src/components/admin";
import { formatApiError } from "../../src/utils/apiError";

export default function DirectorPoliciesScreen() {
  const { t } = useLocale();
  const q = useQuery({
    queryKey: queryKeys.policiesActive,
    queryFn: fetchActivePolicies,
  });

  const errFmt = q.isError ? formatApiError(q.error, t) : null;

  if (q.isError && errFmt) {
    return (
      <AdminErrorShell>
        <ErrorState
          title={t("error")}
          message={errFmt.message}
          hint={errFmt.hint}
          onRetry={() => q.refetch()}
          retryLabel={t("retry")}
        />
      </AdminErrorShell>
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
      <AdminAccentStripe />
      <ProductBrandMark title={t("appName")} subtitle={t("policiesTab")} />
      <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("adminPoliciesWorkspaceSubtitle")} />
      <SectionTitle title={t("policiesTitle")} subtitle={t("policiesSubtitle")} />

      {q.isLoading ? (
        <PolicyCardsSkeleton />
      ) : (
        <>
          <Card style={styles.card}>
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
          </Card>

          <Card style={styles.card}>
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
          </Card>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, paddingBottom: space.xxxl },
  card: {
    marginBottom: space.md,
    ...shadow.soft,
  },
  cardTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.primaryDark, marginBottom: space.sm },
  row: { fontSize: font.md, color: colors.text, marginBottom: space.xs, lineHeight: 22 },
  catText: { fontSize: font.sm, color: colors.text, lineHeight: 22 },
  meta: { fontSize: font.xs, color: colors.textMuted, marginTop: space.sm, fontWeight: font.semibold },
  muted: { color: colors.textMuted, fontSize: font.md },
});
