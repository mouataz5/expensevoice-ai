import type { ReactNode } from "react";
import { View, Text, StyleSheet, TouchableOpacity, type ViewStyle } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../theme/colors";
import { font, radius, shadow, space } from "../../theme/tokens";
import { Card } from "../ui/primitives";

/** Director / admin workspace — visual accent (use sparingly). */
export function AdminAccentStripe() {
  return <View style={styles.accentStripe} />;
}

/** Wraps full-screen error so admin routes keep the same chrome as scroll screens. */
export function AdminErrorShell({ children }: { children: ReactNode }) {
  return (
    <View style={styles.errorShell}>
      <AdminAccentStripe />
      <View style={styles.errorShellInner}>{children}</View>
    </View>
  );
}

export function AdminHeader({
  eyebrow,
  title,
  subtitle,
  rightSlot,
}: {
  eyebrow: string;
  title?: string;
  subtitle?: string;
  rightSlot?: ReactNode;
}) {
  return (
    <View style={styles.adminHeader}>
      <View style={styles.adminHeaderText}>
        <Text style={styles.eyebrow}>{eyebrow}</Text>
        {title ? <Text style={styles.adminTitle}>{title}</Text> : null}
        {subtitle ? <Text style={styles.adminSubtitle}>{subtitle}</Text> : null}
      </View>
      {rightSlot ? <View style={styles.adminHeaderRight}>{rightSlot}</View> : null}
    </View>
  );
}

export function AdminSectionLabel({ children }: { children: string }) {
  return (
    <View style={styles.sectionLabelRow}>
      <View style={styles.sectionLabelRule} />
      <Text style={styles.sectionLabel}>{children}</Text>
    </View>
  );
}

export function AdminKpiStatCard({
  label,
  value,
  hint,
  variant = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  variant?: "default" | "emphasis";
}) {
  return (
    <View style={[styles.kpiCard, variant === "emphasis" && styles.kpiCardEmphasis]}>
      <Text style={styles.kpiLabel} numberOfLines={2}>
        {label}
      </Text>
      <Text style={styles.kpiValue} numberOfLines={1}>
        {value}
      </Text>
      {hint ? (
        <Text style={styles.kpiHint} numberOfLines={1}>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

export function AdminAttentionCard({
  icon,
  title,
  subtitle,
  count,
  onPress,
  tone = "neutral",
  disabled,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle?: string;
  count?: number;
  onPress?: () => void;
  tone?: "neutral" | "warning" | "danger";
  disabled?: boolean;
}) {
  const stripe =
    tone === "danger" ? colors.critical : tone === "warning" ? colors.warning : colors.primary;
  const inner = (
    <View style={[styles.attentionInner, { borderLeftColor: stripe }]}>
      <View style={[styles.attentionIcon, tone !== "neutral" && { backgroundColor: colors.warningSoft }]}>
        <Ionicons name={icon} size={22} color={tone === "danger" ? colors.critical : colors.primaryDark} />
      </View>
      <View style={styles.attentionBody}>
        <Text style={styles.attentionTitle}>{title}</Text>
        {subtitle ? <Text style={styles.attentionSub}>{subtitle}</Text> : null}
      </View>
      {count != null && count > 0 ? (
        <View style={styles.attentionCount}>
          <Text style={styles.attentionCountTxt}>{count > 99 ? "99+" : String(count)}</Text>
        </View>
      ) : null}
      {onPress && !disabled ? (
        <Ionicons name="chevron-forward" size={22} color={colors.textSubtle} />
      ) : null}
    </View>
  );

  if (onPress && !disabled) {
    return (
      <TouchableOpacity
        style={[styles.attentionWrap, disabled && styles.attentionDim]}
        onPress={onPress}
        activeOpacity={0.88}
        accessibilityRole="button"
      >
        {inner}
      </TouchableOpacity>
    );
  }

  return <View style={[styles.attentionWrap, disabled && styles.attentionDim]}>{inner}</View>;
}

export function AdminQueueClearCard({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <Card style={styles.clearCard}>
      <View style={styles.clearRow}>
        <Ionicons name="checkmark-circle" size={22} color={colors.success} />
        <View style={styles.clearText}>
          <Text style={styles.clearTitle}>{title}</Text>
          <Text style={styles.clearSub}>{subtitle}</Text>
        </View>
      </View>
    </Card>
  );
}

export function AdminSeverityBadge({ level, label }: { level: "critical" | "high" | "standard"; label: string }) {
  const bg =
    level === "critical" ? colors.errorSoft : level === "high" ? colors.warningSoft : colors.surfaceMuted;
  const fg = level === "critical" ? colors.critical : level === "high" ? colors.warning : colors.textSecondary;
  return (
    <View style={[styles.sevBadge, { backgroundColor: bg }]}>
      <Text style={[styles.sevBadgeTxt, { color: fg }]}>{label}</Text>
    </View>
  );
}

export function AdminDecisionCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <View style={styles.decisionCard}>
      <View style={styles.decisionStripe} />
      <View style={styles.decisionBody}>
        <Text style={styles.decisionTitle}>{title}</Text>
        {subtitle ? <Text style={styles.decisionSub}>{subtitle}</Text> : null}
        <View style={styles.decisionActions}>{children}</View>
      </View>
    </View>
  );
}

export function AdminMiniRow({
  title,
  meta,
  right,
  onPress,
}: {
  title: string;
  meta?: string;
  right?: string;
  onPress?: () => void;
}) {
  const body = (
    <View style={styles.miniRow}>
      <View style={styles.miniRowText}>
        <Text style={styles.miniTitle} numberOfLines={1}>
          {title}
        </Text>
        {meta ? (
          <Text style={styles.miniMeta} numberOfLines={1}>
            {meta}
          </Text>
        ) : null}
      </View>
      {right ? (
        <Text style={styles.miniRight} numberOfLines={1}>
          {right}
        </Text>
      ) : null}
      {onPress ? <Ionicons name="chevron-forward" size={18} color={colors.textSubtle} /> : null}
    </View>
  );

  if (onPress) {
    return (
      <TouchableOpacity onPress={onPress} activeOpacity={0.88} style={styles.miniRowWrap}>
        {body}
      </TouchableOpacity>
    );
  }

  return <View style={styles.miniRowWrap}>{body}</View>;
}

export function AdminScreenSection({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.screenSection, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  accentStripe: {
    height: 3,
    backgroundColor: colors.primaryDark,
    opacity: 0.85,
  },
  errorShell: { flex: 1, backgroundColor: colors.background },
  errorShellInner: { flex: 1 },
  adminHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: space.md,
    marginBottom: space.md,
  },
  adminHeaderText: { flex: 1, minWidth: 0 },
  adminHeaderRight: { paddingTop: 2 },
  eyebrow: {
    fontSize: font.xs,
    fontWeight: font.bold,
    color: colors.primary,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: space.xs,
  },
  adminTitle: {
    fontSize: font.xl,
    fontWeight: font.bold,
    color: colors.primaryDark,
    letterSpacing: -0.2,
  },
  adminSubtitle: {
    marginTop: space.xs,
    fontSize: font.sm,
    color: colors.textMuted,
    lineHeight: 20,
    maxWidth: 360,
  },
  sectionLabelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    marginTop: space.lg,
    marginBottom: space.sm,
  },
  sectionLabelRule: { width: 3, height: 14, borderRadius: 2, backgroundColor: colors.primary },
  sectionLabel: {
    fontSize: font.xs,
    fontWeight: font.bold,
    color: colors.textSecondary,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  kpiCard: {
    flex: 1,
    minWidth: 0,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.md,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow.soft,
  },
  kpiCardEmphasis: {
    borderColor: colors.primaryMuted,
    backgroundColor: colors.backgroundElevated,
  },
  kpiLabel: {
    fontSize: font.xs,
    fontWeight: font.bold,
    color: colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.4,
    marginBottom: space.xs,
  },
  kpiValue: {
    fontSize: font.xxl,
    fontWeight: font.bold,
    color: colors.primaryDark,
    letterSpacing: -0.5,
  },
  kpiHint: { marginTop: 4, fontSize: font.xs, color: colors.textSubtle, fontWeight: font.medium },
  attentionWrap: {
    marginBottom: space.sm,
    borderRadius: radius.lg,
    overflow: "hidden",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    ...shadow.card,
  },
  attentionDim: { opacity: 0.85 },
  attentionInner: {
    flexDirection: "row",
    alignItems: "center",
    padding: space.md,
    gap: space.md,
    borderLeftWidth: 4,
    borderLeftColor: colors.primary,
  },
  attentionIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  attentionBody: { flex: 1, minWidth: 0 },
  attentionTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.text },
  attentionSub: { marginTop: 4, fontSize: font.sm, color: colors.textMuted, lineHeight: 18 },
  attentionCount: {
    minWidth: 28,
    paddingHorizontal: space.sm,
    paddingVertical: 4,
    borderRadius: radius.full,
    backgroundColor: colors.primaryDark,
    alignItems: "center",
  },
  attentionCountTxt: { fontSize: font.sm, fontWeight: font.bold, color: "#fff" },
  clearCard: {
    marginBottom: space.sm,
    backgroundColor: colors.successSoft,
    borderColor: colors.success,
    borderWidth: 1,
  },
  clearRow: { flexDirection: "row", alignItems: "flex-start", gap: space.md },
  clearText: { flex: 1 },
  clearTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.text },
  clearSub: { marginTop: 4, fontSize: font.sm, color: colors.textSecondary, lineHeight: 18 },
  sevBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: space.sm,
    paddingVertical: 3,
    borderRadius: radius.sm,
  },
  sevBadgeTxt: { fontSize: font.xs, fontWeight: font.bold },
  decisionCard: {
    flexDirection: "row",
    borderRadius: radius.lg,
    overflow: "hidden",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    marginBottom: space.md,
    ...shadow.card,
  },
  decisionStripe: { width: 5, backgroundColor: colors.primary },
  decisionBody: { flex: 1, padding: space.lg },
  decisionTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.primaryDark },
  decisionSub: { marginTop: space.xs, fontSize: font.sm, color: colors.textMuted, lineHeight: 18 },
  decisionActions: { marginTop: space.md, gap: space.sm },
  miniRowWrap: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: space.sm,
    ...shadow.soft,
  },
  miniRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: space.sm,
    paddingHorizontal: space.md,
    gap: space.sm,
  },
  miniRowText: { flex: 1, minWidth: 0 },
  miniTitle: { fontSize: font.sm, fontWeight: font.bold, color: colors.text },
  miniMeta: { marginTop: 2, fontSize: font.xs, color: colors.textMuted },
  miniRight: { fontSize: font.sm, fontWeight: font.bold, color: colors.primary },
  screenSection: { marginBottom: space.xs },
});
