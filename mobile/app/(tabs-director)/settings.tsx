import { useEffect, useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, Linking } from "react-native";
import { useRouter } from "expo-router";
import Constants from "expo-constants";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import type { Locale } from "../../src/i18n/translations";
import { colors } from "../../src/theme/colors";
import { font, space } from "../../src/theme/tokens";
import { fetchSettings, updateSettings } from "../../src/api/settings";
import Toast from "react-native-toast-message";
import { confirmAsync } from "../../src/lib/confirm";
import { formatApiError } from "../../src/utils/apiError";
import {
  ScreenScroll,
  Card,
  SectionTitle,
  TextFieldInput,
  PrimaryButton,
  DestructiveOutlineButton,
  LangChips,
  ProductBrandMark,
  InfoBanner,
  FormField,
  AdminSettingsFormSkeleton,
  UserAvatar,
} from "../../src/components/ui";
import { AdminAccentStripe, AdminHeader } from "../../src/components/admin";

const SUPPORT_EMAIL =
  (typeof process !== "undefined" && process.env.EXPO_PUBLIC_SUPPORT_EMAIL) || "support@abesagrotech.tn";

function roleLabel(t: (k: string) => string, role: string | undefined): string {
  if (role === "admin") return t("roleAdmin");
  if (role === "director") return t("roleDirector");
  if (role === "employee") return t("roleEmployee");
  return role ?? "—";
}

export default function DirectorSettingsScreen() {
  const { user, signOut } = useAuth();
  const { t, locale, setLocale } = useLocale();
  const router = useRouter();
  const qc = useQueryClient();
  const isAdmin = user?.role === "admin";

  const [companyName, setCompanyName] = useState("");
  const [currency, setCurrency] = useState("TND");
  const [maxPerPurchase, setMaxPerPurchase] = useState("500");
  const [dailyLimit, setDailyLimit] = useState("1500");

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  useEffect(() => {
    if (!settings) return;
    setCompanyName(settings.company_name ?? "");
    setCurrency(settings.currency ?? "TND");
    setMaxPerPurchase(String(settings.default_limits?.max_per_purchase ?? 500));
    setDailyLimit(String(settings.default_limits?.daily_limit_default ?? 1500));
  }, [settings]);

  const updateM = useMutation({
    mutationFn: (payload: Parameters<typeof updateSettings>[0]) => updateSettings(payload),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("settingsSaved") });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message });
    },
  });

  const handleSave = () => {
    const max = parseInt(maxPerPurchase, 10);
    const daily = parseInt(dailyLimit, 10);
    if (isNaN(max) || isNaN(daily)) return;
    updateM.mutate({
      company_name: companyName || undefined,
      currency: currency || undefined,
      default_limits: { max_per_purchase: max, daily_limit_default: daily },
    });
  };

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
      <AdminAccentStripe />
      <ProductBrandMark title={t("appName")} subtitle={t("settings")} />
      <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("adminSettingsWorkspaceSubtitle")} />

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

      {isLoading ? (
        <>
          <SectionTitle title={t("settings")} subtitle={t("adminLoadingWorkspace")} />
          <AdminSettingsFormSkeleton />
        </>
      ) : (
        <Card>
          {!isAdmin ? (
            <InfoBanner variant="info" title={t("settings")}>
              {t("directorSettingsReadOnly")}
            </InfoBanner>
          ) : null}
          <FormField label={t("settingsCompanyName")}>
            <TextFieldInput
              value={companyName}
              onChangeText={setCompanyName}
              placeholder={t("settingsCompanyName")}
              editable={isAdmin}
            />
          </FormField>
          <FormField label={t("settingsCurrency")}>
            <TextFieldInput value={currency} onChangeText={setCurrency} placeholder="TND" editable={isAdmin} />
          </FormField>
          <FormField label={t("limitsMaxPerPurchase")}>
            <TextFieldInput
              value={maxPerPurchase}
              onChangeText={setMaxPerPurchase}
              placeholder="500"
              keyboardType="numeric"
              editable={isAdmin}
            />
          </FormField>
          <FormField label={t("limitsDailyDefault")}>
            <TextFieldInput
              value={dailyLimit}
              onChangeText={setDailyLimit}
              placeholder="1500"
              keyboardType="numeric"
              editable={isAdmin}
            />
          </FormField>
          {isAdmin ? (
            <PrimaryButton
              title={t("settingsSave")}
              onPress={handleSave}
              loading={updateM.isPending}
              disabled={updateM.isPending}
              icon="save-outline"
            />
          ) : null}
        </Card>
      )}

      <View style={styles.logoutWrap}>
        <DestructiveOutlineButton title={t("logout")} onPress={onLogoutPress} icon="log-out-outline" />
      </View>
    </ScreenScroll>
  );
}

const styles = StyleSheet.create({
  profileCard: { alignItems: "center", paddingVertical: space.xl },
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
  supportRow: { paddingVertical: space.xs },
  supportLabel: { fontSize: font.sm, fontWeight: font.bold, color: colors.text, marginBottom: space.xs },
  supportEmail: { fontSize: font.md, color: colors.primary, fontWeight: font.semibold },
  versionText: { fontSize: font.md, color: colors.textSecondary, fontWeight: font.medium },
  securityCard: { backgroundColor: colors.surfaceMuted, borderStyle: "dashed" },
  securityText: { fontSize: font.sm, color: colors.textSecondary, lineHeight: 22 },
  logoutWrap: { marginTop: space.xl },
});
