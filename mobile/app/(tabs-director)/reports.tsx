import { View, Text, StyleSheet } from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, space } from "../../src/theme/tokens";
import { getStoredToken } from "../../src/lib/secure-store";
import { baseURL } from "../../src/api/client";
import { Card, PrimaryButton, SecondaryButton, ProductBrandMark, SectionTitle } from "../../src/components/ui";
import { AdminAccentStripe, AdminHeader } from "../../src/components/admin";
import Toast from "react-native-toast-message";
import { formatApiError } from "../../src/utils/apiError";

export default function DirectorReportsScreen() {
  const { t } = useLocale();

  const downloadReport = async (path: string, filename: string) => {
    try {
      const token = await getStoredToken();
      const url = `${baseURL}${path}`;
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64 = (reader.result as string)?.split(",")[1];
        if (!base64) {
          Toast.show({ type: "error", text1: t("directorReportFail") });
          return;
        }
        const filePath = `${FileSystem.cacheDirectory}${filename}`;
        await FileSystem.writeAsStringAsync(filePath, base64, {
          encoding: FileSystem.EncodingType.Base64,
        });
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(filePath, {
            mimeType: path.endsWith(".pdf") ? "application/pdf" : "text/csv",
            dialogTitle: filename,
          });
          Toast.show({ type: "success", text1: t("directorReportSuccess") });
        }
      };
      reader.readAsDataURL(blob);
    } catch (e: unknown) {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("directorReportFail"), text2: message });
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.pad}>
        <AdminAccentStripe />
        <ProductBrandMark title={t("appName")} subtitle={t("reports")} />
        <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("adminReportsWorkspaceSubtitle")} />
        <Text style={styles.intro}>{t("directorReportsIntro")}</Text>
        <SectionTitle title={t("reports")} />
        <Card style={styles.card}>
          <PrimaryButton
            title={t("directorReportStatsPdf")}
            onPress={() => void downloadReport("/export/stats.pdf", "stats.pdf")}
            icon="document-outline"
          />
          <SecondaryButton
            title={t("directorReportAlertsCsv")}
            onPress={() => void downloadReport("/export/alerts.csv", "alerts.csv")}
            icon="notifications-outline"
          />
          <SecondaryButton
            title={t("directorReportAuditCsv")}
            onPress={() => void downloadReport("/export/audit.csv", "audit.csv")}
            icon="reader-outline"
          />
          <SecondaryButton
            title={t("directorReportFinanceCsv")}
            onPress={() => void downloadReport("/dashboard/finance-report.csv", "finance-report.csv")}
            icon="cash-outline"
          />
        </Card>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  pad: { padding: space.lg, paddingBottom: space.xxxl },
  intro: { fontSize: font.sm, color: colors.textMuted, lineHeight: 20, marginBottom: space.lg, maxWidth: 360 },
  card: { gap: space.sm },
});
