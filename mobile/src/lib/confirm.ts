import { Alert, Platform } from "react-native";

export function confirmAsync(
  title: string,
  message: string,
  options: { confirmLabel: string; cancelLabel: string; destructive?: boolean }
): Promise<boolean> {
  return new Promise((resolve) => {
    if (Platform.OS === "web") {
      const ok = typeof window !== "undefined" && window.confirm(`${title}\n\n${message}`);
      resolve(Boolean(ok));
      return;
    }
    Alert.alert(title, message, [
      { text: options.cancelLabel, style: "cancel", onPress: () => resolve(false) },
      {
        text: options.confirmLabel,
        style: options.destructive ? "destructive" : "default",
        onPress: () => resolve(true),
      },
    ]);
  });
}
