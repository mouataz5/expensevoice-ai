// Part 2.2: same base as api client (/api/v1)
const base =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "" : "http://localhost:8000");
const baseURL = `${base.replace(/\/?$/, "")}/api/v1`;

export async function downloadFile(urlPath: string, filename: string) {
  const token = localStorage.getItem("access_token");
  const url = urlPath.startsWith("http") ? urlPath : `${baseURL}${urlPath}`;
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!res.ok) throw new Error("download failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
