import { useMemo, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  TextInput,
  ScrollView,
} from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import {
  uploadVoice,
  getPurchase,
  confirmPurchase,
  isVoicePipelineReady,
  sttLanguageFromLocale,
  type PurchaseOut,
} from "../../src/api/purchases";
import { queryKeys } from "../../src/queryKeys";
import Toast from "react-native-toast-message";
import {
  useAudioRecorder,
  useAudioRecorderState,
  RecordingPresets,
  AudioModule,
  setAudioModeAsync,
} from "expo-audio";

type TxType = "buy" | "sell" | null;

export default function RecordScreen() {
  const { t, locale } = useLocale();
  const queryClient = useQueryClient();
  const [txType, setTxType] = useState<TxType>(null);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  /** `recorder.isRecording` alone does not re-render; expo-audio expects this hook for UI. */
  const recorderState = useAudioRecorderState(recorder, 250);
  const isRecording = recorderState.isRecording;
  const [uploading, setUploading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [review, setReview] = useState<PurchaseOut | null>(null);
  const [form, setForm] = useState({ product_name: "", category: "", quantity: "1", unit_price: "0", total_amount: "0" });

  const startRecording = async () => {
    try {
      const status = await AudioModule.requestRecordingPermissionsAsync();
      if (!status.granted) {
        Toast.show({
          type: "error",
          text1: t("error"),
          text2: "Microphone permission denied — enable it in Settings",
        });
        return;
      }
      // iOS: session must allow recording (otherwise native layer rejects / no audio).
      await setAudioModeAsync({
        allowsRecording: true,
        playsInSilentMode: true,
        interruptionMode: "doNotMix",
      });
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch (e) {
      Toast.show({
        type: "error",
        text1: t("error"),
        text2: e instanceof Error ? e.message : "Could not start recording",
      });
      try {
        await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      } catch {
        /* ignore */
      }
    }
  };

  const stopAndUpload = async () => {
    if (!recorder.getStatus().isRecording || txType === null) return;
    setUploading(true);
    try {
      await recorder.stop();
      const uri = recorder.uri ?? recorder.getStatus().url;
      if (!uri) throw new Error("No recording URI");
      const res = await uploadVoice(uri, txType, { language: sttLanguageFromLocale(locale) });
      setPolling(true);
      let lastPurchase: PurchaseOut | null = null;
      let ready = false;
      const pollMs = 2000;
      const maxPolls = 90;
      for (let i = 0; i < maxPolls; i++) {
        await new Promise((r) => setTimeout(r, pollMs));
        lastPurchase = await getPurchase(res.purchase_id);
        if (lastPurchase && isVoicePipelineReady(lastPurchase)) {
          setReview(lastPurchase);
          setForm({
            product_name: lastPurchase.product_name || "",
            category: lastPurchase.category || "",
            quantity: String(lastPurchase.quantity || 1),
            unit_price: String(lastPurchase.unit_price ?? 0),
            total_amount: String(lastPurchase.total_amount ?? 0),
          });
          ready = true;
          break;
        }
      }
      if (!ready && lastPurchase) {
        if (lastPurchase.processing_status === "processing") {
          Toast.show({
            type: "error",
            text1: t("error"),
            text2: t("voiceProcessingTimeout"),
          });
          setReview(null);
        } else {
          setReview(lastPurchase);
          setForm({
            product_name: lastPurchase.product_name || "",
            category: lastPurchase.category || "",
            quantity: String(lastPurchase.quantity || 1),
            unit_price: String(lastPurchase.unit_price ?? 0),
            total_amount: String(lastPurchase.total_amount ?? 0),
          });
        }
      }
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    } finally {
      setUploading(false);
      setPolling(false);
      try {
        await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      } catch {
        /* ignore */
      }
    }
  };

  const handleConfirm = async () => {
    if (!review) return;
    const qty = parseInt(form.quantity, 10) || 1;
    const up = parseFloat(String(form.unit_price).replace(",", ".")) || 0;
    const totalParsed = parseFloat(String(form.total_amount).replace(",", "."));
    const total =
      Number.isFinite(totalParsed) && totalParsed >= 0 ? totalParsed : qty * up;
    try {
      await confirmPurchase(review.id, {
        product_name: form.product_name || "—",
        category: form.category || null,
        quantity: qty,
        unit_price: up,
        total_amount: total,
      });
      Toast.show({ type: "success", text1: t("confirm") });
      setReview(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.purchasesMe });
      await queryClient.invalidateQueries({ queryKey: queryKeys.alertsMe });
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    }
  };

  const stepActiveIndex = useMemo(() => {
    if (review) return 3;
    if (uploading || polling) return 2;
    if (isRecording) return 1;
    if (txType) return 1;
    return 0;
  }, [review, uploading, polling, isRecording, txType]);

  const stepLabels = [t("stepChooseType"), t("stepRecord"), t("stepProcess"), t("readyForReview")];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.stepsRow}>
        {stepLabels.map((label, i) => (
          <View
            key={`step-${i}`}
            style={[styles.stepPill, i <= stepActiveIndex && styles.stepPillActive]}
          >
            <Text
              style={[styles.stepPillText, i <= stepActiveIndex && styles.stepPillTextActive]}
              numberOfLines={2}
            >
              {label}
            </Text>
          </View>
        ))}
      </View>

      <Text style={styles.label}>{t("selectType")}</Text>
      <View style={styles.row}>
        <TouchableOpacity
          style={[styles.txBtn, txType === "buy" && styles.txBtnActive]}
          onPress={() => setTxType("buy")}
          accessibilityLabel={t("buy")}
          accessibilityRole="button"
        >
          <Text style={[styles.txBtnText, txType === "buy" && styles.txBtnTextActive]} pointerEvents="none">{t("buy")}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.txBtn, txType === "sell" && styles.txBtnActive]}
          onPress={() => setTxType("sell")}
          accessibilityLabel={t("sell")}
          accessibilityRole="button"
        >
          <Text style={[styles.txBtnText, txType === "sell" && styles.txBtnTextActive]} pointerEvents="none">{t("sell")}</Text>
        </TouchableOpacity>
      </View>

      {!review ? (
        <>
          {!isRecording ? (
            <TouchableOpacity
              style={[styles.recordBtn, (!txType || uploading || polling) && styles.recordBtnDisabled]}
              onPress={startRecording}
              disabled={!txType || uploading || polling}
              accessibilityLabel={uploading || polling ? (polling ? t("processing") : t("uploadRecord")) : t("record")}
              accessibilityRole="button"
            >
              <Text style={styles.recordBtnText} pointerEvents="none">{uploading || polling ? (polling ? t("processing") : t("uploadRecord")) : t("record")}</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity style={styles.stopBtn} onPress={stopAndUpload} disabled={uploading} accessibilityLabel={t("stopRecord")} accessibilityRole="button">
              {uploading ? <ActivityIndicator color="#fff" /> : <Text style={styles.stopBtnText} pointerEvents="none">{t("stopRecord")}</Text>}
            </TouchableOpacity>
          )}
          {(uploading || polling) && (
            <View style={styles.loading}>
              <ActivityIndicator size="small" color={colors.primary} />
              <Text style={styles.loadingText}>{t("processing")}</Text>
            </View>
          )}
        </>
      ) : (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t("readyForReview")}</Text>
          {!!review.transcription?.trim() && (
            <View style={styles.transcriptionBox}>
              <Text style={styles.transcriptionLabel}>{t("transcriptionLabel")}</Text>
              <Text style={styles.transcriptionText}>{review.transcription}</Text>
            </View>
          )}
          <TextInput style={styles.input} placeholder={t("productName")} value={form.product_name} onChangeText={(v) => setForm((f) => ({ ...f, product_name: v }))} placeholderTextColor={colors.textMuted} />
          <TextInput style={styles.input} placeholder={t("category")} value={form.category} onChangeText={(v) => setForm((f) => ({ ...f, category: v }))} placeholderTextColor={colors.textMuted} />
          <TextInput style={styles.input} placeholder={t("quantity")} value={form.quantity} onChangeText={(v) => setForm((f) => ({ ...f, quantity: v }))} keyboardType="numeric" placeholderTextColor={colors.textMuted} />
          <TextInput style={styles.input} placeholder={t("unitPrice")} value={form.unit_price} onChangeText={(v) => setForm((f) => ({ ...f, unit_price: v }))} keyboardType="decimal-pad" placeholderTextColor={colors.textMuted} />
          <TextInput style={styles.input} placeholder={t("totalAmount")} value={form.total_amount} onChangeText={(v) => setForm((f) => ({ ...f, total_amount: v }))} keyboardType="decimal-pad" placeholderTextColor={colors.textMuted} />
          <TouchableOpacity style={styles.confirmBtn} onPress={handleConfirm}>
            <Text style={styles.confirmBtnText}>{t("confirm")}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.cancelBtn} onPress={() => setReview(null)}>
            <Text style={styles.cancelBtnText}>{t("retry")}</Text>
          </TouchableOpacity>
        </View>
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
  recordBtn: { backgroundColor: colors.accent, padding: 20, borderRadius: 12, alignItems: "center", marginBottom: 12 },
  recordBtnDisabled: { opacity: 0.6 },
  recordBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  stopBtn: { backgroundColor: colors.error, padding: 20, borderRadius: 12, alignItems: "center", marginBottom: 12 },
  stopBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  loading: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 8 },
  loadingText: { color: colors.textMuted, fontSize: 14 },
  card: { backgroundColor: colors.surface, borderRadius: 20, padding: 20, marginTop: 16 },
  cardTitle: { fontSize: 18, fontWeight: "600", color: colors.primary, marginBottom: 16 },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 14, marginBottom: 12, fontSize: 16, color: colors.text },
  confirmBtn: { backgroundColor: colors.primary, padding: 16, borderRadius: 12, alignItems: "center", marginTop: 8 },
  confirmBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelBtn: { marginTop: 12, alignItems: "center" },
  cancelBtnText: { color: colors.primary, fontSize: 14 },
  transcriptionBox: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 12,
    padding: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  transcriptionLabel: { fontSize: 12, fontWeight: "600", color: colors.textMuted, marginBottom: 6 },
  transcriptionText: { fontSize: 14, color: colors.text, lineHeight: 20 },
});
