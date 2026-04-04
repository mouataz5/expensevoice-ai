import { useEffect, useRef } from "react";
import { View, Text, StyleSheet, Modal, Animated, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../theme/colors";
import { font, radius, shadow, space } from "../../theme/tokens";
import { PrimaryButton, SecondaryButton } from "./primitives";

type Props = {
  visible: boolean;
  title: string;
  subtitle?: string;
  primaryLabel: string;
  onPrimary: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
};

export function SuccessCelebration({
  visible,
  title,
  subtitle,
  primaryLabel,
  onPrimary,
  secondaryLabel,
  onSecondary,
  icon = "checkmark-circle",
}: Props) {
  const opacity = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(0.92)).current;

  useEffect(() => {
    if (!visible) return;
    opacity.setValue(0);
    scale.setValue(0.92);
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }),
      Animated.spring(scale, { toValue: 1, friction: 7, useNativeDriver: true }),
    ]).start();
  }, [visible, opacity, scale]);

  return (
    <Modal visible={visible} animationType="none" transparent onRequestClose={onPrimary}>
      <Pressable style={styles.backdrop} onPress={onPrimary}>
        <Animated.View style={[styles.cardWrap, { opacity, transform: [{ scale }] }]}>
          <Pressable onPress={(e) => e.stopPropagation()}>
            <View style={styles.card}>
              <View style={styles.iconCircle}>
                <Ionicons name={icon} size={48} color={colors.success} />
              </View>
              <Text style={styles.title}>{title}</Text>
              {subtitle ? <Text style={styles.sub}>{subtitle}</Text> : null}
              <PrimaryButton title={primaryLabel} onPress={onPrimary} icon="arrow-forward-outline" />
              {secondaryLabel && onSecondary ? (
                <SecondaryButton title={secondaryLabel} onPress={onSecondary} icon="home-outline" />
              ) : null}
            </View>
          </Pressable>
        </Animated.View>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: colors.overlay,
    justifyContent: "center",
    padding: space.lg,
  },
  cardWrap: { width: "100%", maxWidth: 400, alignSelf: "center" },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: space.xl,
    alignItems: "stretch",
    gap: space.md,
    ...shadow.card,
  },
  iconCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: colors.successSoft,
    alignSelf: "center",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.xs,
  },
  title: {
    fontSize: font.xl,
    fontWeight: font.bold,
    color: colors.primaryDark,
    textAlign: "center",
  },
  sub: { fontSize: font.md, color: colors.textSecondary, textAlign: "center", lineHeight: 22 },
});
