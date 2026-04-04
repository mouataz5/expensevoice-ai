import { useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../src/context/AuthContext";
import { useLocale } from "../src/context/LocaleContext";
import { setOnboardingComplete } from "../src/lib/onboarding";
import { colors } from "../src/theme/colors";
import { font, space } from "../src/theme/tokens";
import { ScreenScroll, Card, PrimaryButton, SecondaryButton } from "../src/components/ui";

const STEPS = [
  { icon: "hand-left-outline" as const, titleKey: "onboardingWelcomeTitle", bodyKey: "onboardingWelcomeBody" },
  { icon: "document-text-outline" as const, titleKey: "onboardingStepScanTitle", bodyKey: "onboardingStepScanBody" },
  { icon: "mic-outline" as const, titleKey: "onboardingStepVoiceTitle", bodyKey: "onboardingStepVoiceBody" },
  { icon: "notifications-outline" as const, titleKey: "onboardingStepAlertsTitle", bodyKey: "onboardingStepAlertsBody" },
];

export default function OnboardingScreen() {
  const { t } = useLocale();
  const { user } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [finishing, setFinishing] = useState(false);

  const goTabs = () => {
    const isDirector = user?.role === "director" || user?.role === "admin";
    router.replace(isDirector ? "/(tabs-director)" : "/(tabs)");
  };

  const finish = async () => {
    setFinishing(true);
    try {
      await setOnboardingComplete();
      goTabs();
    } finally {
      setFinishing(false);
    }
  };

  const next = () => {
    if (step < STEPS.length - 1) setStep((s) => s + 1);
    else void finish();
  };

  const back = () => setStep((s) => Math.max(0, s - 1));

  const s = STEPS[step]!;

  return (
    <ScreenScroll contentStyle={styles.scroll}>
      <View style={styles.dots}>
        {STEPS.map((_, i) => (
          <View key={i} style={[styles.dot, i === step && styles.dotOn]} />
        ))}
      </View>

      <Card style={styles.card}>
        <View style={styles.iconCircle}>
          <Ionicons name={s.icon} size={36} color={colors.primary} />
        </View>
        <Text style={styles.title}>{t(s.titleKey)}</Text>
        <Text style={styles.body}>{t(s.bodyKey)}</Text>
      </Card>

      <View style={styles.actions}>
        {step > 0 ? (
          <SecondaryButton title={t("back")} onPress={back} icon="arrow-back-outline" />
        ) : (
          <View style={styles.actionSpacer} />
        )}
        <View style={styles.primaryWrap}>
          <PrimaryButton
            title={step < STEPS.length - 1 ? t("onboardingNext") : t("onboardingStart")}
            onPress={next}
            loading={finishing && step === STEPS.length - 1}
            disabled={finishing}
            icon={step < STEPS.length - 1 ? "arrow-forward-outline" : "checkmark-circle-outline"}
          />
        </View>
      </View>
    </ScreenScroll>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingBottom: space.xxxl },
  dots: { flexDirection: "row", justifyContent: "center", gap: space.xs, marginBottom: space.lg },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.border },
  dotOn: { backgroundColor: colors.primary, width: 22 },
  card: { alignItems: "center", paddingVertical: space.xxl },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.lg,
  },
  title: {
    fontSize: font.xl,
    fontWeight: font.bold,
    color: colors.primaryDark,
    textAlign: "center",
    marginBottom: space.md,
  },
  body: { fontSize: font.md, color: colors.textSecondary, textAlign: "center", lineHeight: 24, paddingHorizontal: space.sm },
  actions: { flexDirection: "row", alignItems: "center", gap: space.sm, marginTop: space.xl },
  actionSpacer: { flex: 1 },
  primaryWrap: { flex: 2 },
});
