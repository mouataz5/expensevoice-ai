import axios, { AxiosError } from "axios";
import { getStoredToken, clearStoredToken } from "../lib/secure-store";

const baseURL =
  (process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000").replace(/\/?$/, "") + "/api/v1";

export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

/** Call this before each request to attach the latest token (async). */
api.interceptors.request.use(async (config) => {
  const token = await getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** On 401, clear token so auth context redirects to login. */
api.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    if (err.response?.status === 401) {
      await clearStoredToken();
    }
    return Promise.reject(err);
  }
);

export { baseURL };
