import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  Animated,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
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
  PrimaryButton,
  GhostButton,
  FormField,
  TextFieldInput,
} from "../../src/components/ui";
import { confirmAsync } from "../../src/lib/confirm";

type TxType = "buy" | "sell";

const SILENCE_THRESHOLD_DB = -38;
const SILENCE_AUTO_STOP_MS = 3000;
const MIN_RECORD_MS = 1500;
const NUM_BARS = 24;

const RECORDING_OPTS = {
  ...RecordingPresets.HIGH_QUALITY,
  isMeteringEnabled: true,
};

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

function dbToLevel(db: number | undefined): number {
  if (db == null || db <= -60) return 0;
  if (db >= 0) return 1;
  return (db + 60) / 60;
}

function WaveformVisualizer({ metering, isActive }: { metering: number | undefined; isActive: boolean }) {
  const barsRef = useRef<Animated.Value[]>(
    Array.from({ length: NUM_BARS }, () => new Animated.Value(0.08))
  );
  const historyRef = useRef<number[]>(Array(NUM_BARS).fill(0.08));

  useEffect(() => {
    if (!isActive) {
      historyRef.current = Array(NUM_BARS).fill(0.08);
      barsRef.current.forEach((b) => {
        Animated.timing(b, { toValue: 0.08, duration: 200, useNativeDriver: false }).start();
      });
      return;
    }
    const level = dbToLevel(metering);
    historyRef.current.push(level);
    if (historyRef.current.length > NUM_BARS) historyRef.current.shift();

    historyRef.current.forEach((val, i) => {
      const target = Math.max(0.08, val);
      Animated.timing(barsRef.current[i], {
        toValue: target,
        duration: 120,
        useNativeDriver: false,
      }).start();
    });
  }, [metering, isActive]);

  return (
    <View style={waveStyles.container}>
      {barsRef.current.map((anim, i) => (
        <Animated.View
          key={i}
          style={[
            waveStyles.bar,
            {
              height: anim.interpolate({
                inputRange: [0, 1],
                outputRange: [4, 56],
              }),
              backgroundColor: isActive ? colors.primary : colors.border,
            },
          ]}
        />
      ))}
    </View>
  );
}

const waveStyles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    height: 60,
    gap: 2,
    marginVertical: space.sm,
  },
  bar: {
    width: 4,
    borderRadius: 2,
    minHeight: 4,
  },
});

function VoiceStatusIndicator({ metering, silenceCountdown }: { metering: number | undefined; silenceCountdown: number }) {
  const level = dbToLevel(metering);
  const isSpeaking = level > 0.15;
  const secondsLeft = Math.ceil(silenceCountdown / 1000);

  return (
    <View style={statusStyles.row}>
      <View style={[statusStyles.dot, { backgroundColor: isSpeaking ? colors.success : colors.textMuted }]} />
      <Text style={[statusStyles.text, { color: isSpeaking ? colors.success : colors.textMuted }]}>
        {isSpeaking ? "🎙️ Voix détectée" : `⏸️ Silence${secondsLeft < 3 ? ` (${secondsLeft}s)` : ""}`}
      </Text>
    </View>
  );
}

const statusStyles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, marginTop: 4 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  text: { fontSize: font.sm, fontWeight: font.semibold },
});


export default function RecordScreen() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [txType, setTxType] = useState<TxType>("buy");
  const recorder = useAudioRecorder(RECORDING_OPTS);
  const recorderState = useAudioRecorderState(recorder, 150);
  const isRecording = recorderState.isRecording;
  const metering = recorderState.metering;
  const durationMs = recorderState.durationMs ?? 0;

  const [uploading, setUploading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [review, setReview] = useState<PurchaseOut | null>(null);
  const [form, setForm] = useState({
    product_name: "",
    category: "",
    quantity: "1",
    unit_price: "0",
    total_amount: "0",
  });

  const silenceStartRef = useRef<number | null>(null);
  const [silenceCountdown, setSilenceCountdown] = useState(SILENCE_AUTO_STOP_MS);
  const stopTriggeredRef = useRef(false);

  useEffect(() => {
    if (!isRecording) {
      silenceStartRef.current = null;
      setSilenceCountdown(SILENCE_AUTO_STOP_MS);
      stopTriggeredRef.current = false;
      return;
    }
    if (durationMs < MIN_RECORD_MS) {
      silenceStartRef.current = null;
      setSilenceCountdown(SILENCE_AUTO_STOP_MS);
      return;
    }

    const level = dbToLevel(metering);
    const isSilent = level < 0.12;

    if (isSilent) {
      if (silenceStartRef.current == null) {
        silenceStartRef.current = Date.now();
      }
      const elapsed = Date.now() - silenceStartRef.current;
      const remaining = Math.max(0, SILENCE_AUTO_STOP_MS - elapsed);
      setSilenceCountdown(remaining);

      if (remaining <= 0 && !stopTriggeredRef.current) {
        stopTriggeredRef.current = true;
        void doStopAndUpload();
      }
    } else {
      silenceStartRef.current = null;
      setSilenceCountdown(SILENCE_AUTO_STOP_MS);
    }
  }, [metering, isRecording, durationMs]);

  const startRecording = useCallback(async () => {
    stopTriggeredRef.current = false;
    try {
      const status = await AudioModule.requestRecordingPermissionsAsync();
      if (!status.granted) {
        Toast.show({ type: "error", text1: t("error"), text2: t("micDenied") });
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
      } catch { /* ignore */ }
    }
  }, [recorder, t]);

  const doStopAndUpload = useCallback(async () => {
    if (!recorder.getStatus().isRecording) return;
    setUploading(true);
    try {
      await recorder.stop();
      const uri = recorder.uri ?? recorder.getStatus().url;
      if (!uri) throw new Error("No recording URI");
      const res = await uploadVoice(uri, txType, {
        language: sttLanguageFromLocale(locale),
      });
      setPolling(true);
      let lastPurchase: PurchaseOut | null = null;
      let ready = false;
      for (let i = 0; i < 90; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        lastPurchase = await getPurchase(res.purchase_id);
        if (lastPurchase && isVoicePipelineReady(lastPurchase)) {
          ready = true;
          break;
        }
      }
      if (lastPurchase) {
        if (!ready && lastPurchase.processing_status === "processing") {
          Toast.show({ type: "error", text1: t("error"), text2: t("voiceProcessingTimeout") });
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
      } catch { /* ignore */ }
    }
  }, [recorder, txType, locale, t]);

  const handleConfirm = useCallback(async () => {
    if (!review) return;
    const qty = parseInt(form.quantity, 10) || 1;
    const up = parseFloat(String(form.unit_price).replace(",", ".")) || 0;
    const totalParsed = parseFloat(String(form.total_amount).replace(",", "."));
    const total = Number.isFinite(totalParsed) && totalParsed >= 0 ? totalParsed : qty * up;
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
  }, [review, form, queryClient, router, t]);

  const resetFlow = useCallback(() => {
    void confirmAsync(
      t("confirmDiscardVoiceTitle"),
      t("confirmDiscardVoiceMessage"),
      { confirmLabel: t("confirmDiscardVoiceConfirm"), cancelLabel: t("cancel"), destructive: true }
    ).then((ok) => { if (ok) setReview(null); });
  }, [t]);

  const stepActiveIndex = useMemo(() => {
    if (review) return 3;
    if (uploading || polling) return 2;
    if (isRecording) return 1;
    return 0;
  }, [review, uploading, polling, isRecording]);

  const stepLabels = [t("stepChooseType"), t("stepRecord"), t("stepProcess"), t("readyForReview")];
  const isBusy = uploading || polling;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <StepIndicator steps={stepLabels} activeIndex={stepActiveIndex} />

      <Text style={styles.sectionLabel}>{t("selectType")}</Text>
      <View style={styles.segWrap}>
        {(["buy", "sell"] as const).map((val) => (
          <TouchableOpacity
            key={val}
            style={[styles.segSide, txType === val && styles.segSideOn]}
            onPress={() => setTxType(val)}
            accessibilityRole="button"
            accessibilityState={{ selected: txType === val }}
          >
            <Text style={[styles.segTxt, txType === val && styles.segTxtOn]}>
              {val === "buy" ? t("buy") : t("sell")}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {!review ? (
        <>
          {!isRecording && !isBusy && (
            <TouchableOpacity
              style={styles.recordBtn}
              onPress={() => void startRecording()}
              activeOpacity={0.7}
              accessibilityRole="button"
              accessibilityLabel={t("record")}
            >
              <View style={styles.recordBtnInner}>
                <Ionicons name="mic" size={40} color="#fff" />
              </View>
              <Text style={styles.recordBtnLabel}>{t("voiceTapRecord")}</Text>
              <Text style={styles.recordBtnHint}>{t("voiceAutoStopHint")}</Text>
            </TouchableOpacity>
          )}

          {isRecording && (
            <View style={styles.recordingArea}>
              <Text style={styles.timer}>{formatDuration(durationMs)}</Text>
              <WaveformVisualizer metering={metering} isActive={isRecording} />
              <VoiceStatusIndicator metering={metering} silenceCountdown={silenceCountdown} />

              <TouchableOpacity
                style={styles.stopBtn}
                onPress={() => void doStopAndUpload()}
                disabled={uploading}
                activeOpacity={0.7}
                accessibilityRole="button"
              >
                <View style={styles.stopBtnInner}>
                  <Ionicons name="stop" size={28} color="#fff" />
                </View>
              </TouchableOpacity>
              <Text style={styles.stopHint}>{t("stopRecord")}</Text>
            </View>
          )}

          {isBusy && (
            <View style={styles.processingBox}>
              <ActivityIndicator size="large" color={colors.primary} />
              <Text style={styles.processingText}>{t("processing")}</Text>
              <Text style={styles.processingHint}>
                {polling ? t("voiceProcessingHint") : t("uploadRecord")}
              </Text>
            </View>
          )}
        </>
      ) : (
        <Card style={styles.reviewCard}>
          <View style={styles.reviewHeader}>
            <Ionicons name="checkmark-circle" size={24} color={colors.success} />
            <Text style={styles.cardTitle}>{t("readyForReview")}</Text>
          </View>

          {!!review.transcription?.trim() && (
            <View style={styles.transcriptionBox}>
              <Text style={styles.transcriptionLabel}>{t("transcriptionLabel")}</Text>
              <Text style={styles.transcriptionText}>{review.transcription}</Text>
            </View>
          )}

          <FormField label={t("productName")}>
            <TextFieldInput value={form.product_name} onChangeText={(v) => setForm((f) => ({ ...f, product_name: v }))} />
          </FormField>
          <FormField label={t("category")}>
            <TextFieldInput value={form.category} onChangeText={(v) => setForm((f) => ({ ...f, category: v }))} />
          </FormField>
          <View style={styles.row}>
            <View style={styles.halfField}>
              <FormField label={t("quantity")}>
                <TextFieldInput value={form.quantity} onChangeText={(v) => setForm((f) => ({ ...f, quantity: v }))} keyboardType="numeric" />
              </FormField>
            </View>
            <View style={styles.halfField}>
              <FormField label={t("unitPrice")}>
                <TextFieldInput value={form.unit_price} onChangeText={(v) => setForm((f) => ({ ...f, unit_price: v }))} keyboardType="decimal-pad" />
              </FormField>
            </View>
          </View>
          <FormField label={t("totalAmount")}>
            <TextFieldInput value={form.total_amount} onChangeText={(v) => setForm((f) => ({ ...f, total_amount: v }))} keyboardType="decimal-pad" />
          </FormField>

          <PrimaryButton title={t("confirm")} onPress={() => void handleConfirm()} icon="checkmark-circle-outline" />
          <GhostButton title={t("retry")} onPress={resetFlow} />
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, paddingBottom: space.xxxl },

  sectionLabel: {
    fontSize: font.sm,
    color: colors.textSecondary,
    marginBottom: space.sm,
    fontWeight: font.semibold,
  },
  segWrap: {
    flexDirection: "row",
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    padding: 4,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: space.xl,
  },
  segSide: { flex: 1, paddingVertical: space.sm + 2, alignItems: "center", borderRadius: radius.sm },
  segSideOn: { backgroundColor: colors.primary },
  segTxt: { fontSize: font.md, fontWeight: font.semibold, color: colors.textSecondary },
  segTxtOn: { color: "#fff", fontWeight: font.bold },

  recordBtn: { alignItems: "center", marginVertical: space.xl },
  recordBtnInner: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  recordBtnLabel: {
    marginTop: space.md,
    fontSize: font.md,
    fontWeight: font.bold,
    color: colors.textSecondary,
  },
  recordBtnHint: {
    marginTop: space.xs,
    fontSize: font.xs,
    color: colors.textMuted,
    textAlign: "center",
  },

  recordingArea: {
    alignItems: "center",
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.lg,
    padding: space.lg,
    marginVertical: space.md,
    borderWidth: 1.5,
    borderColor: colors.primary,
  },
  timer: {
    fontSize: 36,
    fontWeight: font.bold,
    color: colors.primary,
    fontVariant: ["tabular-nums"],
    marginBottom: space.xs,
  },

  stopBtn: { alignItems: "center", marginTop: space.md },
  stopBtnInner: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.error,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.error,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 4,
  },
  stopHint: {
    marginTop: space.sm,
    fontSize: font.sm,
    fontWeight: font.semibold,
    color: colors.error,
  },

  processingBox: { alignItems: "center", paddingVertical: space.xxl, gap: space.sm },
  processingText: { fontSize: font.lg, fontWeight: font.bold, color: colors.primary, marginTop: space.sm },
  processingHint: { fontSize: font.sm, color: colors.textMuted, textAlign: "center" },

  reviewCard: { marginTop: space.md },
  reviewHeader: { flexDirection: "row", alignItems: "center", gap: space.sm, marginBottom: space.md },
  cardTitle: { fontSize: font.xl, fontWeight: font.bold, color: colors.primaryDark },

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

  row: { flexDirection: "row", gap: space.md },
  halfField: { flex: 1 },
});
