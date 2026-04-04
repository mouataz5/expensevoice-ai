import { View, Text, StyleSheet, TouchableOpacity, Linking } from "react-native";
import { useRouter } from "expo-router";
import Constants from "expo-constants";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import type { Locale } from "../../src/i18n/translations";
import { colors } from "../../src/theme/colors";
import { font, space } from "../../src/theme/tokens";
import {
  ScreenScroll,
  Card,
  SectionTitle,
  DestructiveOutlineButton,
  LangChips,
  UserAvatar,
} from "../../src/components/ui";
import { confirmAsync } from "../../src/lib/confirm";

/** Shown in “Contact support”; override via EXPO_PUBLIC_SUPPORT_EMAIL if needed. */
const SUPPORT_EMAIL =
  (typeof process !== "undefined" && process.env.EXPO_PUBLIC_SUPPORT_EMAIL) || "support@abesagrotech.tn";

function roleLabel(t: (k: string) => string, role: string | undefined): string {
  if (role === "admin") return t("roleAdmin");
  if (role === "director") return t("roleDirector");
  if (role === "employee") return t("roleEmployee");
  return role ?? "—";
}

export default function ProfileScreen() {
  const { user, signOut } = useAuth();
  const { t, locale, setLocale } = useLocale();
  const router = useRouter();

  const handleLogout = async () => {
    await signOut();
    router.replace("/login");
  };

  const onLogoutPress = () => {
    void confirmAsync(t("confirmLogoutTitle"), t("confirmLogoutMessage"), {
      confirmLabel: t("logout"),
      cancelLabel: t("cancel"),
      destructive: true,
    }).then((ok) => {
      if (ok) void handleLogout();
    });
  };

  const appVersion = Constants.expoConfig?.version ?? "1.0.0";

  const openSupport = () => {
    void Linking.openURL(`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(t("appName"))}`);
  };

  return (
    <ScreenScroll>
      <Card style={styles.profileCard}>
        <UserAvatar
          email={user?.email}
          size="xl"
          role={user?.role}
          showRoleBadge
          accessibilityLabel={user?.email ?? undefined}
        />
        <Text style={styles.name}>{user?.email ?? "—"}</Text>
        <Text style={styles.roleCaption}>{roleLabel(t, user?.role)}</Text>
      </Card>

      <SectionTitle title={t("profileSupportTitle")} subtitle={t("profileSupportBody")} />
      <Card>
        <TouchableOpacity style={styles.supportRow} onPress={openSupport} accessibilityRole="button">
          <Text style={styles.supportLabel}>{t("profileContactSupport")}</Text>
          <Text style={styles.supportEmail}>{SUPPORT_EMAIL}</Text>
        </TouchableOpacity>
      </Card>

      <SectionTitle title={t("profileAppVersion")} />
      <Card>
        <Text style={styles.versionText}>
          {t("appName")} · v{appVersion}
        </Text>
      </Card>

      <SectionTitle title={t("profileSecurityTitle")} subtitle={t("profileSecurityBody")} />
      <Card style={styles.securityCard}>
        <Text style={styles.securityText}>{t("profileSecurityHint")}</Text>
      </Card>

      <SectionTitle title={t("profileSession")} subtitle={t("profileLanguageHint")} />
      <Card>
        <LangChips
          options={[
            { key: "ar", label: "العربية" },
            { key: "fr", label: "Français" },
            { key: "en", label: "English" },
          ]}
          value={locale}
          onChange={(k) => setLocale(k as Locale)}
        />
      </Card>

      <View style={styles.logoutWrap}>
        <DestructiveOutlineButton title={t("logout")} onPress={onLogoutPress} icon="log-out-outline" />
      </View>
    </ScreenScroll>
  );
}

const styles = StyleSheet.create({
  profileCard: { alignItems: "center", paddingVertical: space.xxl },
  name: {
    fontSize: font.lg,
    fontWeight: font.bold,
    color: colors.text,
    textAlign: "center",
    marginTop: space.md,
  },
  roleCaption: {
    marginTop: space.xs,
    fontSize: font.sm,
    fontWeight: font.semibold,
    color: colors.textMuted,
    textAlign: "center",
  },
  logoutWrap: { marginTop: space.xl },
  supportRow: { paddingVertical: space.xs },
  supportLabel: { fontSize: font.sm, fontWeight: font.bold, color: colors.text, marginBottom: space.xs },
  supportEmail: { fontSize: font.md, color: colors.primary, fontWeight: font.semibold },
  versionText: { fontSize: font.md, color: colors.textSecondary, fontWeight: font.medium },
  securityCard: { backgroundColor: colors.surfaceMuted, borderStyle: "dashed" },
  securityText: { fontSize: font.sm, color: colors.textSecondary, lineHeight: 22 },
});
