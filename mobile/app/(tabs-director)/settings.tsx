import { useEffect, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  TextInput,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { fetchSettings, updateSettings } from "../../src/api/settings";
import Toast from "react-native-toast-message";

export default function DirectorSettingsScreen() {
  const { user, signOut } = useAuth();
  const { t, locale, setLocale } = useLocale();
  const router = useRouter();
  const qc = useQueryClient();
  const isAdmin = user?.role === "admin";

  const [companyName, setCompanyName] = useState("");
  const [currency, setCurrency] = useState("TND");
  const [maxPerPurchase, setMaxPerPurchase] = useState("500");
  const [dailyLimit, setDailyLimit] = useState("1500");

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  useEffect(() => {
    if (!settings) return;
    setCompanyName(settings.company_name ?? "");
    setCurrency(settings.currency ?? "TND");
    setMaxPerPurchase(
      String(settings.default_limits?.max_per_purchase ?? 500)
    );
    setDailyLimit(
      String(settings.default_limits?.daily_limit_default ?? 1500)
    );
  }, [settings]);

  const updateM = useMutation({
    mutationFn: (payload: Parameters<typeof updateSettings>[0]) =>
      updateSettings(payload),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("settingsSaved") });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: () => Toast.show({ type: "error", text1: t("error") }),
  });

  const handleSave = () => {
    const max = parseInt(maxPerPurchase, 10);
    const daily = parseInt(dailyLimit, 10);
    if (isNaN(max) || isNaN(daily)) return;
    updateM.mutate({
      company_name: companyName || undefined,
      currency: currency || undefined,
      default_limits: { max_per_purchase: max, daily_limit_default: daily },
    });
  };

  const handleLogout = async () => {
    await signOut();
    router.replace("/login");
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.card}>
        <Text style={styles.title}>{t("settings")}</Text>
        <Text style={styles.email}>{user?.email ?? ""}</Text>
        <Text style={styles.role}>{user?.role ?? ""}</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>{t("language")}</Text>
        <View style={styles.langRow}>
          {(["ar", "fr", "en"] as const).map((l) => (
            <TouchableOpacity
              key={l}
              style={[styles.langBtn, locale === l && styles.langBtnActive]}
              onPress={() => setLocale(l)}
            >
              <Text
                style={[
                  styles.langBtnText,
                  locale === l && styles.langBtnTextActive,
                ]}
                pointerEvents="none"
              >
                {l.toUpperCase()}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {isLoading ? (
        <View style={styles.card}>
          <ActivityIndicator size="small" color={colors.primary} />
        </View>
      ) : (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t("settingsCompanyName")}</Text>
          <TextInput
            style={styles.input}
            value={companyName}
            onChangeText={setCompanyName}
            placeholder={t("settingsCompanyName")}
            placeholderTextColor={colors.textMuted}
            editable={isAdmin}
          />
          <Text style={styles.label}>{t("settingsCurrency")}</Text>
          <TextInput
            style={styles.input}
            value={currency}
            onChangeText={setCurrency}
            placeholder="TND"
            placeholderTextColor={colors.textMuted}
            editable={isAdmin}
          />
          <Text style={styles.label}>Max / purchase</Text>
          <TextInput
            style={styles.input}
            value={maxPerPurchase}
            onChangeText={setMaxPerPurchase}
            placeholder="500"
            placeholderTextColor={colors.textMuted}
            keyboardType="numeric"
            editable={isAdmin}
          />
          <Text style={styles.label}>Daily limit (default)</Text>
          <TextInput
            style={styles.input}
            value={dailyLimit}
            onChangeText={setDailyLimit}
            placeholder="1500"
            placeholderTextColor={colors.textMuted}
            keyboardType="numeric"
            editable={isAdmin}
          />
          {isAdmin && (
            <TouchableOpacity
              style={styles.saveBtn}
              onPress={handleSave}
              disabled={updateM.isPending}
            >
              <Text style={styles.saveBtnText} pointerEvents="none">
                {updateM.isPending ? "…" : t("settingsSave")}
              </Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutBtnText} pointerEvents="none">
          {t("logout")}
        </Text>
      </TouchableOpacity>
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
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
    color: colors.primary,
    marginBottom: 8,
  },
  email: { fontSize: 16, color: colors.text, marginBottom: 4 },
  role: { fontSize: 14, color: colors.textMuted },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.text,
    marginBottom: 12,
  },
  label: {
    fontSize: 14,
    color: colors.textMuted,
    marginTop: 12,
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
  },
  langRow: { flexDirection: "row", gap: 12 },
  langBtn: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: colors.surfaceMuted,
  },
  langBtnActive: { backgroundColor: colors.primary },
  langBtnText: { fontSize: 14, color: colors.text },
  langBtnTextActive: { color: "#fff", fontWeight: "600" },
  saveBtn: {
    marginTop: 20,
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: "center",
  },
  saveBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  logoutBtn: {
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.error,
    alignItems: "center",
  },
  logoutBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
