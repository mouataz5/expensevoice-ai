import { View, Text, StyleSheet } from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";

export default function DirectorEmployeesScreen() {
  const { t } = useLocale();
  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.title}>{t("employees")}</Text>
        <Text style={styles.hint}>List of employees — coming soon</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: 20 },
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
  title: { fontSize: 20, fontWeight: "700", color: colors.primary, marginBottom: 8 },
  hint: { fontSize: 14, color: colors.textMuted },
});
