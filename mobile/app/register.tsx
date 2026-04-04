import { useState, useCallback } from "react";
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform, ScrollView } from "react-native";
import { useRouter } from "expo-router";
import Toast from "react-native-toast-message";
import { useLocale } from "../src/context/LocaleContext";
import { colors } from "../src/theme/colors";
import { font, space } from "../src/theme/tokens";
import { api } from "../src/api/client";
import { setStoredToken } from "../src/lib/secure-store";
import { useAuth } from "../src/context/AuthContext";
import {
  Card,
  PrimaryButton,
  GhostButton,
  FormField,
  TextFieldInput,
  InfoBanner,
} from "../src/components/ui";

export default function RegisterScreen() {
  const { t } = useLocale();
  const { setUser, setToken } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [bannerError, setBannerError] = useState<string | null>(null);

  const clearBanner = useCallback(() => setBannerError(null), []);

  const handleRegister = async () => {
    if (!email.trim() || !password) {
      const msg = t("emailPasswordRequired");
      setBannerError(msg);
      Toast.show({ type: "error", text1: t("error"), text2: msg });
      return;
    }
    if (password !== confirmPassword) {
      const msg = t("passwordsMismatch");
      setBannerError(msg);
      Toast.show({ type: "error", text1: t("error"), text2: msg });
      return;
    }
    setBannerError(null);
    setLoading(true);
    try {
      const { data } = await api.post<{ access_token: string }>("/auth/register", {
        email: email.trim(),
        password,
        role: "employee",
      });
      if (data.access_token) await setStoredToken(data.access_token);
      const { data: user } = await api.get<{ id: string; email: string; role: string }>("/me");
      setToken(data.access_token);
      setUser(user);
      Toast.show({ type: "success", text1: t("register") });
      router.replace("/");
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "response" in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : "Registration failed";
      const s = String(msg);
      setBannerError(s);
      Toast.show({ type: "error", text1: t("error"), text2: s });
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.root}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.brandRow}>
          <View style={styles.logoMark}>
            <Text style={styles.logoLetter}>A</Text>
          </View>
          <Text style={styles.brandName}>{t("appName")}</Text>
        </View>
        <Card style={styles.card}>
          <Text style={styles.title}>{t("register")}</Text>
          <Text style={styles.sub}>{t("registerSubtitle")}</Text>
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
          <FormField label={t("confirmPassword")}>
            <TextFieldInput
              value={confirmPassword}
              onChangeText={(v) => {
                clearBanner();
                setConfirmPassword(v);
              }}
              secureTextEntry
              editable={!loading}
            />
          </FormField>
          <PrimaryButton title={t("register")} onPress={() => void handleRegister()} loading={loading} icon="person-add-outline" />
          <GhostButton title={t("login")} onPress={() => router.back()} disabled={loading} />
        </Card>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  scroll: { flexGrow: 1, justifyContent: "center", padding: space.lg, paddingVertical: space.xxxl },
  brandRow: { alignItems: "center", marginBottom: space.lg },
  logoMark: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.sm,
  },
  logoLetter: { color: "#fff", fontSize: font.xl, fontWeight: font.bold },
  brandName: { fontSize: font.xl, fontWeight: font.bold, color: colors.primaryDark },
  card: { padding: space.xl },
  title: { fontSize: font.xxl, fontWeight: font.bold, color: colors.text, marginBottom: space.xxs },
  sub: { fontSize: font.sm, color: colors.textMuted, marginBottom: space.lg },
});
