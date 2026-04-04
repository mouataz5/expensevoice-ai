import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  Animated,
  type ViewStyle,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../theme/colors";
import { font, radius, shadow, space } from "../../theme/tokens";

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.sectionTitleWrap}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle ? <Text style={styles.sectionSubtitle}>{subtitle}</Text> : null}
    </View>
  );
}

export function PrimaryButton({
  title,
  onPress,
  loading,
  disabled,
  icon,
}: {
  title: string;
  onPress: () => void;
  loading?: boolean;
  /** Désactive le bouton (ex. choix requis avant action). */
  disabled?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
}) {
  const dim = Boolean(disabled || loading);
  return (
    <TouchableOpacity
      style={[styles.primaryBtn, dim && styles.primaryBtnDim]}
      onPress={onPress}
      disabled={dim}
      activeOpacity={0.88}
      accessibilityRole="button"
      accessibilityLabel={title}
    >
      {loading ? (
        <ActivityIndicator color="#fff" />
      ) : (
        <View style={styles.btnInner}>
          {icon ? <Ionicons name={icon} size={20} color="#fff" /> : null}
          <Text style={styles.primaryBtnText}>{title}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

export function SecondaryButton({
  title,
  onPress,
  disabled,
  icon,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
}) {
  return (
    <TouchableOpacity
      style={[styles.secondaryBtn, disabled && styles.secondaryBtnDim]}
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.88}
      accessibilityRole="button"
    >
      <View style={styles.btnInner}>
        {icon ? <Ionicons name={icon} size={18} color={colors.primary} /> : null}
        <Text style={styles.secondaryBtnText}>{title}</Text>
      </View>
    </TouchableOpacity>
  );
}

export function GhostButton({ title, onPress, disabled }: { title: string; onPress: () => void; disabled?: boolean }) {
  return (
    <TouchableOpacity onPress={onPress} disabled={disabled} style={styles.ghostBtn} accessibilityRole="button">
      <Text style={styles.ghostBtnText}>{title}</Text>
    </TouchableOpacity>
  );
}

/** Déconnexion / action sensible — contour discret, pas un CTA primaire. */
export function DestructiveOutlineButton({
  title,
  onPress,
  icon,
}: {
  title: string;
  onPress: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
}) {
  return (
    <TouchableOpacity style={styles.destructiveBtn} onPress={onPress} activeOpacity={0.88} accessibilityRole="button">
      <View style={styles.btnInner}>
        {icon ? <Ionicons name={icon} size={20} color={colors.error} /> : null}
        <Text style={styles.destructiveBtnText}>{title}</Text>
      </View>
    </TouchableOpacity>
  );
}

export function MetricCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <View style={styles.metricCard}>
      <Text style={styles.metricLabel} numberOfLines={2}>
        {label}
      </Text>
      <Text style={styles.metricValue} numberOfLines={1}>
        {value}
      </Text>
      {hint ? (
        <Text style={styles.metricHint} numberOfLines={1}>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

export function QuickActionTile({
  title,
  subtitle,
  icon,
  onPress,
}: {
  title: string;
  subtitle?: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity style={styles.quickTile} onPress={onPress} activeOpacity={0.9} accessibilityRole="button">
      <View style={styles.quickIconWrap}>
        <Ionicons name={icon} size={22} color={colors.primary} />
      </View>
      <View style={styles.quickTextWrap}>
        <Text style={styles.quickTitle}>{title}</Text>
        {subtitle ? <Text style={styles.quickSub}>{subtitle}</Text> : null}
      </View>
      <Ionicons name="chevron-forward" size={18} color={colors.textSubtle} />
    </TouchableOpacity>
  );
}

export function FormField({
  label,
  error,
  children,
}: {
  label?: string;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <View style={styles.formField}>
      {label ? <Text style={styles.formLabel}>{label}</Text> : null}
      {children}
      {error ? <Text style={styles.formError}>{error}</Text> : null}
    </View>
  );
}

export function TextFieldInput(props: React.ComponentProps<typeof TextInput>) {
  return <TextInput {...props} style={[styles.textInput, props.style]} placeholderTextColor={colors.textSubtle} />;
}

export function EmptyState({
  icon,
  title,
  subtitle,
  actionLabel,
  onAction,
  primaryCtaTitle,
  onPrimaryCta,
  secondaryCtaTitle,
  onSecondaryCta,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle?: string;
  /** Lien texte discret (ancien comportement). */
  actionLabel?: string;
  onAction?: () => void;
  /** CTA principal type bouton primaire. */
  primaryCtaTitle?: string;
  onPrimaryCta?: () => void;
  secondaryCtaTitle?: string;
  onSecondaryCta?: () => void;
}) {
  return (
    <View style={styles.emptyWrap}>
      <View style={styles.emptyIconCircle}>
        <Ionicons name={icon} size={40} color={colors.primary} />
      </View>
      <Text style={styles.emptyTitle}>{title}</Text>
      {subtitle ? <Text style={styles.emptySub}>{subtitle}</Text> : null}
      {primaryCtaTitle && onPrimaryCta ? (
        <View style={styles.emptyCtaBlock}>
          <PrimaryButton title={primaryCtaTitle} onPress={onPrimaryCta} />
        </View>
      ) : null}
      {secondaryCtaTitle && onSecondaryCta ? (
        <View style={styles.emptyCtaBlock}>
          <SecondaryButton title={secondaryCtaTitle} onPress={onSecondaryCta} />
        </View>
      ) : null}
      {actionLabel && onAction ? (
        <TouchableOpacity style={styles.emptyAction} onPress={onAction} accessibilityRole="button">
          <Text style={styles.emptyActionText}>{actionLabel}</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

export function LoadingState({ message }: { message?: string }) {
  return (
    <View style={styles.loadingWrap}>
      <ActivityIndicator size="large" color={colors.primary} />
      {message ? <Text style={styles.loadingMsg}>{message}</Text> : null}
    </View>
  );
}

export function ErrorState({
  title,
  message,
  hint,
  onRetry,
  retryLabel,
}: {
  title: string;
  message: string;
  /** Secondary guidance (e.g. check network, try again later). */
  hint?: string;
  onRetry?: () => void;
  retryLabel: string;
}) {
  return (
    <View style={styles.errorWrap}>
      <View style={styles.errorIconCircle}>
        <Ionicons name="cloud-offline-outline" size={36} color={colors.error} />
      </View>
      <Text style={styles.errorTitle}>{title}</Text>
      <Text style={styles.errorMsg}>{message}</Text>
      {hint ? <Text style={styles.errorHint}>{hint}</Text> : null}
      {onRetry ? <PrimaryButton title={retryLabel} onPress={onRetry} /> : null}
    </View>
  );
}

export function StepIndicator({ steps, activeIndex }: { steps: string[]; activeIndex: number }) {
  return (
    <View style={styles.stepsRow}>
      {steps.map((label, i) => {
        const done = i <= activeIndex;
        return (
          <View key={`step-${i}`} style={[styles.stepPill, done && styles.stepPillActive]}>
            <View style={[styles.stepNumDot, done && styles.stepNumDotActive]}>
              <Text style={[styles.stepNumTxt, done && styles.stepNumTxtActive]}>{i + 1}</Text>
            </View>
            <Text style={[styles.stepLabel, done && styles.stepLabelActive]} numberOfLines={2}>
              {label}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

export function SegmentedPair({
  left,
  right,
  value,
  onChange,
}: {
  left: { label: string; value: string };
  right: { label: string; value: string };
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <View style={styles.segWrap}>
      <TouchableOpacity
        style={[styles.segSide, value === left.value && styles.segSideOn]}
        onPress={() => onChange(left.value)}
        accessibilityRole="button"
        accessibilityState={{ selected: value === left.value }}
      >
        <Text style={[styles.segTxt, value === left.value && styles.segTxtOn]}>{left.label}</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.segSide, value === right.value && styles.segSideOn]}
        onPress={() => onChange(right.value)}
        accessibilityRole="button"
        accessibilityState={{ selected: value === right.value }}
      >
        <Text style={[styles.segTxt, value === right.value && styles.segTxtOn]}>{right.label}</Text>
      </TouchableOpacity>
    </View>
  );
}

export function LangChips({
  options,
  value,
  onChange,
}: {
  options: { key: string; label: string }[];
  value: string;
  onChange: (k: string) => void;
}) {
  return (
    <View style={styles.langChipsRow}>
      {options.map((o) => (
        <TouchableOpacity
          key={o.key}
          style={[styles.langChip, value === o.key && styles.langChipOn]}
          onPress={() => onChange(o.key)}
          accessibilityRole="button"
          accessibilityState={{ selected: value === o.key }}
        >
          <Text style={[styles.langChipTxt, value === o.key && styles.langChipTxtOn]}>{o.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

export function StatusPill({ label, tone }: { label: string; tone: "neutral" | "success" | "warning" | "danger" | "info" }) {
  const bg =
    tone === "success"
      ? colors.successSoft
      : tone === "warning"
        ? colors.warningSoft
        : tone === "danger"
          ? colors.errorSoft
          : tone === "info"
            ? colors.infoSoft
            : colors.surfaceMuted;
  const fg =
    tone === "success"
      ? colors.success
      : tone === "warning"
        ? colors.warning
        : tone === "danger"
          ? colors.error
          : tone === "info"
            ? colors.info
            : colors.textSecondary;
  return (
    <View style={[styles.pill, { backgroundColor: bg }]}>
      <Text style={[styles.pillTxt, { color: fg }]}>{label}</Text>
    </View>
  );
}

export function InfoBanner({
  variant,
  title,
  children,
}: {
  variant: "warning" | "error" | "success" | "info";
  title?: string;
  children: ReactNode;
}) {
  const map = {
    warning: { bg: colors.warningSoft, border: colors.warning, icon: "alert-circle" as const },
    error: { bg: colors.errorSoft, border: colors.error, icon: "close-circle" as const },
    success: { bg: colors.successSoft, border: colors.success, icon: "checkmark-circle" as const },
    info: { bg: colors.infoSoft, border: colors.info, icon: "information-circle" as const },
  };
  const m = map[variant];
  return (
    <View style={[styles.banner, { backgroundColor: m.bg, borderLeftColor: m.border }]}>
      <Ionicons name={m.icon} size={20} color={m.border} style={styles.bannerIcon} />
      <View style={styles.bannerBody}>
        {title ? <Text style={styles.bannerTitle}>{title}</Text> : null}
        <Text style={styles.bannerText}>{children}</Text>
      </View>
    </View>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <View style={styles.confWrap}>
      <View style={styles.confTrack}>
        <View style={[styles.confFill, { width: `${pct}%` }]} />
      </View>
      <Text style={styles.confLabel}>{pct}%</Text>
    </View>
  );
}

export function ScreenScroll({
  children,
  contentStyle,
}: {
  children: ReactNode;
  contentStyle?: ViewStyle;
}) {
  return (
    <ScrollView
      style={styles.screenScroll}
      contentContainerStyle={[styles.screenContent, contentStyle]}
      showsVerticalScrollIndicator={false}
    >
      {children}
    </ScrollView>
  );
}

/** Barre animée type “shimmer” léger pour listes en chargement. */
export function SkeletonBox({
  width,
  height,
  style,
  radius: r = radius.md,
}: {
  width: number | `${number}%`;
  height: number;
  style?: ViewStyle;
  radius?: number;
}) {
  const opacity = useRef(new Animated.Value(0.35)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.85, duration: 650, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.35, duration: 650, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);
  return (
    <Animated.View
      style={[
        {
          width,
          height,
          borderRadius: r,
          backgroundColor: colors.surfaceDark,
          opacity,
        },
        style,
      ]}
    />
  );
}

export function InvoiceRowSkeleton() {
  return (
    <View style={styles.skeletonRowCard}>
      <SkeletonBox width="70%" height={16} style={{ marginBottom: space.sm }} />
      <SkeletonBox width="40%" height={12} style={{ marginBottom: space.md }} />
      <View style={styles.skeletonRowFooter}>
        <SkeletonBox width={88} height={22} radius={radius.full} />
        <SkeletonBox width={100} height={18} />
      </View>
      <SkeletonBox width="50%" height={11} style={{ marginTop: space.sm }} />
    </View>
  );
}

export function InvoiceListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <View style={styles.skeletonList} accessibilityLabel="Loading">
      {Array.from({ length: count }, (_, i) => (
        <InvoiceRowSkeleton key={i} />
      ))}
    </View>
  );
}

export function AlertRowSkeleton() {
  return (
    <View style={styles.skeletonRowCard}>
      <SkeletonBox width="45%" height={14} style={{ marginBottom: space.sm }} />
      <SkeletonBox width="100%" height={40} style={{ marginBottom: space.md }} />
      <View style={styles.skeletonRowFooter}>
        <SkeletonBox width={100} height={30} radius={radius.md} />
        <SkeletonBox width={120} height={30} radius={radius.md} />
      </View>
    </View>
  );
}

export function AlertListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <View style={styles.skeletonList} accessibilityLabel="Loading">
      {Array.from({ length: count }, (_, i) => (
        <AlertRowSkeleton key={i} />
      ))}
    </View>
  );
}

export function HomeOverviewSkeleton() {
  return (
    <View style={styles.skeletonHome}>
      <SkeletonBox width="55%" height={22} style={{ marginBottom: space.md }} />
      <SkeletonBox width="90%" height={14} style={{ marginBottom: space.xl }} />
      <View style={styles.skeletonKpiRow}>
        <SkeletonBox width="31%" height={72} />
        <SkeletonBox width="31%" height={72} />
        <SkeletonBox width="31%" height={72} />
      </View>
    </View>
  );
}

/** Grille 2×2 pour tableau de bord directeur. */
export function DirectorKpiSkeleton() {
  return (
    <View style={styles.skeletonDirectorKpi}>
      <View style={styles.skeletonKpiRow}>
        <View style={styles.skeletonKpiHalf}>
          <SkeletonBox width="100%" height={88} />
        </View>
        <View style={styles.skeletonKpiHalf}>
          <SkeletonBox width="100%" height={88} />
        </View>
      </View>
      <View style={styles.skeletonKpiRow}>
        <View style={styles.skeletonKpiHalf}>
          <SkeletonBox width="100%" height={88} />
        </View>
        <View style={styles.skeletonKpiHalf}>
          <SkeletonBox width="100%" height={88} />
        </View>
      </View>
    </View>
  );
}

export function UsersListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <View style={styles.skeletonList} accessibilityLabel="Loading">
      {Array.from({ length: count }, (_, i) => (
        <View key={i} style={styles.skeletonRowCard}>
          <SkeletonBox width="78%" height={16} style={{ marginBottom: space.sm }} />
          <SkeletonBox width="32%" height={13} style={{ marginBottom: space.md }} />
          <SkeletonBox width="100%" height={36} radius={radius.md} />
        </View>
      ))}
    </View>
  );
}

export function PolicyCardsSkeleton() {
  return (
    <View style={{ gap: space.md, marginTop: space.md }}>
      <View style={styles.skeletonRowCard}>
        <SkeletonBox width="40%" height={16} style={{ marginBottom: space.md }} />
        <SkeletonBox width="90%" height={14} style={{ marginBottom: space.sm }} />
        <SkeletonBox width="70%" height={14} />
      </View>
      <View style={styles.skeletonRowCard}>
        <SkeletonBox width="45%" height={16} style={{ marginBottom: space.md }} />
        <SkeletonBox width="100%" height={48} />
      </View>
    </View>
  );
}

export function AuditListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <View style={styles.skeletonList}>
      {Array.from({ length: count }, (_, i) => (
        <View key={i} style={styles.skeletonRowCard}>
          <SkeletonBox width="50%" height={15} style={{ marginBottom: space.sm }} />
          <SkeletonBox width="100%" height={12} style={{ marginBottom: space.xs }} />
          <SkeletonBox width="85%" height={14} />
        </View>
      ))}
    </View>
  );
}

/** Mimics `AdminAttentionCard` layout (dashboard “à traiter”). */
export function AdminAttentionCardSkeleton() {
  return (
    <View style={[styles.skeletonRowCard, styles.skeletonAttentionCard]}>
      <View style={styles.skeletonAttentionRow}>
        <SkeletonBox width={44} height={44} radius={radius.md} />
        <View style={styles.skeletonAttentionBody}>
          <SkeletonBox width="68%" height={16} style={{ marginBottom: space.sm }} />
          <SkeletonBox width="92%" height={12} />
        </View>
        <SkeletonBox width={28} height={22} radius={radius.full} />
      </View>
    </View>
  );
}

export function AdminAttentionPairSkeleton() {
  return (
    <View style={styles.skeletonAttentionPair} accessibilityLabel="Loading">
      <AdminAttentionCardSkeleton />
      <AdminAttentionCardSkeleton />
    </View>
  );
}

/** Mimics `AdminMiniRow` (dernières factures dashboard). */
export function AdminMiniRowsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <View style={styles.skeletonMiniRowsWrap} accessibilityLabel="Loading">
      {Array.from({ length: count }, (_, i) => (
        <View key={i} style={[styles.skeletonRowCard, styles.skeletonMiniRow]}>
          <View style={styles.skeletonMiniRowInner}>
            <View style={{ flex: 1, marginRight: space.md }}>
              <SkeletonBox width="72%" height={14} style={{ marginBottom: space.xs }} />
              <SkeletonBox width="48%" height={11} />
            </View>
            <SkeletonBox width={76} height={14} />
          </View>
        </View>
      ))}
    </View>
  );
}

/** Chargement du bloc paramètres organisation (directeur). */
export function AdminSettingsFormSkeleton() {
  return (
    <View style={styles.skeletonSettingsForm} accessibilityLabel="Loading">
      <Card>
        {[0, 1, 2, 3].map((i) => (
          <View key={i} style={styles.skeletonSettingsField}>
            <SkeletonBox width="38%" height={11} style={{ marginBottom: space.xs }} />
            <SkeletonBox width="100%" height={48} radius={radius.lg} />
          </View>
        ))}
        <SkeletonBox width="100%" height={52} radius={radius.md} style={{ marginTop: space.sm }} />
      </Card>
    </View>
  );
}

/** Repère visuel produit (coherent avec login). */
export function ProductBrandMark({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.brandMarkRow}>
      <View style={styles.brandMarkCircle}>
        <Text style={styles.brandMarkLetter}>A</Text>
      </View>
      <View style={styles.brandMarkTextCol}>
        <Text style={styles.brandMarkName}>{title}</Text>
        {subtitle ? <Text style={styles.brandMarkSub}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow.card,
  },
  sectionTitleWrap: { marginBottom: space.md },
  sectionTitle: {
    fontSize: font.lg,
    fontWeight: font.bold,
    color: colors.text,
    letterSpacing: -0.2,
  },
  sectionSubtitle: { fontSize: font.sm, color: colors.textMuted, marginTop: space.xxs },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: space.md,
    paddingHorizontal: space.lg,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 52,
  },
  primaryBtnDim: { opacity: 0.55 },
  primaryBtnText: { color: "#fff", fontSize: font.md, fontWeight: font.bold },
  btnInner: { flexDirection: "row", alignItems: "center", gap: space.sm },
  secondaryBtn: {
    borderRadius: radius.md,
    paddingVertical: space.md,
    paddingHorizontal: space.lg,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.primary,
    backgroundColor: colors.surface,
    minHeight: 50,
  },
  secondaryBtnDim: { opacity: 0.5 },
  secondaryBtnText: { color: colors.primary, fontSize: font.md, fontWeight: font.bold },
  ghostBtn: { paddingVertical: space.sm, alignItems: "center" },
  ghostBtnText: { color: colors.primary, fontSize: font.sm, fontWeight: font.semibold },
  destructiveBtn: {
    borderRadius: radius.md,
    paddingVertical: space.md,
    paddingHorizontal: space.lg,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.error,
    backgroundColor: colors.errorSoft,
    minHeight: 52,
  },
  destructiveBtnText: { color: colors.error, fontSize: font.md, fontWeight: font.bold },
  metricCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: space.md,
    borderWidth: 1,
    borderColor: colors.border,
    minWidth: 0,
    ...shadow.soft,
  },
  metricLabel: { fontSize: font.xs, color: colors.textMuted, fontWeight: font.semibold, marginBottom: space.xs },
  metricValue: { fontSize: font.xl, fontWeight: font.bold, color: colors.primary },
  metricHint: { fontSize: font.xs, color: colors.textSubtle, marginTop: space.xxs },
  quickTile: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.md,
    marginBottom: space.sm,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow.soft,
  },
  quickIconWrap: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginRight: space.md,
  },
  quickTextWrap: { flex: 1 },
  quickTitle: { fontSize: font.md, fontWeight: font.bold, color: colors.text },
  quickSub: { fontSize: font.sm, color: colors.textMuted, marginTop: 2 },
  formField: { marginBottom: space.md },
  formLabel: { fontSize: font.sm, fontWeight: font.semibold, color: colors.textSecondary, marginBottom: space.xs },
  formError: { fontSize: font.sm, color: colors.error, marginTop: space.xs },
  textInput: {
    borderWidth: 1.5,
    borderColor: colors.borderStrong,
    borderRadius: radius.md,
    paddingVertical: space.sm + 2,
    paddingHorizontal: space.md,
    fontSize: font.md,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  emptyWrap: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: space.xxxl,
    paddingHorizontal: space.xl,
  },
  emptyIconCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.lg,
  },
  emptyTitle: { fontSize: font.xl, fontWeight: font.bold, color: colors.text, textAlign: "center" },
  emptySub: {
    fontSize: font.md,
    color: colors.textMuted,
    textAlign: "center",
    marginTop: space.sm,
    lineHeight: 22,
    maxWidth: 300,
  },
  emptyCtaBlock: { marginTop: space.lg, width: "100%", maxWidth: 320, alignSelf: "center", gap: space.sm },
  emptyAction: { marginTop: space.lg, paddingVertical: space.sm, paddingHorizontal: space.lg },
  emptyActionText: { color: colors.primary, fontWeight: font.bold, fontSize: font.md },
  skeletonList: { padding: space.lg, gap: space.md },
  skeletonRowCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow.soft,
  },
  skeletonRowFooter: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  skeletonHome: { marginBottom: space.lg },
  skeletonKpiRow: { flexDirection: "row", gap: space.sm, justifyContent: "space-between" },
  skeletonDirectorKpi: { gap: space.sm, marginBottom: space.lg },
  skeletonKpiHalf: { flex: 1, minWidth: 0 },
  skeletonAttentionCard: {
    marginBottom: 0,
    borderLeftWidth: 4,
    borderLeftColor: colors.border,
  },
  skeletonAttentionRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  skeletonAttentionBody: { flex: 1, minWidth: 0 },
  skeletonAttentionPair: { gap: space.sm, marginBottom: space.sm },
  skeletonMiniRow: { paddingVertical: space.sm + 2 },
  skeletonMiniRowInner: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  skeletonMiniRowsWrap: { gap: space.sm, marginBottom: space.md },
  skeletonSettingsForm: { marginBottom: space.md },
  skeletonSettingsField: { marginBottom: space.md },
  brandMarkRow: { flexDirection: "row", alignItems: "center", gap: space.md, marginBottom: space.lg },
  brandMarkCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  brandMarkLetter: { color: "#fff", fontSize: font.lg, fontWeight: font.bold },
  brandMarkTextCol: { flex: 1 },
  brandMarkName: { fontSize: font.md, fontWeight: font.bold, color: colors.primaryDark },
  brandMarkSub: { fontSize: font.xs, color: colors.textMuted, marginTop: 2 },
  loadingWrap: { flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl },
  loadingMsg: { marginTop: space.md, fontSize: font.sm, color: colors.textMuted },
  errorWrap: { flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl },
  errorIconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.errorSoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.md,
  },
  errorTitle: { fontSize: font.xl, fontWeight: font.bold, color: colors.text, marginBottom: space.xs },
  errorMsg: { fontSize: font.sm, color: colors.textMuted, textAlign: "center", marginBottom: space.sm },
  errorHint: {
    fontSize: font.xs,
    color: colors.textSubtle,
    textAlign: "center",
    marginBottom: space.lg,
    lineHeight: 18,
    paddingHorizontal: space.md,
  },
  stepsRow: { flexDirection: "row", flexWrap: "wrap", gap: space.sm, marginBottom: space.lg },
  stepPill: {
    flexGrow: 1,
    minWidth: "30%",
    flexDirection: "row",
    alignItems: "center",
    gap: space.xs,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingVertical: space.sm,
    paddingHorizontal: space.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  stepPillActive: { borderColor: colors.primary, backgroundColor: colors.primaryMuted },
  stepNumDot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  stepNumDotActive: { backgroundColor: colors.primary },
  stepNumTxt: { fontSize: font.xs, fontWeight: font.bold, color: colors.textMuted },
  stepNumTxtActive: { color: "#fff" },
  stepLabel: { flex: 1, fontSize: font.xs, color: colors.textMuted, fontWeight: font.medium },
  stepLabelActive: { color: colors.primaryDark, fontWeight: font.bold },
  segWrap: {
    flexDirection: "row",
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    padding: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  segSide: {
    flex: 1,
    paddingVertical: space.sm + 2,
    alignItems: "center",
    borderRadius: radius.sm,
  },
  segSideOn: { backgroundColor: colors.primary },
  segTxt: { fontSize: font.md, fontWeight: font.semibold, color: colors.textSecondary },
  segTxtOn: { color: "#fff", fontWeight: font.bold },
  langChipsRow: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  langChip: {
    paddingVertical: space.sm,
    paddingHorizontal: space.md,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  langChipOn: { borderColor: colors.primary, backgroundColor: colors.primaryMuted },
  langChipTxt: { fontSize: font.sm, fontWeight: font.semibold, color: colors.textMuted },
  langChipTxtOn: { color: colors.primaryDark },
  pill: { alignSelf: "flex-start", paddingHorizontal: space.sm, paddingVertical: 4, borderRadius: radius.sm },
  pillTxt: { fontSize: font.xs, fontWeight: font.bold },
  banner: {
    flexDirection: "row",
    borderRadius: radius.md,
    padding: space.md,
    borderLeftWidth: 4,
    marginBottom: space.md,
  },
  bannerIcon: { marginRight: space.sm, marginTop: 2 },
  bannerBody: { flex: 1 },
  bannerTitle: { fontSize: font.sm, fontWeight: font.bold, color: colors.text, marginBottom: 4 },
  bannerText: { fontSize: font.sm, color: colors.textSecondary, lineHeight: 20 },
  confWrap: { flexDirection: "row", alignItems: "center", gap: space.sm, marginBottom: space.sm },
  confTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.surfaceMuted,
    overflow: "hidden",
  },
  confFill: { height: "100%", backgroundColor: colors.accent, borderRadius: 4 },
  confLabel: { fontSize: font.sm, fontWeight: font.bold, color: colors.primary, minWidth: 40 },
  screenScroll: { flex: 1, backgroundColor: colors.background },
  screenContent: { padding: space.lg, paddingBottom: space.xxxl },
});

export function invoiceStatusTone(status: string): "neutral" | "success" | "warning" | "danger" | "info" {
  switch (status) {
    case "approved":
      return "success";
    case "ready":
    case "ready_for_review":
      return "info";
    case "rejected":
    case "failed":
      return "danger";
    case "processing":
      return "warning";
    default:
      return "neutral";
  }
}
