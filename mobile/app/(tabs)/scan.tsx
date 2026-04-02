import { useMemo, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Image,
  ActivityIndicator,
  ScrollView,
  Linking,
  Modal,
  TextInput,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useQueryClient } from "@tanstack/react-query";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import {
  applyInvoiceCorrections,
  getInvoice,
  getInvoicePdfUrl,
  getInvoicePreview,
  retryInvoiceExtraction,
  scanInvoice,
  type InvoicePreview,
} from "../../src/api/invoices";
import { queryKeys } from "../../src/queryKeys";
import Toast from "react-native-toast-message";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { getStoredToken } from "../../src/lib/secure-store";

type TxType = "buy" | "sell" | null;

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 80;
const MIN_OCR_CHARS_WARN = 80;

function fmtTnAmount(val: number | null | undefined): string {
  if (val == null || Number.isNaN(val)) return "—";
  return new Intl.NumberFormat("fr-TN", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  }).format(val);
}

export default function ScanScreen() {
  const { t } = useLocale();
  const queryClient = useQueryClient();
  const [txType, setTxType] = useState<TxType>(null);
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [ready, setReady] = useState(false);
  const [preview, setPreview] = useState<InvoicePreview | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editSupplier, setEditSupplier] = useState("");
  const [editInvoiceNumber, setEditInvoiceNumber] = useState("");
  const [editInvoiceDate, setEditInvoiceDate] = useState("");
  const [editTotal, setEditTotal] = useState("");
  const [editCurrency, setEditCurrency] = useState("TND");

  const pollUntilReady = async (id: string): Promise<boolean> => {
    let failed = false;
    let lastStatus = "";
    for (let i = 0; i < MAX_POLL_ATTEMPTS; i++) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      const inv = await getInvoice(id);
      lastStatus = inv.status;
      setStatus(inv.status);
      if (inv.status === "ready" || inv.status === "ready_for_review") {
        setReady(true);
        try {
          const data = await getInvoicePreview(id);
          setPreview(data);
        } catch {
          /* preview optional */
        }
        void queryClient.invalidateQueries({ queryKey: queryKeys.invoicesMe });
        return true;
      }
      if (inv.status === "failed") {
        failed = true;
        Toast.show({
          type: "error",
          text1: t("error"),
          text2: inv.error_message || "Processing failed",
        });
        return false;
      }
    }
    if (!failed) {
      Toast.show({
        type: "error",
        text1: t("error"),
        text2:
          lastStatus === "processing"
            ? t("invoiceProcessingTimeout")
            : `${t("error")}: ${lastStatus}`,
      });
    }
    return false;
  };

  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") {
      Toast.show({ type: "error", text1: t("error"), text2: "Permission required" });
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"] as const, allowsEditing: true, quality: 0.9 });
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
    const result = await ImagePicker.launchCameraAsync({ mediaTypes: ["images"] as const, allowsEditing: true, quality: 0.9 });
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
      await pollUntilReady(invoice_id);
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    } finally {
      setProcessing(false);
    }
  };

  const onRetryExtraction = async () => {
    if (!invoiceId) return;
    setProcessing(true);
    try {
      await retryInvoiceExtraction(invoiceId);
      await pollUntilReady(invoiceId);
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    } finally {
      setProcessing(false);
    }
  };

  const openManualEdit = () => {
    if (!preview) return;
    setEditSupplier(preview.supplier_name ?? "");
    setEditInvoiceNumber(preview.invoice_number ?? "");
    setEditInvoiceDate(preview.invoice_date ?? "");
    const raw =
      preview.total_ttc ?? preview.totals?.ttc ?? (preview.extraction as { total_amount?: number } | undefined)?.total_amount;
    setEditTotal(raw != null && !Number.isNaN(Number(raw)) ? String(raw) : "");
    setEditCurrency(preview.currency ?? "TND");
    setEditOpen(true);
  };

  const saveManualCorrections = async () => {
    if (!invoiceId) return;
    const patch: Record<string, unknown> = {};
    if (editSupplier.trim()) patch.supplier_name = editSupplier.trim();
    if (editInvoiceNumber.trim()) patch.invoice_number = editInvoiceNumber.trim();
    if (editInvoiceDate.trim()) patch.invoice_date = editInvoiceDate.trim();
    if (editCurrency.trim()) patch.currency = editCurrency.trim();
    const parsed = parseFloat(String(editTotal).replace(",", "."));
    if (editTotal.trim() && !Number.isNaN(parsed)) patch.total_amount = parsed;
    if (Object.keys(patch).length === 0) {
      Toast.show({ type: "error", text1: t("error"), text2: "Nothing to save" });
      return;
    }
    try {
      const p = await applyInvoiceCorrections(invoiceId, patch);
      setPreview(p);
      setEditOpen(false);
      Toast.show({ type: "success", text1: t("confirm"), text2: t("correctionsSaved") });
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
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

  const scanStepActiveIndex = useMemo(() => {
    if (ready) return 3;
    if (processing) return 2;
    if (imageUri && txType) return 2;
    if (txType) return 1;
    return 0;
  }, [ready, processing, imageUri, txType]);

  const scanStepLabels = [t("stepChooseType"), t("stepMedia"), t("stepSend"), t("stepResult")];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Modal visible={editOpen} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>{t("manualEdit")}</Text>
            <Text style={styles.modalLabel}>Fournisseur</Text>
            <TextInput
              style={styles.modalInput}
              value={editSupplier}
              onChangeText={setEditSupplier}
              placeholder="supplier_name"
            />
            <Text style={styles.modalLabel}>N° facture</Text>
            <TextInput
              style={styles.modalInput}
              value={editInvoiceNumber}
              onChangeText={setEditInvoiceNumber}
            />
            <Text style={styles.modalLabel}>Date (YYYY-MM-DD)</Text>
            <TextInput
              style={styles.modalInput}
              value={editInvoiceDate}
              onChangeText={setEditInvoiceDate}
              placeholder="2026-01-16"
            />
            <Text style={styles.modalLabel}>Total TTC</Text>
            <TextInput
              style={styles.modalInput}
              value={editTotal}
              onChangeText={setEditTotal}
              keyboardType="decimal-pad"
            />
            <Text style={styles.modalLabel}>Devise</Text>
            <TextInput
              style={styles.modalInput}
              value={editCurrency}
              onChangeText={setEditCurrency}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity style={styles.modalCancel} onPress={() => setEditOpen(false)} accessibilityRole="button">
                <Text style={styles.modalCancelText}>{t("cancel")}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSave} onPress={() => void saveManualCorrections()} accessibilityRole="button">
                <Text style={styles.modalSaveText}>{t("saveCorrections")}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
      <View style={styles.stepsRow}>
        {scanStepLabels.map((label, i) => (
          <View key={`scan-step-${i}`} style={[styles.stepPill, i <= scanStepActiveIndex && styles.stepPillActive]}>
            <Text
              style={[styles.stepPillText, i <= scanStepActiveIndex && styles.stepPillTextActive]}
              numberOfLines={2}
            >
              {label}
            </Text>
          </View>
        ))}
      </View>

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
                  {((preview.ocr_text?.length ?? 0) < MIN_OCR_CHARS_WARN ||
                    !!(preview.extraction_error && String(preview.extraction_error).trim())) && (
                    <Text style={styles.warningText}>
                      {(preview.ocr_text?.length ?? 0) < MIN_OCR_CHARS_WARN
                        ? t("scanOcrWeak")
                        : `${t("scanExtractionWarning")}: ${preview.extraction_error}`}
                    </Text>
                  )}
                  {(preview.global_confidence ?? preview.confidence) > 0 && (
                    <Text style={styles.confidenceText}>
                      {t("confidence")}: {Math.round((preview.global_confidence ?? preview.confidence) * 100)}%
                    </Text>
                  )}
                  {(["supplier_name", "invoice_number", "invoice_date", "total_amount"] as const).map((k) => {
                    const v = preview.field_confidence?.[k];
                    if (v == null || v <= 0) return null;
                    return (
                      <Text key={k} style={styles.confidenceText}>
                        {k}: {Math.round(v * 100)}%
                      </Text>
                    );
                  })}
                  {preview.warnings && preview.warnings.length > 0 ? (
                    <>
                      <Text style={styles.sectionLabel}>{t("warningsTitle")}</Text>
                      {preview.warnings.map((w, i) => (
                        <Text key={`w-${i}`} style={styles.warningText}>
                          • {w}
                        </Text>
                      ))}
                    </>
                  ) : null}
                  {preview.missing_fields && preview.missing_fields.length > 0 ? (
                    <>
                      <Text style={styles.sectionLabel}>{t("missingFieldsTitle")}</Text>
                      <Text style={styles.reviewMuted}>{preview.missing_fields.join(", ")}</Text>
                    </>
                  ) : null}
                  <Text style={styles.sectionLabel}>Fournisseur</Text>
                  {preview.supplier_name ? (
                    <Text style={styles.reviewRow}>{preview.supplier_name}</Text>
                  ) : (
                    <Text style={styles.reviewMuted}>—</Text>
                  )}
                  {preview.invoice_number ? (
                    <Text style={styles.reviewRow}><Text style={styles.reviewLabel}>N°: </Text>{preview.invoice_number}</Text>
                  ) : null}
                  {preview.invoice_date ? (
                    <Text style={styles.reviewRow}><Text style={styles.reviewLabel}>Date: </Text>{preview.invoice_date}</Text>
                  ) : null}
                  <Text style={styles.sectionLabel}>Lignes</Text>
                  {preview.items?.length ? (
                    <View style={styles.itemsBlock}>
                      {preview.items.map((item, idx) => (
                        <View key={idx} style={styles.itemRow}>
                          <Text style={styles.itemDesignation} numberOfLines={2}>{item.designation ?? "—"}</Text>
                          <Text style={styles.itemQty}>Qté: {item.quantity ?? "—"}</Text>
                          <Text style={styles.itemPrice}>
                            P.U: {item.unit_price != null ? fmtTnAmount(Number(item.unit_price)) : "—"} {preview.currency}
                          </Text>
                          <Text style={styles.itemTotal}>
                            Total: {item.line_total != null ? fmtTnAmount(Number(item.line_total)) : "—"} {preview.currency}
                          </Text>
                        </View>
                      ))}
                    </View>
                  ) : (
                    <Text style={styles.reviewMuted}>—</Text>
                  )}
                  <Text style={styles.sectionLabel}>Totaux</Text>
                  <Text style={styles.totalRow}>
                    <Text style={styles.reviewLabel}>Net à payer: </Text>
                    {fmtTnAmount(
                      preview.total_ttc ?? preview.totals?.ttc ?? null,
                    )}{" "}
                    {preview.currency}
                  </Text>
                  <View style={styles.actionRow}>
                    <TouchableOpacity style={styles.secondaryBtn} onPress={openManualEdit} accessibilityRole="button">
                      <Text style={styles.secondaryBtnText}>{t("manualEdit")}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.secondaryBtn, processing && styles.secondaryBtnDisabled]}
                      onPress={() => void onRetryExtraction()}
                      disabled={processing}
                      accessibilityRole="button"
                    >
                      <Text style={styles.secondaryBtnText}>{t("retryExtraction")}</Text>
                    </TouchableOpacity>
                  </View>
                  {typeof __DEV__ !== "undefined" && __DEV__ && preview.normalized_text ? (
                    <Text style={styles.debugText} numberOfLines={10}>
                      {t("debugNormalizedOcr")}: {preview.normalized_text.slice(0, 800)}
                    </Text>
                  ) : null}
                </View>
              )}
              <TouchableOpacity style={styles.pdfBtn} onPress={downloadPdf} accessibilityLabel={t("downloadPdf")} accessibilityRole="button">
                <Text style={styles.pdfBtnText} pointerEvents="none">{t("downloadPdf")}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.resetBtn} onPress={reset} accessibilityLabel={t("newInvoice")} accessibilityRole="button">
                <Text style={styles.resetBtnText} pointerEvents="none">{t("newInvoice")}</Text>
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
  stepsRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 20 },
  stepPill: {
    flexGrow: 1,
    minWidth: "47%",
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  stepPillActive: { borderColor: colors.primary, backgroundColor: colors.surfaceMuted },
  stepPillText: { fontSize: 11, color: colors.textMuted, textAlign: "center", fontWeight: "500" },
  stepPillTextActive: { color: colors.primary, fontWeight: "700" },
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
  sectionLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.primary,
    marginTop: 12,
    marginBottom: 6,
    letterSpacing: 0.3,
  },
  reviewMuted: { fontSize: 14, color: colors.textMuted, marginBottom: 6 },
  reviewLabel: { fontWeight: "600", color: colors.textMuted },
  reviewRow: { fontSize: 14, color: colors.text, marginBottom: 6 },
  itemsBlock: { marginTop: 12, marginBottom: 8 },
  itemRow: { flexDirection: "row", flexWrap: "wrap", marginBottom: 6, paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: colors.border },
  itemDesignation: { flex: 1, fontSize: 14, color: colors.text, minWidth: "100%" },
  itemQty: { fontSize: 12, color: colors.textMuted, marginRight: 8 },
  itemPrice: { fontSize: 12, color: colors.textMuted, marginRight: 8 },
  itemTotal: { fontSize: 12, fontWeight: "600", color: colors.text },
  totalRow: { fontSize: 16, fontWeight: "600", color: colors.text, marginTop: 8 },
  warningText: {
    fontSize: 13,
    color: colors.warning,
    marginBottom: 10,
    lineHeight: 18,
  },
  pdfBtn: { backgroundColor: colors.primary, padding: 16, borderRadius: 12, alignItems: "center", marginBottom: 12 },
  pdfBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  resetBtn: { alignItems: "center" },
  resetBtnText: { color: colors.primary, fontSize: 14 },
  actionRow: { flexDirection: "row", gap: 10, marginTop: 14, flexWrap: "wrap" },
  secondaryBtn: {
    flex: 1,
    minWidth: "45%",
    paddingVertical: 12,
    paddingHorizontal: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary,
    alignItems: "center",
  },
  secondaryBtnDisabled: { opacity: 0.5 },
  secondaryBtnText: { color: colors.primary, fontWeight: "600", fontSize: 13 },
  debugText: { marginTop: 10, fontSize: 11, color: colors.textMuted, fontFamily: "monospace" },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.45)",
    justifyContent: "center",
    padding: 16,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
    maxHeight: "90%",
  },
  modalTitle: { fontSize: 18, fontWeight: "700", color: colors.primary, marginBottom: 12 },
  modalLabel: { fontSize: 12, color: colors.textMuted, marginTop: 8, marginBottom: 4 },
  modalInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
    fontSize: 15,
    color: colors.text,
    backgroundColor: colors.background,
  },
  modalActions: { flexDirection: "row", gap: 12, marginTop: 20, justifyContent: "flex-end" },
  modalCancel: { paddingVertical: 12, paddingHorizontal: 16 },
  modalCancelText: { color: colors.textMuted, fontWeight: "600" },
  modalSave: {
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 10,
  },
  modalSaveText: { color: "#fff", fontWeight: "700" },
});
