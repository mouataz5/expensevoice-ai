import { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Image,
  Linking,
  Modal,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, space } from "../../src/theme/tokens";
import {
  ScreenScroll,
  SectionTitle,
  StepIndicator,
  Card,
  InfoBanner,
  ConfidenceBar,
  PrimaryButton,
  SecondaryButton,
  GhostButton,
  FormField,
  TextFieldInput,
  ScanQualityBadge,
  ScanQualityBanner,
  ScanTipsCard,
  RetakeRecommendationCard,
  ScanPreviewFrame,
} from "../../src/components/ui";
import { analyzeScanImageQuality, type ScanQualityResult } from "../../src/lib/scanImageQuality";
import {
  applyInvoiceCorrections,
  getInvoice,
  getInvoicePdfUrl,
  getInvoicePreview,
  retryInvoiceExtraction,
  scanInvoice,
  type InvoicePreview,
} from "../../src/api/invoices";
import { listFarms } from "../../src/api/farms";
import { queryKeys } from "../../src/queryKeys";
import Toast from "react-native-toast-message";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { getStoredToken } from "../../src/lib/secure-store";
import { confirmAsync } from "../../src/lib/confirm";
import { SuccessCelebration } from "../../src/components/ui/SuccessCelebration";

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
  const router = useRouter();
  const queryClient = useQueryClient();
  const [txType, setTxType] = useState<TxType>(null);
  const [farmId, setFarmId] = useState("");
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
  const [showScanSuccess, setShowScanSuccess] = useState(false);
  const [scanQuality, setScanQuality] = useState<ScanQualityResult | null>(null);
  const [qualityAnalyzing, setQualityAnalyzing] = useState(false);
  const [userAcknowledgedPoor, setUserAcknowledgedPoor] = useState(false);
  const { data: farms = [] } = useQuery({
    queryKey: queryKeys.farms,
    queryFn: listFarms,
  });

  useEffect(() => {
    if (!imageUri || ready) {
      if (!imageUri) {
        setScanQuality(null);
        setQualityAnalyzing(false);
        setUserAcknowledgedPoor(false);
      }
      return;
    }
    let cancelled = false;
    setUserAcknowledgedPoor(false);
    setQualityAnalyzing(true);
    setScanQuality(null);
    void analyzeScanImageQuality(imageUri)
      .then((r) => {
        if (cancelled) return;
        setScanQuality(r);
        setQualityAnalyzing(false);
        if (r.level === "fair") {
          Toast.show({
            type: "info",
            text1: t("scanQualityFair"),
            text2: t("scanToastFair"),
          });
        } else if (r.level === "poor") {
          Toast.show({
            type: "info",
            text1: t("scanQualityPoor"),
            text2: t("scanToastPoor"),
          });
        }
      })
      .catch(() => {
        if (cancelled) return;
        setQualityAnalyzing(false);
        setScanQuality({
          level: "fair",
          issues: ["hard_to_read"],
          primaryIssue: "hard_to_read",
          pixelsAnalyzed: false,
        });
      });
    return () => {
      cancelled = true;
    };
  }, [imageUri, ready, t]);

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
        setShowScanSuccess(true);
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
    if (qualityAnalyzing) return;
    if (scanQuality?.level === "poor" && !userAcknowledgedPoor) return;
    setProcessing(true);
    setStatus("processing");
    setPreview(null);
    try {
      const { invoice_id, status: s } = await scanInvoice(imageUri, txType, farmId);
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
    const supplier = editSupplier.trim();
    const invoiceNumber = editInvoiceNumber.trim();
    const invoiceDate = editInvoiceDate.trim();
    const currency = editCurrency.trim().toUpperCase();
    const currentTotalRaw =
      preview?.total_ttc ?? preview?.totals?.ttc ?? (preview?.extraction as { total_amount?: number } | undefined)?.total_amount ?? null;

    if (supplier && (supplier.length < 2 || supplier.length > 255)) {
      Toast.show({ type: "error", text1: t("error"), text2: "Nom fournisseur invalide (2..255 caractères)." });
      return;
    }
    if (invoiceNumber && invoiceNumber.length > 100) {
      Toast.show({ type: "error", text1: t("error"), text2: "Numéro de facture trop long." });
      return;
    }
    if (invoiceDate && !/^\d{4}-\d{2}-\d{2}$/.test(invoiceDate)) {
      Toast.show({ type: "error", text1: t("error"), text2: "Date invalide. Format attendu: YYYY-MM-DD." });
      return;
    }
    if (currency && !["TND", "EUR", "USD", "MAD", "DZD", "SAR"].includes(currency)) {
      Toast.show({ type: "error", text1: t("error"), text2: "Devise invalide (TND, EUR, USD, MAD, DZD, SAR)." });
      return;
    }

    const patch: Record<string, unknown> = {};
    if (supplier) patch.supplier_name = supplier;
    if (invoiceNumber) patch.invoice_number = invoiceNumber;
    if (invoiceDate) patch.invoice_date = invoiceDate;
    if (currency) patch.currency = currency;
    const parsed = parseFloat(String(editTotal).replace(",", "."));
    if (editTotal.trim() && !Number.isNaN(parsed)) {
      if (parsed < 0) {
        Toast.show({ type: "error", text1: t("error"), text2: "Le total ne peut pas être négatif." });
        return;
      }
      if (currentTotalRaw != null && Number(currentTotalRaw) > 0) {
        const ratio = Math.abs(parsed - Number(currentTotalRaw)) / Number(currentTotalRaw);
        if (ratio > 0.5) {
          Toast.show({
            type: "error",
            text1: t("error"),
            text2: "Écart trop grand (>50%). Vérifiez les lignes ou relancez l'extraction.",
          });
          return;
        }
      }
      patch.total_amount = parsed;
    }
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
    void (async () => {
      const hasWork = Boolean(imageUri || invoiceId || ready);
      if (hasWork) {
        const ok = await confirmAsync(t("confirmResetScanTitle"), t("confirmResetScanMessage"), {
          confirmLabel: t("confirmResetScanConfirm"),
          cancelLabel: t("cancel"),
          destructive: true,
        });
        if (!ok) return;
      }
      setImageUri(null);
      setInvoiceId(null);
      setStatus("");
      setReady(false);
      setPreview(null);
      setShowScanSuccess(false);
      setScanQuality(null);
      setUserAcknowledgedPoor(false);
      setQualityAnalyzing(false);
    })();
  };

  const clearScanImage = () => {
    setImageUri(null);
    setScanQuality(null);
    setUserAcknowledgedPoor(false);
    setQualityAnalyzing(false);
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
    <>
      <SuccessCelebration
        visible={showScanSuccess}
        title={t("scanSuccessTitle")}
        subtitle={t("scanSuccessScreenSubtitle")}
        primaryLabel={t("scanSuccessContinueReview")}
        onPrimary={() => setShowScanSuccess(false)}
        secondaryLabel={t("scanSuccessViewInvoices")}
        onSecondary={() => {
          setShowScanSuccess(false);
          router.push("/(tabs)/invoices");
        }}
      />
      <Modal visible={editOpen} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>{t("manualEdit")}</Text>
            <FormField label={t("supplierLabel")}>
              <TextFieldInput value={editSupplier} onChangeText={setEditSupplier} placeholder="supplier_name" />
            </FormField>
            <FormField label={t("invoiceNumber")}>
              <TextFieldInput value={editInvoiceNumber} onChangeText={setEditInvoiceNumber} />
            </FormField>
            <FormField label={`${t("invoiceDate")} (YYYY-MM-DD)`}>
              <TextFieldInput value={editInvoiceDate} onChangeText={setEditInvoiceDate} placeholder="2026-01-16" />
            </FormField>
            <FormField label={t("totalAmount")}>
              <TextFieldInput value={editTotal} onChangeText={setEditTotal} keyboardType="decimal-pad" />
            </FormField>
            <FormField label={t("settingsCurrency")}>
              <TextFieldInput value={editCurrency} onChangeText={setEditCurrency} />
            </FormField>
            <View style={styles.modalActions}>
              <GhostButton title={t("cancel")} onPress={() => setEditOpen(false)} />
              <PrimaryButton title={t("saveCorrections")} onPress={() => void saveManualCorrections()} />
            </View>
          </View>
        </View>
      </Modal>
      <ScreenScroll contentStyle={styles.content}>
        <SectionTitle title={t("scanInvoice")} subtitle={t("scanWorkflowHint")} />
        <StepIndicator steps={scanStepLabels} activeIndex={scanStepActiveIndex} />

        <Text style={styles.label}>{t("selectType")}</Text>
        <Text style={styles.label}>Ferme</Text>
        <View style={styles.farmWrap}>
          {farms.map((f) => (
            <TouchableOpacity
              key={f.id}
              style={[styles.farmChip, farmId === f.id && styles.farmChipOn]}
              onPress={() => setFarmId(f.id)}
            >
              <Text style={[styles.farmChipText, farmId === f.id && styles.farmChipTextOn]}>{f.name}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <View style={styles.segWrap}>
          <TouchableOpacity
            style={[styles.segSide, txType === "buy" && styles.segSideOn]}
            onPress={() => setTxType("buy")}
            accessibilityLabel={t("buy")}
            accessibilityRole="button"
            accessibilityState={{ selected: txType === "buy" }}
          >
            <Text style={[styles.segTxt, txType === "buy" && styles.segTxtOn]}>{t("buy")}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.segSide, txType === "sell" && styles.segSideOn]}
            onPress={() => setTxType("sell")}
            accessibilityLabel={t("sell")}
            accessibilityRole="button"
            accessibilityState={{ selected: txType === "sell" }}
          >
            <Text style={[styles.segTxt, txType === "sell" && styles.segTxtOn]}>{t("sell")}</Text>
          </TouchableOpacity>
        </View>

        {!imageUri ? (
          <View style={styles.uploadRow}>
            <View style={styles.uploadHalf}>
              <SecondaryButton
                title={t("pickImage")}
                onPress={() => void pickImage()}
                disabled={!txType || !farmId || processing}
                icon="images-outline"
              />
            </View>
            <View style={styles.uploadHalf}>
              <SecondaryButton
                title={t("takePhoto")}
                onPress={() => void takePhoto()}
                disabled={!txType || !farmId || processing}
                icon="camera-outline"
              />
            </View>
          </View>
        ) : (
        <>
          <View style={styles.previewHeaderRow}>
            <Text style={styles.previewLabel}>{t("scanPreviewLabel")}</Text>
            <ScanQualityBadge
              level={scanQuality?.level ?? null}
              analyzing={qualityAnalyzing}
              t={t}
            />
          </View>
          <Card style={styles.previewCard}>
            <ScanPreviewFrame>
              <Image source={{ uri: imageUri }} style={styles.preview} resizeMode="contain" />
            </ScanPreviewFrame>
          </Card>
          {!ready ? (
            <>
              {scanQuality && !qualityAnalyzing ? (
                <ScanQualityBanner
                  level={scanQuality.level}
                  primaryIssue={scanQuality.primaryIssue}
                  t={t}
                />
              ) : null}
              {scanQuality?.level === "poor" && !userAcknowledgedPoor && !qualityAnalyzing ? (
                <RetakeRecommendationCard
                  t={t}
                  onRetake={clearScanImage}
                  onContinueAnyway={() => setUserAcknowledgedPoor(true)}
                />
              ) : null}
              <ScanTipsCard t={t} />
              <PrimaryButton
                title={processing ? t("processing") : t("uploadInvoice")}
                onPress={() => void uploadAndPoll()}
                loading={processing}
                disabled={
                  processing ||
                  !farmId ||
                  qualityAnalyzing ||
                  (scanQuality?.level === "poor" && !userAcknowledgedPoor)
                }
                icon="cloud-upload-outline"
              />
              {scanQuality &&
              !qualityAnalyzing &&
              (scanQuality.level !== "poor" || userAcknowledgedPoor) ? (
                <View style={styles.retakeRow}>
                  <SecondaryButton
                    title={t("scanRetakePhoto")}
                    onPress={clearScanImage}
                    disabled={processing}
                    icon="camera-outline"
                  />
                </View>
              ) : null}
              {processing ? (
                <Text style={styles.statusText}>
                  {t("processing")} — {status}
                </Text>
              ) : null}
            </>
          ) : (
            <>
              <View style={styles.successBannerWrap}>
                <InfoBanner variant="success" title={t("scanSuccessTitle")}>
                  {t("scanSuccessBody")}
                </InfoBanner>
              </View>
              {preview && (
                <Card style={styles.reviewCard}>
                  <Text style={styles.reviewTitle}>{t("readyForReview")}</Text>
                  {((preview.ocr_text?.length ?? 0) < MIN_OCR_CHARS_WARN ||
                    !!(preview.extraction_error && String(preview.extraction_error).trim())) && (
                    <InfoBanner variant="warning" title={t("warningsTitle")}>
                      {(preview.ocr_text?.length ?? 0) < MIN_OCR_CHARS_WARN
                        ? t("scanOcrWeak")
                        : `${t("scanExtractionWarning")}: ${preview.extraction_error}`}
                    </InfoBanner>
                  )}
                  {(preview.global_confidence ?? preview.confidence) > 0 ? (
                    <View style={styles.confBlock}>
                      <Text style={styles.confLabel}>{t("confidence")}</Text>
                      <ConfidenceBar value={preview.global_confidence ?? preview.confidence ?? 0} />
                    </View>
                  ) : null}
                  {(["supplier_name", "invoice_number", "invoice_date", "total_amount"] as const).map((k) => {
                    const v = preview.field_confidence?.[k];
                    if (v == null || v <= 0) return null;
                    return (
                      <Text key={k} style={styles.confidenceText}>
                        {k}: {Math.round(v * 100)}%
                      </Text>
                    );
                  })}
                  {preview.warnings && preview.warnings.length > 0
                    ? preview.warnings.map((w, i) => (
                        <InfoBanner key={`w-${i}`} variant="warning" title={t("warningsTitle")}>
                          {w}
                        </InfoBanner>
                      ))
                    : null}
                  {preview.missing_fields && preview.missing_fields.length > 0 ? (
                    <InfoBanner variant="error" title={t("missingFieldsTitle")}>
                      {preview.missing_fields.join(", ")}
                    </InfoBanner>
                  ) : null}
                  <Text style={styles.sectionLabel}>{t("supplierLabel")}</Text>
                  {preview.supplier_name ? (
                    <Text style={styles.reviewRow}>{preview.supplier_name}</Text>
                  ) : (
                    <Text style={styles.reviewMuted}>—</Text>
                  )}
                  {preview.invoice_number ? (
                    <Text style={styles.reviewRow}>
                      <Text style={styles.reviewLabel}>{t("invoiceNumber")}: </Text>
                      {preview.invoice_number}
                    </Text>
                  ) : null}
                  {preview.invoice_date ? (
                    <Text style={styles.reviewRow}>
                      <Text style={styles.reviewLabel}>{t("invoiceDate")}: </Text>
                      {preview.invoice_date}
                    </Text>
                  ) : null}
                  <Text style={styles.sectionLabel}>{t("invoiceLines")}</Text>
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
                  <Text style={styles.sectionLabel}>{t("totalAmount")}</Text>
                  <Text style={styles.totalRow}>
                    <Text style={styles.reviewLabel}>{t("netToPay")}: </Text>
                    {fmtTnAmount(
                      preview.total_ttc ?? preview.totals?.ttc ?? null,
                    )}{" "}
                    {preview.currency}
                  </Text>
                  <View style={styles.actionRow}>
                    <View style={styles.actionHalf}>
                      <SecondaryButton title={t("manualEdit")} onPress={openManualEdit} icon="create-outline" />
                    </View>
                    <View style={styles.actionHalf}>
                      <SecondaryButton
                        title={t("retryExtraction")}
                        onPress={() => void onRetryExtraction()}
                        disabled={processing}
                        icon="refresh-outline"
                      />
                    </View>
                  </View>
                  {typeof __DEV__ !== "undefined" && __DEV__ && preview.normalized_text ? (
                    <Text style={styles.debugText} numberOfLines={10}>
                      {t("debugNormalizedOcr")}: {preview.normalized_text.slice(0, 800)}
                    </Text>
                  ) : null}
                </Card>
              )}
              <PrimaryButton title={t("downloadPdf")} onPress={() => void downloadPdf()} icon="document-attach-outline" />
              <GhostButton title={t("newInvoice")} onPress={reset} />
            </>
          )}
        </>
      )}
      </ScreenScroll>
    </>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: space.xxxl },
  successBannerWrap: { marginBottom: space.md },
  label: { fontSize: font.sm, color: colors.textSecondary, marginBottom: space.sm, marginTop: space.md, fontWeight: font.semibold },
  farmWrap: { flexDirection: "row", flexWrap: "wrap", gap: space.xs, marginBottom: space.md },
  farmChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.full,
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
    backgroundColor: colors.surface,
  },
  farmChipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  farmChipText: { color: colors.textSecondary, fontSize: font.sm, fontWeight: font.semibold },
  farmChipTextOn: { color: "#fff" },
  segWrap: {
    flexDirection: "row",
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    padding: 4,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: space.lg,
  },
  segSide: {
    flex: 1,
    paddingVertical: space.sm + 2,
    alignItems: "center",
    borderRadius: radius.sm,
  },
  segSideOn: { backgroundColor: colors.primary },
  segTxt: { fontSize: font.md, fontWeight: font.semibold, color: colors.textSecondary },
  segTxtOn: { color: "#fff", fontWeight: font.bold },
  uploadRow: { flexDirection: "row", gap: space.sm, marginBottom: space.md },
  uploadHalf: { flex: 1, minWidth: "45%" },
  previewHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space.sm,
    marginBottom: space.sm,
    flexWrap: "wrap",
  },
  previewLabel: { fontSize: font.md, fontWeight: font.bold, color: colors.primaryDark },
  previewCard: { padding: space.sm, marginBottom: space.md, overflow: "hidden" },
  preview: { width: "100%", height: 280, backgroundColor: colors.surfaceMuted },
  retakeRow: { marginTop: space.sm, marginBottom: space.xs },
  statusText: { color: colors.textMuted, fontSize: font.sm, marginTop: space.sm, textAlign: "center" },
  reviewCard: { marginBottom: space.md },
  reviewTitle: { fontSize: font.xl, fontWeight: font.bold, color: colors.primaryDark, marginBottom: space.md },
  confBlock: { marginBottom: space.sm },
  confLabel: { fontSize: font.sm, fontWeight: font.bold, color: colors.textSecondary, marginBottom: space.xs },
  confidenceText: { fontSize: font.sm, color: colors.textMuted, marginBottom: space.xs },
  sectionLabel: {
    fontSize: font.sm,
    fontWeight: font.bold,
    color: colors.primary,
    marginTop: space.md,
    marginBottom: space.xs,
  },
  reviewMuted: { fontSize: font.sm, color: colors.textMuted, marginBottom: space.xs },
  reviewLabel: { fontWeight: font.bold, color: colors.textMuted },
  reviewRow: { fontSize: font.sm, color: colors.text, marginBottom: space.xs },
  itemsBlock: { marginTop: space.sm, marginBottom: space.sm },
  itemRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: space.sm,
    paddingVertical: space.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  itemDesignation: { flex: 1, fontSize: font.sm, color: colors.text, minWidth: "100%" },
  itemQty: { fontSize: font.xs, color: colors.textMuted, marginRight: space.sm },
  itemPrice: { fontSize: font.xs, color: colors.textMuted, marginRight: space.sm },
  itemTotal: { fontSize: font.xs, fontWeight: font.bold, color: colors.text },
  totalRow: { fontSize: font.lg, fontWeight: font.bold, color: colors.primary, marginTop: space.sm },
  actionRow: { flexDirection: "row", gap: space.sm, marginTop: space.lg, flexWrap: "wrap" },
  actionHalf: { flex: 1, minWidth: "45%" },
  debugText: { marginTop: space.md, fontSize: font.xs, color: colors.textSubtle, fontFamily: "monospace" },
  modalBackdrop: {
    flex: 1,
    backgroundColor: colors.overlay,
    justifyContent: "center",
    padding: space.md,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: 1,
    borderColor: colors.border,
    maxHeight: "92%",
  },
  modalTitle: { fontSize: font.xl, fontWeight: font.bold, color: colors.primaryDark, marginBottom: space.md },
  modalActions: {
    flexDirection: "row",
    gap: space.md,
    marginTop: space.lg,
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
  },
});
