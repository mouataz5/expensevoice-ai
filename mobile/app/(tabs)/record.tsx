import { useMemo, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
} from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, space } from "../../src/theme/tokens";
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
import {
  StepIndicator,
  Card,
  SectionTitle,
  PrimaryButton,
  GhostButton,
  FormField,
  TextFieldInput,
  InfoBanner,
} from "../../src/components/ui";
import { confirmAsync } from "../../src/lib/confirm";

type TxType = "buy" | "sell" | null;

export default function RecordScreen() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [txType, setTxType] = useState<TxType>(null);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
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
      setReview(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.purchasesMe });
      await queryClient.invalidateQueries({ queryKey: queryKeys.alertsMe });
      router.replace({ pathname: "/success", params: { flow: "purchase" } });
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
    <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <SectionTitle title={t("record")} subtitle={t("scanWorkflowHint")} />
      <StepIndicator steps={stepLabels} activeIndex={stepActiveIndex} />

      <Text style={styles.label}>{t("selectType")}</Text>
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

      {!review ? (
        <>
          {!isRecording ? (
            <PrimaryButton
              title={uploading || polling ? (polling ? t("processing") : t("uploadRecord")) : t("record")}
              onPress={startRecording}
              loading={false}
              disabled={!txType || uploading || polling}
              icon="mic-outline"
            />
          ) : (
            <TouchableOpacity style={styles.stopBtn} onPress={stopAndUpload} disabled={uploading} accessibilityRole="button">
              {uploading ? <ActivityIndicator color="#fff" /> : <Text style={styles.stopBtnText}>{t("stopRecord")}</Text>}
            </TouchableOpacity>
          )}
          {(uploading || polling) && (
            <View style={styles.loading}>
              <ActivityIndicator size="small" color={colors.primary} />
              <Text style={styles.loadingText}>{t("processing")}</Text>
            </View>
          )}
          {txType === null ? (
            <InfoBanner variant="info" title={t("selectType")}>
              {t("scanWorkflowHint")}
            </InfoBanner>
          ) : null}
        </>
      ) : (
        <Card style={styles.reviewCard}>
          <Text style={styles.cardTitle}>{t("readyForReview")}</Text>
          {!!review.transcription?.trim() && (
            <View style={styles.transcriptionBox}>
              <Text style={styles.transcriptionLabel}>{t("transcriptionLabel")}</Text>
              <Text style={styles.transcriptionText}>{review.transcription}</Text>
            </View>
          )}
          <FormField label={t("productName")}>
            <TextFieldInput
              value={form.product_name}
              onChangeText={(v) => setForm((f) => ({ ...f, product_name: v }))}
            />
          </FormField>
          <FormField label={t("category")}>
            <TextFieldInput value={form.category} onChangeText={(v) => setForm((f) => ({ ...f, category: v }))} />
          </FormField>
          <FormField label={t("quantity")}>
            <TextFieldInput
              value={form.quantity}
              onChangeText={(v) => setForm((f) => ({ ...f, quantity: v }))}
              keyboardType="numeric"
            />
          </FormField>
          <FormField label={t("unitPrice")}>
            <TextFieldInput
              value={form.unit_price}
              onChangeText={(v) => setForm((f) => ({ ...f, unit_price: v }))}
              keyboardType="decimal-pad"
            />
          </FormField>
          <FormField label={t("totalAmount")}>
            <TextFieldInput
              value={form.total_amount}
              onChangeText={(v) => setForm((f) => ({ ...f, total_amount: v }))}
              keyboardType="decimal-pad"
            />
          </FormField>
          <PrimaryButton title={t("confirm")} onPress={() => void handleConfirm()} icon="checkmark-circle-outline" />
          <GhostButton
            title={t("retry")}
            onPress={() => {
              void confirmAsync(t("confirmDiscardVoiceTitle"), t("confirmDiscardVoiceMessage"), {
                confirmLabel: t("confirmDiscardVoiceConfirm"),
                cancelLabel: t("cancel"),
                destructive: true,
              }).then((ok) => {
                if (ok) setReview(null);
              });
            }}
          />
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, paddingBottom: space.xxxl },
  label: { fontSize: font.sm, color: colors.textSecondary, marginBottom: space.sm, fontWeight: font.semibold },
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
  stopBtn: {
    backgroundColor: colors.error,
    padding: space.lg,
    borderRadius: radius.md,
    alignItems: "center",
    marginBottom: space.md,
    minHeight: 52,
    justifyContent: "center",
  },
  stopBtnText: { color: "#fff", fontSize: font.md, fontWeight: font.bold },
  loading: { flexDirection: "row", alignItems: "center", gap: space.sm, marginTop: space.sm, marginBottom: space.md },
  loadingText: { color: colors.textMuted, fontSize: font.sm },
  reviewCard: { marginTop: space.md },
  cardTitle: { fontSize: font.xl, fontWeight: font.bold, color: colors.primaryDark, marginBottom: space.md },
  transcriptionBox: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    padding: space.md,
    marginBottom: space.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  transcriptionLabel: { fontSize: font.xs, fontWeight: font.bold, color: colors.textMuted, marginBottom: space.xs },
  transcriptionText: { fontSize: font.sm, color: colors.text, lineHeight: 22 },
});
