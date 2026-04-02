import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Linking,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { useLocale } from "../../../src/context/LocaleContext";
import { colors } from "../../../src/theme/colors";
import {
  getInvoice,
  getInvoicePreview,
  getInvoicePdfUrl,
  type InvoicePreview,
} from "../../../src/api/invoices";
import { getStoredToken } from "../../../src/lib/secure-store";
import { queryKeys } from "../../../src/queryKeys";
import Toast from "react-native-toast-message";

export default function InvoiceDetailScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const invoiceId = typeof id === "string" ? id : id?.[0] ?? "";
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<InvoicePreview | null>(null);

  const { data: inv, isLoading } = useQuery({
    queryKey: queryKeys.invoiceDetail(invoiceId),
    queryFn: () => getInvoice(invoiceId),
    enabled: !!invoiceId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "processing" ? 2000 : false;
    },
  });

  useEffect(() => {
    if (!inv || !invoiceId) return;
    const loadPreview = async () => {
      if (inv.status !== "ready" && inv.status !== "ready_for_review" && inv.status !== "approved") {
        setPreview(null);
        return;
      }
      try {
        const p = await getInvoicePreview(invoiceId);
        setPreview(p);
      } catch {
        setPreview(null);
      }
    };
    void loadPreview();
  }, [invoiceId, inv]);

  const downloadPdf = async () => {
    if (!invoiceId) return;
    try {
      const token = await getStoredToken();
      const url = getInvoicePdfUrl(invoiceId);
      const path = `${FileSystem.cacheDirectory}invoice_${invoiceId}.pdf`;
      await FileSystem.downloadAsync(url, path, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(path, { mimeType: "application/pdf", dialogTitle: t("downloadPdf") });
      } else {
        Linking.openURL(path);
      }
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    }
  };

  if (!invoiceId) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{t("error")}</Text>
      </View>
    );
  }

  if (isLoading || !inv) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  const canPdf =
    inv.status === "ready" || inv.status === "ready_for_review" || inv.status === "approved";

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <TouchableOpacity style={styles.backRow} onPress={() => router.back()} accessibilityRole="button" accessibilityLabel={t("back")}>
        <Ionicons name="arrow-back" size={22} color={colors.primary} />
        <Text style={styles.backText}>{t("back")}</Text>
      </TouchableOpacity>

      <Text style={styles.title}>{t("invoiceDetail")}</Text>
      <View style={[styles.chip, { backgroundColor: colors.surfaceMuted }]}>
        <Text style={styles.chipText}>{inv.status}</Text>
      </View>
      {inv.error_message ? <Text style={styles.errorMsg}>{inv.error_message}</Text> : null}

      {inv.status === "processing" ? (
        <View style={styles.loadingRow}>
          <ActivityIndicator color={colors.primary} />
          <Text style={styles.muted}>{t("processing")}</Text>
        </View>
      ) : null}

      {preview ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t("readyForReview")}</Text>
          {preview.confidence > 0 ? (
            <Text style={styles.meta}>
              {t("confidence")}: {Math.round(preview.confidence * 100)}%
            </Text>
          ) : null}
          {preview.supplier_name ? (
            <Text style={styles.row}>
              <Text style={styles.label}>Fournisseur: </Text>
              {preview.supplier_name}
            </Text>
          ) : null}
          {preview.invoice_number ? (
            <Text style={styles.row}>
              <Text style={styles.label}>N°: </Text>
              {preview.invoice_number}
            </Text>
          ) : null}
          {(preview.total_ttc != null || preview.totals?.ttc != null) && (
            <Text style={styles.total}>
              {preview.total_ttc ?? preview.totals?.ttc} {preview.currency}
            </Text>
          )}
        </View>
      ) : null}

      {canPdf ? (
        <TouchableOpacity style={styles.pdfBtn} onPress={downloadPdf} accessibilityRole="button">
          <Text style={styles.pdfBtnText}>{t("downloadPdf")}</Text>
        </TouchableOpacity>
      ) : null}

      <TouchableOpacity
        style={styles.secondaryBtn}
        onPress={() => {
          queryClient.invalidateQueries({ queryKey: queryKeys.invoicesMe });
          router.back();
        }}
        accessibilityRole="button"
      >
        <Text style={styles.secondaryBtnText}>{t("close")}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  backRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 16 },
  backText: { fontSize: 16, color: colors.primary, fontWeight: "600" },
  title: { fontSize: 22, fontWeight: "700", color: colors.primary, marginBottom: 12 },
  chip: { alignSelf: "flex-start", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, marginBottom: 12 },
  chipText: { fontSize: 13, fontWeight: "600", color: colors.primary },
  errorMsg: { color: colors.error, marginBottom: 12 },
  loadingRow: { flexDirection: "row", alignItems: "center", gap: 12, marginVertical: 16 },
  muted: { color: colors.textMuted, fontSize: 14 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginTop: 8,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardTitle: { fontSize: 18, fontWeight: "600", color: colors.primary, marginBottom: 12 },
  meta: { fontSize: 14, color: colors.textMuted, marginBottom: 8 },
  row: { fontSize: 14, color: colors.text, marginBottom: 6 },
  label: { fontWeight: "600", color: colors.textMuted },
  total: { fontSize: 16, fontWeight: "700", color: colors.text, marginTop: 8 },
  pdfBtn: { backgroundColor: colors.primary, padding: 16, borderRadius: 12, alignItems: "center", marginBottom: 12 },
  pdfBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  secondaryBtn: { padding: 14, alignItems: "center" },
  secondaryBtnText: { color: colors.primary, fontSize: 16, fontWeight: "600" },
});
