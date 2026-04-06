/**
 * Environnement d’exécution (dev | prod) pour logs et comportements optionnels.
 *
 * Définir dans `.env` : EXPO_PUBLIC_APP_ENV=production pour forcer le mode prod en local si besoin.
 */
export type AppRuntimeEnv = "dev" | "prod";

export function getAppEnv(): AppRuntimeEnv {
  const raw = process.env.EXPO_PUBLIC_APP_ENV?.trim().toLowerCase();
  if (raw === "production" || raw === "prod") return "prod";
  if (raw === "development" || raw === "dev") return "dev";
  return __DEV__ ? "dev" : "prod";
}

export const APP_ENV = getAppEnv();
export const IS_DEV = __DEV__;
