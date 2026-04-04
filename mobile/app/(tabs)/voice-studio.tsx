import { useCallback, useMemo, useState, Fragment } from "react";
import { View, Text, StyleSheet, TextInput } from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, space } from "../../src/theme/tokens";
import { VoiceRecorder } from "../../src/components/VoiceRecorder";
import {
  transcribeSpeech,
  parseInvoiceFromSpeech,
  type TranscribeApiResult,
  type ParseInvoiceVoiceResult,
} from "../../src/api/speechApi";
import Toast from "react-native-toast-message";
import {
  ScreenScroll,
  SectionTitle,
  SegmentedPair,
  LangChips,
  Card,
  PrimaryButton,
  SecondaryButton,
  InfoBanner,
} from "../../src/components/ui";
import { SuccessCelebration } from "../../src/components/ui/SuccessCelebration";

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
  const [showTranscribeSuccess, setShowTranscribeSuccess] = useState(false);
  const [showInvoiceSuccess, setShowInvoiceSuccess] = useState(false);

  const langParam = useMemo(() => (lang === "auto" ? undefined : lang), [lang]);

  const onRecordingReady = useCallback(
    (uri: string) => {
      setAudioUri(uri);
      setTranscript(null);
      setInvoiceResult(null);
      setEditedText("");
      Toast.show({ type: "success", text1: t("voiceClipReady") });
    },
    [t]
  );

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
      setShowTranscribeSuccess(true);
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const textForParse = editedText.trim();
  const canParseInvoice = Boolean(textForParse || audioUri);

  const runParseInvoice = async () => {
    if (!canParseInvoice) return;
    setBusy(true);
    try {
      const r = await parseInvoiceFromSpeech(txType, {
        text: textForParse || undefined,
        audioUri: textForParse ? undefined : audioUri ?? undefined,
        language: langParam,
      });
      setInvoiceResult(r);
      setTranscript({
        success: true,
        text: r.transcription.text,
        language: String(r.transcription.language ?? ""),
        confidence: r.transcription.confidence ?? null,
      });
      setEditedText(r.transcription.text || "");
      setShowInvoiceSuccess(true);
    } catch (e) {
      Toast.show({ type: "error", text1: t("error"), text2: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const invData = invoiceResult?.invoice?.data as Record<string, unknown> | undefined;
  const vp = invoiceResult?.voice_purchase;

  return (
    <Fragment>
      <SuccessCelebration
        visible={showTranscribeSuccess}
        title={t("successVoiceTranscribeTitle")}
        subtitle={t("successVoiceTranscribeSubtitle")}
        primaryLabel={t("successVoiceContinue")}
        onPrimary={() => setShowTranscribeSuccess(false)}
        icon="text-outline"
      />
      <SuccessCelebration
        visible={showInvoiceSuccess}
        title={t("successVoiceInvoiceTitle")}
        subtitle={t("successVoiceInvoiceSubtitle")}
        primaryLabel={t("successVoiceContinue")}
        onPrimary={() => setShowInvoiceSuccess(false)}
        icon="receipt-outline"
      />
    <ScreenScroll contentStyle={styles.scrollPad}>
      <SectionTitle title={t("voiceStudio")} subtitle={t("voiceStudioSub")} />

      <Text style={styles.label}>{t("selectType")}</Text>
      <SegmentedPair
        left={{ label: t("buy"), value: "buy" }}
        right={{ label: t("sell"), value: "sell" }}
        value={txType}
        onChange={(v) => setTxType(v as Tx)}
      />

      <Text style={styles.label}>{t("speechLanguage")}</Text>
      <LangChips
        options={[
          { key: "auto", label: "AUTO" },
          { key: "ar", label: "AR" },
          { key: "fr", label: "FR" },
          { key: "en", label: "EN" },
        ]}
        value={lang}
        onChange={(k) => setLang(k as LangOpt)}
      />

      <Card style={styles.recCard}>
        <Text style={styles.recTitle}>{t("voiceTapRecord")}</Text>
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
          style={styles.recorderSlot}
        />
        {audioUri ? (
          <Text style={styles.uriHint}>{t("voiceClipReady")}</Text>
        ) : null}
      </Card>

      <InfoBanner variant="info" title={t("transcribeOnly")}>
        {t("voiceModeHintTranscribe")}
      </InfoBanner>
      <InfoBanner variant="success" title={t("voiceInvoiceMode")}>
        {t("voiceModeHintInvoice")}
      </InfoBanner>

      <View style={styles.actions}>
        <PrimaryButton
          title={busy ? t("processing") : t("transcribeOnly")}
          onPress={() => void runTranscribe()}
          loading={busy}
          disabled={!audioUri || busy}
          icon="text-outline"
        />
        <SecondaryButton
          title={t("voiceInvoiceMode")}
          onPress={() => void runParseInvoice()}
          disabled={!canParseInvoice || busy}
          icon="analytics-outline"
        />
      </View>

      {transcript || editedText ? (
        <Card>
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
            placeholderTextColor={colors.textSubtle}
          />
        </Card>
      ) : null}

      {vp && (vp.items?.length ?? 0) > 0 ? (
        <Card>
          <Text style={styles.cardTitle}>{t("voiceLinesTitle")}</Text>
          <Text style={styles.meta}>
            {t("voiceLinesType")}: {vp.type} · {vp.currency}
            {vp.total != null ? ` · ${t("totalAmount")}: ${vp.total}` : ""}
          </Text>
          {vp.items.map((it, i) => (
            <View key={`vl-${i}`} style={styles.lineRow}>
              <Text style={styles.lineStrong}>{it.name}</Text>
              <Text style={styles.line}>
                ×{it.quantity ?? "—"} @ {it.unit_price ?? "—"} → {it.line_total ?? "—"}
              </Text>
            </View>
          ))}
          {(vp.warnings?.length ?? 0) > 0 ? (
            <Text style={styles.warnings}>{vp.warnings.join(" · ")}</Text>
          ) : null}
        </Card>
      ) : null}

      {invData ? (
        <Card>
          <Text style={styles.cardTitle}>{t("voiceInvoiceSummary")}</Text>
          <Text style={styles.line}>{t("supplier")}: {String(invData.supplier_name ?? "—")}</Text>
          <Text style={styles.line}>{t("invoiceNumber")}: {String(invData.invoice_number ?? "—")}</Text>
          <Text style={styles.line}>{t("invoiceDate")}: {String(invData.invoice_date ?? "—")}</Text>
          <Text style={styles.line}>{t("totalAmount")}: {String(invData.total_amount ?? "—")}</Text>
        </Card>
      ) : null}
    </ScreenScroll>
    </Fragment>
  );
}

const styles = StyleSheet.create({
  scrollPad: { paddingBottom: space.xxxl },
  label: { fontSize: font.sm, fontWeight: font.semibold, color: colors.textSecondary, marginBottom: space.sm, marginTop: space.md },
  recCard: { marginTop: space.lg, marginBottom: space.md },
  recTitle: { fontSize: font.sm, fontWeight: font.bold, color: colors.textMuted, marginBottom: space.sm, textAlign: "center" },
  recorderSlot: { marginVertical: space.sm },
  uriHint: { fontSize: font.sm, color: colors.success, textAlign: "center", marginTop: space.sm, fontWeight: font.semibold },
  actions: { gap: space.sm, marginBottom: space.lg },
  cardTitle: { fontSize: font.lg, fontWeight: font.bold, color: colors.primaryDark, marginBottom: space.sm },
  meta: { fontSize: font.xs, color: colors.textMuted, marginBottom: space.sm },
  textArea: {
    minHeight: 140,
    borderWidth: 1.5,
    borderColor: colors.borderStrong,
    borderRadius: radius.md,
    padding: space.md,
    fontSize: font.md,
    color: colors.text,
    textAlignVertical: "top",
    backgroundColor: colors.surface,
  },
  line: { fontSize: font.sm, color: colors.text, marginBottom: space.xs },
  lineRow: { marginBottom: space.sm, paddingBottom: space.sm, borderBottomWidth: 1, borderBottomColor: colors.divider },
  lineStrong: { fontSize: font.md, fontWeight: font.bold, color: colors.text, marginBottom: 4 },
  warnings: { fontSize: font.xs, color: colors.textMuted, marginTop: space.sm, fontStyle: "italic" },
});
