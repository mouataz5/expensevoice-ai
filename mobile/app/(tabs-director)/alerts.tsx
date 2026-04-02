import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { listAllAlerts, resolveAlert, type AlertOut } from "../../src/api/alerts";
import Toast from "react-native-toast-message";

export default function DirectorAlertsScreen() {
  const { t } = useLocale();
  const qc = useQueryClient();
  const { data: alerts, isLoading, error, refetch } = useQuery({
    queryKey: ["alerts-director"],
    queryFn: listAllAlerts,
  });

  const resolveM = useMutation({
    mutationFn: (id: string) => resolveAlert(id),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("alertsResolved") });
      qc.invalidateQueries({ queryKey: ["alerts-director"] });
    },
    onError: () => Toast.show({ type: "error", text1: t("error") }),
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
        <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryBtnText} pointerEvents="none">
            {t("retry")}
          </Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!alerts?.length) {
    return (
      <View style={styles.centered}>
        <Text style={styles.emptyTitle}>{t("noAlerts")}</Text>
        <Text style={styles.emptySub}>{t("emptyList")}</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={alerts}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <View
          style={[
            styles.row,
            item.severity === "critical" && styles.rowCritical,
          ]}
        >
          <View style={styles.rowContent}>
            <Text style={styles.rowType}>{item.alert_type}</Text>
            <Text style={styles.rowMessage} numberOfLines={2}>
              {item.message}
            </Text>
            <Text style={styles.rowMeta}>
              {item.severity} · {item.status}
            </Text>
          </View>
          {item.status !== "resolved" && (
            <TouchableOpacity
              style={styles.resolveBtn}
              onPress={() => resolveM.mutate(item.id)}
              disabled={resolveM.isPending}
            >
              <Text style={styles.resolveBtnText} pointerEvents="none">
                {t("alertsResolve")}
              </Text>
            </TouchableOpacity>
          )}
        </View>
      )}
      contentContainerStyle={styles.list}
      style={styles.container}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { padding: 16, paddingBottom: 40 },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: colors.background,
  },
  errorText: { fontSize: 18, color: colors.error, marginBottom: 8 },
  retryBtn: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: colors.primary,
    borderRadius: 12,
  },
  retryBtnText: { color: "#fff", fontWeight: "600" },
  emptyTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: colors.text,
    marginBottom: 8,
  },
  emptySub: { fontSize: 14, color: colors.textMuted },
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
  rowContent: { marginBottom: 8 },
  rowType: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.text,
    marginBottom: 4,
  },
  rowMessage: { fontSize: 14, color: colors.textMuted, marginBottom: 4 },
  rowMeta: { fontSize: 12, color: colors.textMuted },
  resolveBtn: {
    alignSelf: "flex-start",
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: colors.primary,
    borderRadius: 10,
  },
  resolveBtnText: { color: "#fff", fontSize: 14, fontWeight: "600" },
});
