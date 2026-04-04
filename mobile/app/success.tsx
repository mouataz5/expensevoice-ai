import { View, Text, StyleSheet } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useLocale } from "../src/context/LocaleContext";
import { colors } from "../src/theme/colors";
import { font, radius, shadow, space } from "../src/theme/tokens";
import { PrimaryButton, SecondaryButton } from "../src/components/ui";

export default function SuccessScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const { flow } = useLocalSearchParams<{ flow?: string }>();
  const f = typeof flow === "string" ? flow : flow?.[0];

  const title =
    f === "purchase"
      ? t("successPurchaseTitle")
      : f === "voice_transcribe"
        ? t("successVoiceTranscribeTitle")
        : f === "voice_invoice"
          ? t("successVoiceInvoiceTitle")
          : t("successGenericTitle");
  const subtitle =
    f === "purchase"
      ? t("successPurchaseSubtitle")
      : f === "voice_transcribe"
        ? t("successVoiceTranscribeSubtitle")
        : f === "voice_invoice"
          ? t("successVoiceInvoiceSubtitle")
          : t("successGenericSubtitle");

  const goPurchases = () => router.replace("/(tabs)/purchases");
  const goHome = () => router.replace("/(tabs)");

  return (
    <View style={styles.root}>
      <View style={styles.card}>
        <View style={styles.iconCircle}>
          <Ionicons name="checkmark-circle" size={52} color={colors.success} />
        </View>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.sub}>{subtitle}</Text>
        {f === "purchase" ? (
          <PrimaryButton title={t("successCtaPurchases")} onPress={goPurchases} icon="list-outline" />
        ) : (
          <PrimaryButton title={t("successCtaHome")} onPress={goHome} icon="home-outline" />
        )}
        <SecondaryButton title={t("successCtaScan")} onPress={() => router.replace("/(tabs)/scan")} icon="document-text-outline" />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    padding: space.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: space.xl,
    alignItems: "stretch",
    gap: space.md,
    maxWidth: 400,
    alignSelf: "center",
    width: "100%",
    ...shadow.card,
  },
  iconCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.successSoft,
    alignSelf: "center",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.xs,
  },
  title: { fontSize: font.xxl, fontWeight: font.bold, color: colors.primaryDark, textAlign: "center" },
  sub: { fontSize: font.md, color: colors.textSecondary, textAlign: "center", lineHeight: 22 },
});
