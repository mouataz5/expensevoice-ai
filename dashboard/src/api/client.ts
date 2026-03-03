import axios from "axios";

// Part 2.2: All API under /api/v1
const base =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "" : "http://localhost:8000");
const baseURL = `${base.replace(/\/?$/, "")}/api/v1`;

// Let axios set the appropriate Content-Type per request:
// - JSON: application/json
// - FormData: multipart/form-data with boundary
export const api = axios.create({
  baseURL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);
