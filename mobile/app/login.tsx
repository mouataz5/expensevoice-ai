import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import Toast from "react-native-toast-message";
import { useAuth } from "../src/context/AuthContext";
import { useLocale } from "../src/context/LocaleContext";
import { login } from "../src/api/auth";
import { colors } from "../src/theme/colors";

export default function LoginScreen() {
  const { t } = useLocale();
  const { setUser, setToken } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      Toast.show({ type: "error", text1: t("error"), text2: "Email and password required" });
      return;
    }
    setLoading(true);
    try {
      const { access_token } = await login({ email: email.trim(), password });
      const { getMe } = await import("../src/api/auth");
      const user = await getMe();
      setToken(access_token);
      setUser(user);
      Toast.show({ type: "success", text1: t("login") });
      router.replace("/(tabs)");
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "response" in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : "Invalid credentials";
      Toast.show({ type: "error", text1: t("error"), text2: String(msg) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.container}
    >
      <View style={styles.card}>
        <Text style={styles.title}>{t("appName")}</Text>
        <Text style={styles.subtitle}>{t("login")}</Text>
        <TextInput
          style={styles.input}
          placeholder={t("email")}
          placeholderTextColor={colors.textMuted}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          editable={!loading}
        />
        <TextInput
          style={styles.input}
          placeholder={t("password")}
          placeholderTextColor={colors.textMuted}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          editable={!loading}
        />
        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>{t("login")}</Text>
          )}
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.link}
          onPress={() => router.push("/register")}
          disabled={loading}
        >
          <Text style={styles.linkText}>{t("register")}</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    padding: 24,
    backgroundColor: colors.background,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
  },
  title: { fontSize: 22, fontWeight: "700", color: colors.primary, textAlign: "center", marginBottom: 4 },
  subtitle: { fontSize: 16, color: colors.textMuted, textAlign: "center", marginBottom: 24 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
    fontSize: 16,
    color: colors.text,
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
  },
  buttonDisabled: { opacity: 0.7 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  link: { marginTop: 16, alignItems: "center" },
  linkText: { color: colors.primary, fontSize: 14 },
});
