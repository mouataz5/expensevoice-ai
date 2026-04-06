import axios, { AxiosError } from "axios";
import { Platform } from "react-native";
import { getApiBaseUrl, getApiConfigLabel } from "./resolveApiUrl";
import { getStoredToken, clearStoredToken } from "../lib/secure-store";

const DEFAULT_PORT = 8000;

const apiOrigin = getApiBaseUrl();
const effectiveOrigin =
  apiOrigin ||
  (__DEV__ ? `http://localhost:${DEFAULT_PORT}` : null);

if (!__DEV__ && !apiOrigin) {
  console.error(
    "[api] No EXPO_PUBLIC_API_URL — production/preview builds must define it (HTTPS, ngrok, or public API).",
    getApiConfigLabel()
  );
}

const baseURL = `${(effectiveOrigin ?? `http://127.0.0.1:9`).replace(/\/+$/, "")}/api/v1`;

if (__DEV__) {
  console.log(`[api] base ${baseURL} (${getApiConfigLabel()})`);
}

export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
  timeout: 10_000,
});

/** Token set right after login so the very next request (getMe) uses it before storage is read. */
let pendingToken: string | null = null;

export function setPendingToken(token: string | null): void {
  pendingToken = token;
}

/** Call this before each request to attach the latest token (async). */
api.interceptors.request.use(async (config) => {
  const token = pendingToken ?? (await getStoredToken());
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

/** On 401, clear token so auth context redirects to login. */
api.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    if (__DEV__) {
      console.warn("[api] request failed", {
        platform: Platform.OS,
        baseURL: api.defaults.baseURL,
        url: err.config?.url,
        method: err.config?.method,
        code: err.code,
        message: err.message,
        hasResponse: !!err.response,
        status: err.response?.status,
      });
    }
    if (err.response?.status === 401) {
      pendingToken = null;
      await clearStoredToken();
    }
    return Promise.reject(err);
  }
);

export { baseURL };
