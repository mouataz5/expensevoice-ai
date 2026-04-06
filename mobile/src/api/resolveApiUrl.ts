import Constants from "expo-constants";
import { Platform } from "react-native";

import { APP_ENV } from "../config/env";

const DEFAULT_BACKEND_PORT = 8000;

function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

function isLoopbackHost(host: string): boolean {
  const h = host.trim().toLowerCase();
  return h === "localhost" || h === "127.0.0.1" || h === "::1" || h === "[::1]";
}

/**
 * URL de base du backend (sans `/api`, sans slash final).
 *
 * **Production / preview** : définir `EXPO_PUBLIC_API_URL` (obligatoire pour appareils réels).
 * Exemples :
 * - `https://xxxx.ngrok-free.app` (tunnel HTTPS)
 * - `https://api.votredomaine.com`
 *
 * **Développement** :
 * - Si `EXPO_PUBLIC_API_URL` est défini → utilisé tel quel (LAN, ngrok, etc.).
 * - Sinon, l’IP est déduite depuis Metro (`expo start --lan`) : même sous-réseau Wi‑Fi que le téléphone.
 * - Émulateur Android : `10.0.2.2` mappe vers le localhost de la machine hôte (Docker sur le PC).
 * - Simulateur iOS / web local : `localhost`.
 *
 * Ne jamais supposer qu’un téléphone physique peut joindre `localhost` : c’est l’IP du *téléphone*,
 * pas celle du PC qui héberge Docker.
 */
export function getApiBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (fromEnv) {
    return stripTrailingSlash(fromEnv);
  }

  if (!__DEV__) {
    console.warn(
      "[api] EXPO_PUBLIC_API_URL is not set. Release/preview builds need it (HTTPS ou URL LAN). " +
        "See mobile/.env.example."
    );
    return "";
  }

  const hostUri = Constants.expoConfig?.hostUri;
  const host = hostUri?.split(":")[0]?.trim();

  if (host && !isLoopbackHost(host)) {
    const url = `http://${host}:${DEFAULT_BACKEND_PORT}`;
    if (__DEV__) {
      console.log(`[api] Dev fallback: Metro host "${host}" → ${url} (set EXPO_PUBLIC_API_URL to override)`);
    }
    return url;
  }

  if (Platform.OS === "android") {
    const url = `http://10.0.2.2:${DEFAULT_BACKEND_PORT}`;
    if (__DEV__) {
      console.log(
        `[api] Dev Android emulator fallback → ${url} (physical device: use EXPO_PUBLIC_API_URL=http://<LAN_IP>:8000)`
      );
    }
    return url;
  }

  const url = `http://localhost:${DEFAULT_BACKEND_PORT}`;
  if (__DEV__) {
    console.log(
      `[api] Dev iOS simulator / web fallback → ${url} (Expo Go on real device: run "npx expo start --lan" or set EXPO_PUBLIC_API_URL)`
    );
  }
  return url;
}

/** @deprecated Utiliser `getApiBaseUrl` (alias historique). */
export const resolveApiOrigin = getApiBaseUrl;

/** Pour debug / journaux : libellé d’environnement. */
export function getApiConfigLabel(): string {
  return `env=${APP_ENV} EXPO_PUBLIC_API_URL=${process.env.EXPO_PUBLIC_API_URL ?? "(unset)"}`;
}
