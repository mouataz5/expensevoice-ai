import Constants from "expo-constants";
import { Platform } from "react-native";

/**
 * Dev: pointe vers le PC qui exécute Metro (Expo Go / dev client).
 * Sinon localhost (simulateur iOS / web sur la même machine).
 * Émulateur Android: 10.0.2.2 = localhost du PC hôte.
 */
export function resolveApiOrigin(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (fromEnv) {
    return fromEnv.replace(/\/?$/, "");
  }

  if (!__DEV__) {
    return "http://localhost:8000";
  }

  const hostUri = Constants.expoConfig?.hostUri;
  const host = hostUri?.split(":")[0];
  if (host && host !== "localhost" && host !== "127.0.0.1") {
    return `http://${host}:8000`;
  }

  if (Platform.OS === "android") {
    return "http://10.0.2.2:8000";
  }

  return "http://localhost:8000";
}
