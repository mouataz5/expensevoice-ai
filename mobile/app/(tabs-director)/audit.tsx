import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { queryKeys } from "../../src/queryKeys";
import { fetchAudit, type AuditRow } from "../../src/api/audit";

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

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} />}
    >
      <Text style={styles.title}>{t("auditTitle")}</Text>
      <Text style={styles.sub}>{t("auditSubtitle")}</Text>
      <TextInput
        style={styles.search}
        value={filter}
        onChangeText={setFilter}
        placeholder={t("auditSearchPlaceholder")}
        placeholderTextColor={colors.textMuted}
      />

      {filtered.length === 0 ? (
        <Text style={styles.muted}>{t("auditEmpty")}</Text>
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
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 40 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  title: { fontSize: 22, fontWeight: "700", color: colors.text, marginBottom: 6 },
  sub: { fontSize: 14, color: colors.textMuted, marginBottom: 12 },
  search: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  row: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  action: { fontSize: 14, fontWeight: "700", color: colors.primary, marginBottom: 4 },
  meta: { fontSize: 12, color: colors.textMuted, marginBottom: 4 },
  msg: { fontSize: 14, color: colors.text },
  muted: { color: colors.textMuted, textAlign: "center", marginTop: 24 },
  err: { color: colors.error },
});
