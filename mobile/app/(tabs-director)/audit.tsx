import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
} from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, shadow, space } from "../../src/theme/tokens";
import { queryKeys } from "../../src/queryKeys";
import { fetchAudit, type AuditRow } from "../../src/api/audit";
import {
  TextFieldInput,
  ErrorState,
  EmptyState,
  ProductBrandMark,
  SectionTitle,
  AuditListSkeleton,
} from "../../src/components/ui";
import { AdminAccentStripe, AdminErrorShell, AdminHeader } from "../../src/components/admin";
import { formatApiError } from "../../src/utils/apiError";

export default function DirectorAuditScreen() {
  const { t } = useLocale();
  const [filter, setFilter] = useState("");

  const q = useQuery({
    queryKey: queryKeys.auditList,
    queryFn: () => fetchAudit({ limit: 200 }),
  });

  const filtered = useMemo(() => {
    const rows = q.data ?? [];
    const s = filter.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r: AuditRow) => {
      const blob = `${r.action} ${r.entity_type} ${r.entity_id} ${r.message} ${r.actor_role}`.toLowerCase();
      return blob.includes(s);
    });
  }, [q.data, filter]);

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

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} />}
    >
      <AdminAccentStripe />
      <ProductBrandMark title={t("appName")} subtitle={t("auditTab")} />
      <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("adminAuditWorkspaceSubtitle")} />
      <SectionTitle title={t("auditTitle")} subtitle={t("auditSubtitle")} />

      {q.isLoading ? (
        <AuditListSkeleton count={8} />
      ) : (
        <>
          <TextFieldInput
            value={filter}
            onChangeText={setFilter}
            placeholder={t("auditSearchPlaceholder")}
            accessibilityLabel={t("auditSearchPlaceholder")}
            style={styles.search}
          />

          {!q.data?.length ? (
            <EmptyState icon="reader-outline" title={t("auditEmpty")} subtitle={t("adminAuditEmptySub")} />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon="search-outline"
              title={t("noSearchResults")}
              subtitle={t("directorAuditFilteredEmpty")}
              actionLabel={t("adminClearFilter")}
              onAction={() => setFilter("")}
            />
          ) : (
            filtered.slice(0, 80).map((r: AuditRow) => (
              <View key={r.id} style={styles.row}>
                <Text style={styles.action}>{r.action}</Text>
                <Text style={styles.meta}>
                  {r.actor_role} · {r.entity_type} · {r.created_at.slice(0, 19)}
                </Text>
                <Text style={styles.msg}>{r.message}</Text>
              </View>
            ))
          )}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, paddingBottom: space.xxxl },
  search: { marginBottom: space.md },
  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: space.md,
    marginBottom: space.sm,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow.soft,
  },
  action: { fontSize: font.sm, fontWeight: font.bold, color: colors.primary, marginBottom: space.xs },
  meta: { fontSize: font.xs, color: colors.textMuted, marginBottom: space.xs },
  msg: { fontSize: font.sm, color: colors.text, lineHeight: 20 },
});
