import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";

export default function ProfileScreen() {
  const { user, signOut } = useAuth();
  const { t, locale, setLocale } = useLocale();
  const router = useRouter();

  const handleLogout = async () => {
    await signOut();
    router.replace("/login");
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.card}>
        <Text style={styles.title}>{t("profile")}</Text>
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
              <Text style={[styles.langBtnText, locale === l && styles.langBtnTextActive]}>{l.toUpperCase()}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutBtnText}>{t("logout")}</Text>
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
  title: { fontSize: 20, fontWeight: "700", color: colors.primary, marginBottom: 8 },
  email: { fontSize: 16, color: colors.text, marginBottom: 4 },
  role: { fontSize: 14, color: colors.textMuted },
  sectionTitle: { fontSize: 16, fontWeight: "600", color: colors.text, marginBottom: 12 },
  langRow: { flexDirection: "row", gap: 12 },
  langBtn: { paddingHorizontal: 20, paddingVertical: 12, borderRadius: 12, backgroundColor: colors.surfaceMuted },
  langBtnActive: { backgroundColor: colors.primary },
  langBtnText: { fontSize: 14, color: colors.text },
  langBtnTextActive: { color: "#fff", fontWeight: "600" },
  logoutBtn: { marginTop: 24, padding: 16, borderRadius: 12, backgroundColor: colors.error, alignItems: "center" },
  logoutBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
