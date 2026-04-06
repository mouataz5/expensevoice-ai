import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../theme/colors";
import { font, space } from "../../theme/tokens";
import { useNetwork } from "../../context/NetworkContext";

type Props = {
  message: string;
  actionLabel: string;
  onRetry: () => void;
};

export function OfflineBanner({ message, actionLabel, onRetry }: Props) {
  const { showOfflineBanner } = useNetwork();
  const insets = useSafeAreaInsets();

  if (!showOfflineBanner) return null;

  return (
    <View style={[styles.wrap, { paddingTop: Math.max(insets.top, space.sm) }]}>
      <View style={styles.row}>
        <Ionicons name="cloud-offline-outline" size={20} color="#fff" style={styles.icon} />
        <Text style={styles.txt}>{message}</Text>
      </View>
      <TouchableOpacity onPress={onRetry} style={styles.btn} accessibilityRole="button" accessibilityLabel={actionLabel}>
        <Text style={styles.btnTxt}>{actionLabel}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.primaryDark,
    paddingHorizontal: space.md,
    paddingBottom: space.sm,
    gap: space.sm,
  },
  row: { flexDirection: "row", alignItems: "center", gap: space.sm },
  icon: { marginTop: 1 },
  txt: { flex: 1, color: "#F8FAFC", fontSize: font.sm, lineHeight: 20, fontWeight: font.medium },
  btn: {
    alignSelf: "flex-start",
    backgroundColor: "rgba(255,255,255,0.2)",
    paddingHorizontal: space.md,
    paddingVertical: space.xs + 2,
    borderRadius: 8,
  },
  btnTxt: { color: "#fff", fontSize: font.sm, fontWeight: font.bold },
});
