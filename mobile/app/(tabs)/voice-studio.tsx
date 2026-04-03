import { useCallback, useMemo, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
} from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { VoiceRecorder } from "../../src/components/VoiceRecorder";
import {
  transcribeSpeech,
  parseInvoiceFromSpeech,
  type TranscribeApiResult,
  type ParseInvoiceVoiceResult,
} from "../../src/api/speechApi";
import Toast from "react-native-toast-message";

type Tx = "buy" | "sell";
type LangOpt = "auto" | "ar" | "fr" | "en";

export default function VoiceStudioScreen() {
  const { t } = useLocale();
  const [txType, setTxType] = useState<Tx>("buy");
  const [lang, setLang] = useState<LangOpt>("auto");
  const [audioUri, setAudioUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [transcript, setTranscript] = useState<TranscribeApiResult | null>(null);
  const [editedText, setEditedText] = useState("");
  const [invoiceResult, setInvoiceResult] = useState<ParseInvoiceVoiceResult | null>(null);

  const langParam = useMemo(() => (lang === "auto" ? undefined : lang), [lang]);

  const onRecordingReady = useCallback((uri: string) => {
    setAudioUri(uri);
    setTranscript(null);
    setInvoiceResult(null);
    setEditedText("");
    Toast.show({ type: "success", text1: t("voiceClipReady") });
  }, [t]);

  const onRecorderError = useCallback(
    (msg: string) => {
      Toast.show({ type: "error", text1: t("error"), text2: msg });
    },
    [t]
  );

  const runTranscribe = async () => {
    if (!audioUri) return;
    setBusy(true);
    try {
      const r = await transcribeSpeech(audioUri, { language: langParam });
      setTranscript(r);
      setEditedText(r.text || "");
      Toast.show({ type: "success", text1: t("transcribeDone") });
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const runParseInvoice = async () => {
    if (!audioUri) return;
    setBusy(true);
    try {
      const r = await parseInvoiceFromSpeech(audioUri, txType, { language: langParam });
      setInvoiceResult(r);
      setTranscript({
        success: true,
        text: r.transcription.text,
        language: String(r.transcription.language ?? ""),
        confidence: r.transcription.confidence ?? null,
      });
      setEditedText(r.transcription.text || "");
      Toast.show({ type: "success", text1: t("voiceInvoiceDone") });
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const invData = invoiceResult?.invoice?.data as Record<string, unknown> | undefined;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{t("voiceStudio")}</Text>
      <Text style={styles.sub}>{t("voiceStudioSub")}</Text>

      <Text style={styles.label}>{t("selectType")}</Text>
      <View style={styles.row}>
        <TouchableOpacity
          style={[styles.chip, txType === "buy" && styles.chipOn]}
          onPress={() => setTxType("buy")}
        >
          <Text style={[styles.chipTxt, txType === "buy" && styles.chipTxtOn]}>{t("buy")}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.chip, txType === "sell" && styles.chipOn]}
          onPress={() => setTxType("sell")}
        >
          <Text style={[styles.chipTxt, txType === "sell" && styles.chipTxtOn]}>{t("sell")}</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.label}>{t("speechLanguage")}</Text>
      <View style={styles.langRow}>
        {(["auto", "ar", "fr", "en"] as const).map((k) => (
          <TouchableOpacity
            key={k}
            style={[styles.langChip, lang === k && styles.langChipOn]}
            onPress={() => setLang(k)}
          >
            <Text style={[styles.langChipTxt, lang === k && styles.langChipTxtOn]}>{k.toUpperCase()}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <VoiceRecorder
        busy={busy}
        labels={{
          record: t("voiceTapRecord"),
          stop: t("stopRecord"),
          micDenied: t("micDenied"),
          recordError: t("voiceRecordError"),
        }}
        onRecordingReady={onRecordingReady}
        onError={onRecorderError}
        style={{ marginVertical: 16 }}
      />

      {audioUri ? (
        <Text style={styles.uriHint}>{t("voiceClipReady")}</Text>
      ) : null}

      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.actionBtn, (!audioUri || busy) && styles.actionBtnOff]}
          onPress={runTranscribe}
          disabled={!audioUri || busy}
        >
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.actionBtnTxt}>{t("transcribeOnly")}</Text>}
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnSecondary, (!audioUri || busy) && styles.actionBtnOff]}
          onPress={runParseInvoice}
          disabled={!audioUri || busy}
        >
          <Text style={styles.actionBtnTxtDark}>{t("voiceInvoiceMode")}</Text>
        </TouchableOpacity>
      </View>

      {(transcript || editedText) ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t("transcriptionLabel")}</Text>
          {transcript?.language ? (
            <Text style={styles.meta}>
              {t("detectedLanguage")}: {transcript.language}
              {transcript.confidence != null ? ` · ${(transcript.confidence * 100).toFixed(0)}%` : ""}
            </Text>
          ) : null}
          <TextInput
            style={styles.textArea}
            multiline
            value={editedText}
            onChangeText={setEditedText}
            placeholderTextColor={colors.textMuted}
          />
        </View>
      ) : null}

      {invData ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t("voiceInvoiceSummary")}</Text>
          <Text style={styles.line}>{t("supplier")}: {String(invData.supplier_name ?? "—")}</Text>
          <Text style={styles.line}>{t("invoiceNumber")}: {String(invData.invoice_number ?? "—")}</Text>
          <Text style={styles.line}>{t("invoiceDate")}: {String(invData.invoice_date ?? "—")}</Text>
          <Text style={styles.line}>{t("totalAmount")}: {String(invData.total_amount ?? "—")}</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 48 },
  title: { fontSize: 22, fontWeight: "700", color: colors.text, marginBottom: 6 },
  sub: { fontSize: 14, color: colors.textMuted, marginBottom: 20 },
  label: { fontSize: 15, fontWeight: "600", color: colors.text, marginBottom: 8 },
  row: { flexDirection: "row", gap: 10, marginBottom: 16 },
  chip: {
    flex: 1,
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
  },
  chipOn: { backgroundColor: colors.primary },
  chipTxt: { fontSize: 15, color: colors.text, fontWeight: "600" },
  chipTxtOn: { color: "#fff" },
  langRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 8 },
  langChip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 20,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
  },
  langChipOn: { borderColor: colors.primary, backgroundColor: colors.surface },
  langChipTxt: { fontSize: 12, fontWeight: "600", color: colors.textMuted },
  langChipTxtOn: { color: colors.primary },
  uriHint: { fontSize: 13, color: colors.success, textAlign: "center", marginBottom: 8 },
  actions: { gap: 10, marginBottom: 20 },
  actionBtn: {
    backgroundColor: colors.primary,
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
    minHeight: 52,
    justifyContent: "center",
  },
  actionBtnSecondary: { backgroundColor: colors.surface, borderWidth: 2, borderColor: colors.primary },
  actionBtnOff: { opacity: 0.45 },
  actionBtnTxt: { color: "#fff", fontSize: 16, fontWeight: "700" },
  actionBtnTxtDark: { color: colors.primary, fontSize: 16, fontWeight: "700" },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardTitle: { fontSize: 16, fontWeight: "700", color: colors.primary, marginBottom: 10 },
  meta: { fontSize: 12, color: colors.textMuted, marginBottom: 8 },
  textArea: {
    minHeight: 120,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 12,
    fontSize: 15,
    color: colors.text,
    textAlignVertical: "top",
  },
  line: { fontSize: 14, color: colors.text, marginBottom: 6 },
});
