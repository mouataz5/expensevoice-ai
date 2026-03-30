import { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, Image, ActivityIndicator, ScrollView, Linking } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { scanInvoice, getInvoice, getInvoicePdfUrl, getInvoicePreview, type InvoicePreview } from "../../src/api/invoices";
import Toast from "react-native-toast-message";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { getStoredToken } from "../../src/lib/secure-store";

type TxType = "buy" | "sell" | null;

export default function ScanScreen() {
  const { t } = useLocale();
  const [txType, setTxType] = useState<TxType>(null);
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [ready, setReady] = useState(false);
  const [preview, setPreview] = useState<InvoicePreview | null>(null);

  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") {
      Toast.show({ type: "error", text1: t("error"), text2: "Permission required" });
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, allowsEditing: true, quality: 0.9 });
    if (!result.canceled) {
      setImageUri(result.assets[0].uri);
      setReady(false);
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      Toast.show({ type: "error", text1: t("error"), text2: "Camera permission required" });
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ allowsEditing: true, quality: 0.9 });
    if (!result.canceled) {
      setImageUri(result.assets[0].uri);
      setReady(false);
    }
  };

  const uploadAndPoll = async () => {
    if (!imageUri || txType === null) return;
    setProcessing(true);
    setStatus("processing");
    setPreview(null);
    try {
      const { invoice_id, status: s } = await scanInvoice(imageUri, txType);
      setInvoiceId(invoice_id);
      setStatus(s);
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const inv = await getInvoice(invoice_id);
        setStatus(inv.status);
        if (inv.status === "ready" || inv.status === "ready_for_review") {
          setReady(true);
          try {
            const data = await getInvoicePreview(invoice_id);
            setPreview(data);
          } catch {
            // Preview optional; user can still download PDF
          }
          break;
        }
        if (inv.status === "failed") {
          Toast.show({ type: "error", text1: t("error"), text2: inv.error_message || "Processing failed" });
          break;
        }
      }
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    } finally {
      setProcessing(false);
    }
  };

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

  const reset = () => {
    setImageUri(null);
    setInvoiceId(null);
    setStatus("");
    setReady(false);
    setPreview(null);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.label}>{t("selectType")}</Text>
      <View style={styles.row}>
        <TouchableOpacity style={[styles.txBtn, txType === "buy" && styles.txBtnActive]} onPress={() => setTxType("buy")} accessibilityLabel={t("buy")} accessibilityRole="button">
          <Text style={[styles.txBtnText, txType === "buy" && styles.txBtnTextActive]} pointerEvents="none">{t("buy")}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.txBtn, txType === "sell" && styles.txBtnActive]} onPress={() => setTxType("sell")} accessibilityLabel={t("sell")} accessibilityRole="button">
          <Text style={[styles.txBtnText, txType === "sell" && styles.txBtnTextActive]} pointerEvents="none">{t("sell")}</Text>
        </TouchableOpacity>
      </View>

      {!imageUri ? (
        <View style={styles.uploadRow}>
          <TouchableOpacity style={[styles.uploadBtn, (!txType || processing) && styles.uploadBtnDisabled]} onPress={pickImage} disabled={!txType || processing} accessibilityLabel={t("pickImage")} accessibilityRole="button">
            <Text style={styles.uploadBtnText} pointerEvents="none">{t("pickImage")}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.uploadBtn, (!txType || processing) && styles.uploadBtnDisabled]} onPress={takePhoto} disabled={!txType || processing} accessibilityLabel={t("takePhoto")} accessibilityRole="button">
            <Text style={styles.uploadBtnText} pointerEvents="none">{t("takePhoto")}</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          <Image source={{ uri: imageUri }} style={styles.preview} />
          {!ready ? (
            <>
              <TouchableOpacity style={[styles.submitBtn, processing && styles.submitBtnDisabled]} onPress={uploadAndPoll} disabled={processing} accessibilityLabel={t("uploadInvoice")} accessibilityRole="button">
                {processing ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitBtnText} pointerEvents="none">{t("uploadInvoice")}</Text>}
              </TouchableOpacity>
              {processing && <Text style={styles.statusText}>{t("processing")} — {status}</Text>}
            </>
          ) : (
            <>
              {preview && (
                <View style={styles.reviewCard}>
                  <Text style={styles.reviewTitle}>{t("readyForReview")}</Text>
                  {preview.confidence > 0 && (
                    <Text style={styles.confidenceText}>
                      {t("confidence")}: {Math.round(preview.confidence * 100)}%
                    </Text>
                  )}
                  {preview.supplier_name ? (
                    <Text style={styles.reviewRow}><Text style={styles.reviewLabel}>Fournisseur: </Text>{preview.supplier_name}</Text>
                  ) : null}
                  {preview.invoice_number ? (
                    <Text style={styles.reviewRow}><Text style={styles.reviewLabel}>N°: </Text>{preview.invoice_number}</Text>
                  ) : null}
                  {preview.invoice_date ? (
                    <Text style={styles.reviewRow}><Text style={styles.reviewLabel}>Date: </Text>{preview.invoice_date}</Text>
                  ) : null}
                  {preview.items?.length > 0 && (
                    <View style={styles.itemsBlock}>
                      <Text style={styles.reviewLabel}>Articles</Text>
                      {preview.items.map((item, idx) => (
                        <View key={idx} style={styles.itemRow}>
                          <Text style={styles.itemDesignation} numberOfLines={2}>{item.designation ?? "—"}</Text>
                          <Text style={styles.itemQty}>Qté: {item.quantity ?? "—"}</Text>
                          <Text style={styles.itemPrice}>P.U: {item.unit_price ?? "—"} {preview.currency}</Text>
                          <Text style={styles.itemTotal}>Total: {item.line_total ?? "—"} {preview.currency}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                  {(preview.total_ttc != null || (preview.totals?.ttc != null)) && (
                    <Text style={styles.totalRow}>
                      <Text style={styles.reviewLabel}>Net à payer: </Text>
                      {(preview.total_ttc ?? preview.totals?.ttc ?? 0)} {preview.currency}
                    </Text>
                  )}
                </View>
              )}
              <TouchableOpacity style={styles.pdfBtn} onPress={downloadPdf} accessibilityLabel={t("downloadPdf")} accessibilityRole="button">
                <Text style={styles.pdfBtnText} pointerEvents="none">{t("downloadPdf")}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.resetBtn} onPress={reset} accessibilityLabel={t("retry")} accessibilityRole="button">
                <Text style={styles.resetBtnText} pointerEvents="none">{t("retry")}</Text>
              </TouchableOpacity>
            </>
          )}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  label: { fontSize: 16, color: colors.text, marginBottom: 12, fontWeight: "500" },
  row: { flexDirection: "row", gap: 12, marginBottom: 24 },
  txBtn: { flex: 1, padding: 16, borderRadius: 12, backgroundColor: colors.surfaceMuted, alignItems: "center" },
  txBtnActive: { backgroundColor: colors.primary },
  txBtnText: { fontSize: 16, color: colors.text },
  txBtnTextActive: { color: "#fff", fontWeight: "600" },
  uploadRow: { flexDirection: "row", gap: 12, marginBottom: 12 },
  uploadBtn: { flex: 1, backgroundColor: colors.accent, padding: 20, borderRadius: 12, alignItems: "center" },
  uploadBtnDisabled: { opacity: 0.6 },
  uploadBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  preview: { width: "100%", height: 220, borderRadius: 12, backgroundColor: colors.surfaceMuted, marginBottom: 16 },
  submitBtn: { backgroundColor: colors.primary, padding: 16, borderRadius: 12, alignItems: "center", marginBottom: 8 },
  submitBtnDisabled: { opacity: 0.7 },
  submitBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  statusText: { color: colors.textMuted, fontSize: 14, marginTop: 8 },
  reviewCard: { backgroundColor: colors.surface, borderRadius: 12, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  reviewTitle: { fontSize: 18, fontWeight: "600", color: colors.primary, marginBottom: 12 },
  confidenceText: { fontSize: 14, color: colors.textMuted, marginBottom: 8 },
  reviewLabel: { fontWeight: "600", color: colors.textMuted },
  reviewRow: { fontSize: 14, color: colors.text, marginBottom: 6 },
  itemsBlock: { marginTop: 12, marginBottom: 8 },
  itemRow: { flexDirection: "row", flexWrap: "wrap", marginBottom: 6, paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: colors.border },
  itemDesignation: { flex: 1, fontSize: 14, color: colors.text, minWidth: "100%" },
  itemQty: { fontSize: 12, color: colors.textMuted, marginRight: 8 },
  itemPrice: { fontSize: 12, color: colors.textMuted, marginRight: 8 },
  itemTotal: { fontSize: 12, fontWeight: "600", color: colors.text },
  totalRow: { fontSize: 16, fontWeight: "600", color: colors.text, marginTop: 8 },
  pdfBtn: { backgroundColor: colors.primary, padding: 16, borderRadius: 12, alignItems: "center", marginBottom: 12 },
  pdfBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  resetBtn: { alignItems: "center" },
  resetBtnText: { color: colors.primary, fontSize: 14 },
});
