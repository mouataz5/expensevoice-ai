import { useState, useMemo } from "react";
import { View, Text, StyleSheet, Image, type ViewStyle } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../theme/colors";
import { font } from "../../theme/tokens";
import { getUserInitials, normalizeUserRole } from "../../lib/userDisplay";

const SIZES = {
  sm: { outer: 36, font: font.sm, badge: 18, icon: 11 },
  md: { outer: 44, font: font.md, badge: 20, icon: 12 },
  lg: { outer: 56, font: font.lg, badge: 22, icon: 13 },
  xl: { outer: 88, font: font.xxl, badge: 24, icon: 14 },
} as const;

export type UserAvatarSize = keyof typeof SIZES;

type UserAvatarProps = {
  email?: string | null;
  /** Si fourni, prioritaire pour les initiales (ex. “Jean Dupont” → JD). */
  displayName?: string | null;
  imageUri?: string | null;
  size?: UserAvatarSize;
  /** Rôle métier pour le pastille (icône discrète). */
  role?: string | null;
  showRoleBadge?: boolean;
  style?: ViewStyle;
  /** Libellé accessibilité du cercle principal (ex. e-mail). */
  accessibilityLabel?: string;
  /** À false quand l’avatar est dans un bouton parent (évite le double focus vocal). */
  accessible?: boolean;
};

function roleBadgeStyle(r: "admin" | "director" | "employee"): { bg: string; icon: keyof typeof Ionicons.glyphMap; iconColor: string } {
  switch (r) {
    case "admin":
      return { bg: colors.primaryDark, icon: "shield-checkmark", iconColor: "#fff" };
    case "director":
      return { bg: colors.primary, icon: "briefcase-outline", iconColor: "#fff" };
    default:
      return {
        bg: colors.surfaceMuted,
        icon: "person-outline",
        iconColor: colors.primaryDark,
      };
  }
}

export function UserAvatar({
  email,
  displayName,
  imageUri,
  size = "md",
  role,
  showRoleBadge = false,
  style,
  accessibilityLabel,
  accessible = true,
}: UserAvatarProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const dim = SIZES[size];
  const initials = useMemo(() => getUserInitials(email, displayName), [email, displayName]);
  const normalizedRole = normalizeUserRole(role);
  const showImage = Boolean(imageUri?.trim()) && !imageFailed;

  const badge = normalizedRole && showRoleBadge ? roleBadgeStyle(normalizedRole) : null;

  return (
    <View
      style={[styles.wrap, { width: dim.outer, height: dim.outer }, style]}
      accessible={accessible}
      accessibilityRole={accessible ? "image" : undefined}
      accessibilityLabel={accessible ? accessibilityLabel ?? (initials ? `${initials}` : "User") : undefined}
    >
      <View
        style={[
          styles.circle,
          {
            width: dim.outer,
            height: dim.outer,
            borderRadius: dim.outer / 2,
          },
          showImage ? styles.circleImage : null,
        ]}
      >
        {showImage ? (
          <Image
            source={{ uri: imageUri!.trim() }}
            style={[styles.image, { width: dim.outer, height: dim.outer, borderRadius: dim.outer / 2 }]}
            onError={() => setImageFailed(true)}
            accessibilityIgnoresInvertColors
          />
        ) : (
          <Text style={[styles.initials, { fontSize: dim.font }]} numberOfLines={1}>
            {initials}
          </Text>
        )}
      </View>
      {badge ? (
        <View
          style={[
            styles.badge,
            {
              width: dim.badge,
              height: dim.badge,
              borderRadius: dim.badge / 2,
              backgroundColor: badge.bg,
              borderColor: colors.surface,
            },
            normalizedRole === "employee" && styles.badgeEmployee,
          ]}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        >
          <Ionicons name={badge.icon} size={dim.icon} color={badge.iconColor} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "relative",
  },
  circle: {
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.borderStrong,
  },
  circleImage: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
  },
  image: {
    resizeMode: "cover",
  },
  initials: {
    color: "#fff",
    fontWeight: font.bold,
    letterSpacing: 0.3,
  },
  badge: {
    position: "absolute",
    right: -2,
    bottom: -2,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
  },
  badgeEmployee: {
    borderWidth: 1.5,
    borderColor: colors.borderStrong,
  },
});
