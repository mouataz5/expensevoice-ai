import type { ReactNode } from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../theme/colors";
import { font, radius, space } from "../../theme/tokens";
import { Card, PrimaryButton, GhostButton } from "../ui/primitives";
import type { ScanQualityLevel, ScanIssueKey } from "../../lib/scanImageQuality";

type TFn = (key: string) => string;

function issueMessageKey(issue: ScanIssueKey): string {
  return `scanQualityIssue_${issue}`;
}

export function ScanQualityBadge({
  level,
  analyzing,
  t,
}: {
  level: ScanQualityLevel | null;
  analyzing: boolean;
  t: TFn;
}) {
  if (analyzing) {
    return (
      <View style={[styles.badge, styles.badgeNeutral]}>
        <Text style={styles.badgeTextNeutral}>{t("scanQualityAnalyzing")}</Text>
      </View>
    );
  }
  if (!level) return null;
  const map = {
    good: { style: styles.badgeGood, textStyle: styles.badgeTextGood, label: t("scanQualityGood") },
    fair: { style: styles.badgeFair, textStyle: styles.badgeTextFair, label: t("scanQualityFair") },
    poor: { style: styles.badgePoor, textStyle: styles.badgeTextPoor, label: t("scanQualityPoor") },
  };
  const m = map[level];
  return (
    <View style={[styles.badge, m.style]} accessibilityRole="text">
      <Ionicons
        name={level === "good" ? "checkmark-circle" : level === "fair" ? "alert-circle-outline" : "warning"}
        size={16}
        color={level === "good" ? colors.success : level === "fair" ? colors.warning : colors.error}
        style={styles.badgeIcon}
      />
      <Text style={m.textStyle}>{m.label}</Text>
    </View>
  );
}

export function ScanQualityBanner({
  level,
  primaryIssue,
  t,
}: {
  level: ScanQualityLevel;
  primaryIssue: ScanIssueKey | null;
  t: TFn;
}) {
  if (level === "good") {
    return (
      <View style={[styles.banner, styles.bannerGood]}>
        <Ionicons name="checkmark-circle" size={20} color={colors.success} style={styles.bannerIcon} />
        <View style={styles.bannerBody}>
          <Text style={styles.bannerTitleGood}>{t("scanQualityBannerGoodTitle")}</Text>
          <Text style={styles.bannerText}>{t("scanQualityBannerGoodBody")}</Text>
        </View>
      </View>
    );
  }

  const variant = level === "poor" ? "poor" : "fair";
  const borderColor = variant === "poor" ? colors.error : colors.warning;
  const bg = variant === "poor" ? colors.errorSoft : colors.warningSoft;
  const icon = variant === "poor" ? ("close-circle" as const) : ("alert-circle" as const);
  const title =
    level === "poor" ? t("scanQualityBannerPoorTitle") : t("scanQualityBannerFairTitle");
  const body =
    primaryIssue != null ? t(issueMessageKey(primaryIssue)) : t("scanQualityBannerFairBody");

  return (
    <View style={[styles.banner, { backgroundColor: bg, borderLeftColor: borderColor }]}>
      <Ionicons name={icon} size={20} color={borderColor} style={styles.bannerIcon} />
      <View style={styles.bannerBody}>
        <Text style={[styles.bannerTitle, { color: colors.text }]}>{title}</Text>
        <Text style={styles.bannerText}>{body}</Text>
      </View>
    </View>
  );
}

export function ScanTipsCard({ t }: { t: TFn }) {
  const keys = ["scanTipStable", "scanTipFrame", "scanTipLight", "scanTipStraight", "scanTipClose"] as const;
  return (
    <Card style={styles.tipsCard}>
      <Text style={styles.tipsTitle}>{t("scanTipsTitle")}</Text>
      {keys.map((k) => (
        <View key={k} style={styles.tipRow}>
          <Ionicons name="ellipse" size={6} color={colors.primary} style={styles.tipBullet} />
          <Text style={styles.tipText}>{t(k)}</Text>
        </View>
      ))}
    </Card>
  );
}

export function RetakeRecommendationCard({
  onRetake,
  onContinueAnyway,
  t,
}: {
  onRetake: () => void;
  onContinueAnyway: () => void;
  t: TFn;
}) {
  return (
    <Card style={styles.retakeCard}>
      <View style={styles.retakeHeader}>
        <Ionicons name="camera-outline" size={22} color={colors.error} />
        <Text style={styles.retakeTitle}>{t("scanPoorRecommendTitle")}</Text>
      </View>
      <Text style={styles.retakeBody}>{t("scanPoorRecommendBody")}</Text>
      <PrimaryButton title={t("scanRetakePhoto")} onPress={onRetake} icon="camera-outline" />
      <View style={styles.retakeSpacer} />
      <GhostButton title={t("scanContinueAnyway")} onPress={onContinueAnyway} />
    </Card>
  );
}

export function ScanPreviewFrame({ children }: { children: ReactNode }) {
  return <View style={styles.previewFrame}>{children}</View>;
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    paddingHorizontal: space.sm + 2,
    paddingVertical: space.xs + 2,
    borderRadius: radius.full,
    marginBottom: space.sm,
  },
  badgeNeutral: { backgroundColor: colors.surfaceMuted },
  badgeGood: { backgroundColor: colors.successSoft },
  badgeFair: { backgroundColor: colors.warningSoft },
  badgePoor: { backgroundColor: colors.errorSoft },
  badgeTextNeutral: { fontSize: font.sm, color: colors.textMuted, fontWeight: font.semibold },
  badgeTextGood: { fontSize: font.sm, color: colors.success, fontWeight: font.bold },
  badgeTextFair: { fontSize: font.sm, color: colors.warning, fontWeight: font.bold },
  badgeTextPoor: { fontSize: font.sm, color: colors.error, fontWeight: font.bold },
  badgeIcon: { marginRight: space.xs },
  banner: {
    flexDirection: "row",
    alignItems: "flex-start",
    padding: space.md,
    borderRadius: radius.md,
    borderLeftWidth: 4,
    marginBottom: space.md,
  },
  bannerGood: {
    backgroundColor: colors.successSoft,
    borderLeftColor: colors.success,
  },
  bannerIcon: { marginRight: space.sm, marginTop: 2 },
  bannerBody: { flex: 1 },
  bannerTitle: { fontSize: font.sm, fontWeight: font.bold, marginBottom: space.xs },
  bannerTitleGood: { fontSize: font.sm, fontWeight: font.bold, color: colors.success, marginBottom: space.xs },
  bannerText: { fontSize: font.sm, color: colors.textSecondary, lineHeight: 20 },
  tipsCard: { marginBottom: space.md, padding: space.md },
  tipsTitle: {
    fontSize: font.sm,
    fontWeight: font.bold,
    color: colors.primaryDark,
    marginBottom: space.sm,
  },
  tipRow: { flexDirection: "row", alignItems: "flex-start", marginBottom: space.xs },
  tipBullet: { marginTop: 7, marginRight: space.sm },
  tipText: { flex: 1, fontSize: font.sm, color: colors.textSecondary, lineHeight: 20 },
  retakeCard: {
    marginBottom: space.md,
    padding: space.md,
    borderWidth: 1,
    borderColor: colors.error,
    backgroundColor: colors.surface,
  },
  retakeHeader: { flexDirection: "row", alignItems: "center", gap: space.sm, marginBottom: space.sm },
  retakeTitle: { flex: 1, fontSize: font.md, fontWeight: font.bold, color: colors.error },
  retakeBody: { fontSize: font.sm, color: colors.textSecondary, lineHeight: 20, marginBottom: space.md },
  retakeSpacer: { height: space.sm },
  previewFrame: {
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    overflow: "hidden",
    backgroundColor: colors.surfaceMuted,
  },
});
