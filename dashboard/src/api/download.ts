const baseURL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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
