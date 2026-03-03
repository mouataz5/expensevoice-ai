import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { getStoredToken } from "../../src/lib/secure-store";
import { baseURL } from "../../src/api/client";

export default function DirectorReportsScreen() {
  const { t } = useLocale();

  const downloadReport = async (path: string, filename: string) => {
    try {
      const token = await getStoredToken();
      const url = `${baseURL}${path}`;
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64 = (reader.result as string)?.split(",")[1];
        if (base64) {
          const { shareAsync } = require("expo-sharing");
          const fs = require("expo-file-system");
          const filePath = `${fs.cacheDirectory}${filename}`;
          fs.writeAsStringAsync(filePath, base64, { encoding: fs.EncodingType.Base64 }).then(() => {
            shareAsync(filePath, { mimeType: path.endsWith(".pdf") ? "application/pdf" : "text/csv", dialogTitle: filename });
          });
        }
      };
      reader.readAsDataURL(blob);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.title}>{t("reports")}</Text>
        <TouchableOpacity style={styles.btn} onPress={() => downloadReport("/export/stats.pdf", "stats.pdf")}>
          <Text style={styles.btnText}>Stats PDF</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.btn} onPress={() => downloadReport("/export/alerts.csv", "alerts.csv")}>
          <Text style={styles.btnText}>Alerts CSV</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.btn} onPress={() => downloadReport("/export/audit.csv", "audit.csv")}>
          <Text style={styles.btnText}>Audit CSV</Text>
        </TouchableOpacity>
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
  title: { fontSize: 20, fontWeight: "700", color: colors.primary, marginBottom: 16 },
  btn: { backgroundColor: colors.primary, padding: 16, borderRadius: 12, alignItems: "center", marginBottom: 12 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
