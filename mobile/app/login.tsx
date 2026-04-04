import { useState, useCallback } from "react";
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform } from "react-native";
import { useRouter } from "expo-router";
import Toast from "react-native-toast-message";
import { useAuth } from "../src/context/AuthContext";
import { useLocale } from "../src/context/LocaleContext";
import { login } from "../src/api/auth";
import { setPendingToken } from "../src/api/client";
import { colors } from "../src/theme/colors";
import { font, radius, space } from "../src/theme/tokens";
import {
  Card,
  PrimaryButton,
  GhostButton,
  FormField,
  TextFieldInput,
  InfoBanner,
} from "../src/components/ui";

export default function LoginScreen() {
  const { t } = useLocale();
  const { setUser, setToken } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("admin@company.com");
  const [password, setPassword] = useState("Admin12345!");
  const [loading, setLoading] = useState(false);
  const [bannerError, setBannerError] = useState<string | null>(null);

  const clearBanner = useCallback(() => setBannerError(null), []);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      const msg = t("emailPasswordRequired");
      setBannerError(msg);
      Toast.show({ type: "error", text1: t("error"), text2: msg });
      return;
    }
    setBannerError(null);
    setLoading(true);
    try {
      const { access_token } = await login({ email: email.trim(), password });
      setPendingToken(access_token);
      const { getMe } = await import("../src/api/auth");
      const user = await getMe();
      setPendingToken(null);
      setToken(access_token);
      setUser(user);
      Toast.show({ type: "success", text1: t("login") });
      router.replace("/");
    } catch (err: unknown) {
      setPendingToken(null);
      const ax = err && typeof err === "object" && "response" in err
        ? (err as { response?: { status?: number; data?: { detail?: string } }; code?: string })
        : null;
      const status = ax?.response?.status;
      const detail = ax?.response?.data?.detail;
      let text2: string;
      if (!ax?.response) {
        text2 = t("loginNetworkError");
      } else if (status === 401 || String(detail).toLowerCase().includes("invalid credentials")) {
        text2 = t("loginInvalidCredentials");
        if (__DEV__) {
          text2 = `${text2} — ${t("loginDevPasswordHint")}`;
        }
      } else {
        text2 = detail != null ? String(detail) : t("loginInvalidCredentials");
      }
      setBannerError(text2);
      Toast.show({ type: "error", text1: t("error"), text2 });
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.root}
    >
      <View style={styles.decor}>
        <View style={styles.decorCircle} />
        <View style={styles.decorCircle2} />
      </View>
      <View style={styles.inner}>
        <View style={styles.brandBlock}>
          <View style={styles.logoMark}>
            <Text style={styles.logoLetter}>A</Text>
          </View>
          <Text style={styles.brandName}>{t("appName")}</Text>
          <Text style={styles.brandTag}>{t("homeTagline")}</Text>
        </View>

        <Card style={styles.card}>
          <Text style={styles.screenTitle}>{t("login")}</Text>
          <Text style={styles.screenSub}>{t("loginSubtitle")}</Text>

          {bannerError ? (
            <InfoBanner variant="error" title={t("error")}>
              {bannerError}
            </InfoBanner>
          ) : null}

          <FormField label={t("email")}>
            <TextFieldInput
              value={email}
              onChangeText={(v) => {
                clearBanner();
                setEmail(v);
              }}
              autoCapitalize="none"
              keyboardType="email-address"
              editable={!loading}
            />
          </FormField>
          <FormField label={t("password")}>
            <TextFieldInput
              value={password}
              onChangeText={(v) => {
                clearBanner();
                setPassword(v);
              }}
              secureTextEntry
              editable={!loading}
            />
          </FormField>

          <PrimaryButton title={t("login")} onPress={() => void handleLogin()} loading={loading} icon="log-in-outline" />

          <GhostButton title={t("register")} onPress={() => router.push("/register")} disabled={loading} />
        </Card>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  decor: { ...StyleSheet.absoluteFillObject, overflow: "hidden" },
  decorCircle: {
    position: "absolute",
    width: 280,
    height: 280,
    borderRadius: 140,
    backgroundColor: colors.primaryMuted,
    opacity: 0.45,
    top: -80,
    right: -100,
  },
  decorCircle2: {
    position: "absolute",
    width: 200,
    height: 200,
    borderRadius: 100,
    backgroundColor: colors.accentSoft,
    opacity: 0.35,
    bottom: 40,
    left: -60,
  },
  inner: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: space.lg,
    paddingVertical: space.xl,
  },
  brandBlock: { alignItems: "center", marginBottom: space.xl },
  logoMark: {
    width: 56,
    height: 56,
    borderRadius: 16,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.md,
  },
  logoLetter: { color: "#fff", fontSize: font.xxl, fontWeight: font.bold },
  brandName: {
    fontSize: font.display,
    fontWeight: font.bold,
    color: colors.primaryDark,
    letterSpacing: -0.5,
  },
  brandTag: {
    fontSize: font.sm,
    color: colors.textMuted,
    marginTop: space.xs,
    textAlign: "center",
    maxWidth: 280,
    lineHeight: 20,
  },
  card: { padding: space.xl },
  screenTitle: {
    fontSize: font.xxl,
    fontWeight: font.bold,
    color: colors.text,
    marginBottom: space.xxs,
  },
  screenSub: { fontSize: font.sm, color: colors.textMuted, marginBottom: space.lg },
});
