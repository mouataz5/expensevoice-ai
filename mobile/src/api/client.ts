import axios, { AxiosError } from "axios";
import { getStoredToken, clearStoredToken } from "../lib/secure-store";
import { notifyApiReachable, notifyApiUnreachable } from "../lib/networkStatus";
import { resolveApiOrigin } from "./resolveApiUrl";

const apiOrigin = resolveApiOrigin();
if (__DEV__) {
  // Aide au diagnostic : même base que le backend Docker (:8000)
  console.log(`[api] EXPO_PUBLIC_API_URL=${process.env.EXPO_PUBLIC_API_URL ?? "(auto)"} → ${apiOrigin}`);
}

const baseURL = `${apiOrigin.replace(/\/?$/, "")}/api/v1`;

export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
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

/** On 401, clear token so auth context redirects to login. Track reachability for offline UX. */
api.interceptors.response.use(
  (res) => {
    notifyApiReachable();
    return res;
  },
  async (err: AxiosError) => {
    if (err.response == null) {
      notifyApiUnreachable();
    } else {
      notifyApiReachable();
    }
    if (err.response?.status === 401) {
      pendingToken = null;
      await clearStoredToken();
    }
    return Promise.reject(err);
  }
);

export { baseURL };
