import { useQuery } from "@tanstack/react-query";
import { View, Text, StyleSheet, FlatList, ActivityIndicator, RefreshControl } from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { listMyAlerts, type AlertOut } from "../../src/api/alerts";
import { queryKeys } from "../../src/queryKeys";

function AlertRow({ item }: { item: AlertOut }) {
  const isCritical = item.severity === "critical";
  return (
    <View style={[styles.row, isCritical && styles.rowCritical]}>
      <Text style={styles.rowType}>{item.alert_type}</Text>
      <Text style={styles.rowMessage} numberOfLines={2}>{item.message}</Text>
      <Text style={styles.rowMeta}>{item.severity} · {item.status}</Text>
    </View>
  );
}

export default function AlertsScreen() {
  const { t } = useLocale();
  const { data: alerts, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: queryKeys.alertsMe,
    queryFn: listMyAlerts,
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
        <Text style={styles.errorSub}>{String(error)}</Text>
      </View>
    );
  }

  if (!alerts?.length) {
    return (
      <FlatList
        data={[]}
        ListEmptyComponent={
          <View style={styles.centered}>
            <Text style={styles.emptyTitle}>{t("noAlerts")}</Text>
            <Text style={styles.emptySub}>{t("emptyList")}</Text>
          </View>
        }
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        contentContainerStyle={[styles.list, styles.listFlex]}
        style={styles.container}
      />
    );
  }

  return (
    <FlatList
      data={alerts}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <AlertRow item={item} />}
      contentContainerStyle={styles.list}
      style={styles.container}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { padding: 16, paddingBottom: 40 },
  listFlex: { flexGrow: 1 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, backgroundColor: colors.background },
  row: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderLeftColor: colors.warning,
  },
  rowCritical: { borderLeftColor: colors.critical },
  rowType: { fontSize: 14, fontWeight: "600", color: colors.text, marginBottom: 4 },
  rowMessage: { fontSize: 14, color: colors.textMuted, marginBottom: 4 },
  rowMeta: { fontSize: 12, color: colors.textMuted },
  errorText: { fontSize: 18, color: colors.error, marginBottom: 8 },
  errorSub: { fontSize: 14, color: colors.textMuted },
  emptyTitle: { fontSize: 18, fontWeight: "600", color: colors.text, marginBottom: 8 },
  emptySub: { fontSize: 14, color: colors.textMuted },
});
