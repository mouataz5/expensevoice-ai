import { Image, Platform } from "react-native";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";
import * as FileSystem from "expo-file-system/legacy";
import { decode } from "jpeg-js";

export type ScanIssueKey =
  | "blurry"
  | "dark"
  | "bright"
  | "incomplete_frame"
  | "too_small"
  | "heavy_compression"
  | "hard_to_read";

export type ScanQualityLevel = "good" | "fair" | "poor";

export type ScanQualityResult = {
  level: ScanQualityLevel;
  issues: ScanIssueKey[];
  primaryIssue: ScanIssueKey | null;
  pixelsAnalyzed: boolean;
};

const MIN_EDGE_POOR = 520;
const MIN_EDGE_FAIR = 760;
const ASPECT_MIN_POOR = 0.4;
const ASPECT_MAX_POOR = 2.45;
const ASPECT_MIN_FAIR = 0.52;
const ASPECT_MAX_FAIR = 1.92;
const BYTES_PER_PIXEL_POOR = 0.14;
const BYTES_PER_PIXEL_FAIR = 0.28;
const MEAN_DARK_POOR = 54;
const MEAN_DARK_FAIR = 66;
const MEAN_BRIGHT_POOR = 234;
const MEAN_BRIGHT_FAIR = 226;
const LAP_VAR_POOR = 6;
const LAP_VAR_FAIR = 14;

const ISSUE_PRIORITY: ScanIssueKey[] = [
  "incomplete_frame",
  "too_small",
  "dark",
  "bright",
  "blurry",
  "heavy_compression",
  "hard_to_read",
];

function pickPrimary(issues: ScanIssueKey[]): ScanIssueKey | null {
  if (issues.length === 0) return null;
  for (const p of ISSUE_PRIORITY) {
    if (issues.includes(p)) return p;
  }
  return issues[0] ?? null;
}

function getImageSize(uri: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    Image.getSize(
      uri,
      (w, h) => resolve({ width: w, height: h }),
      (e) => reject(e ?? new Error("getSize failed"))
    );
  });
}

function base64ToUint8Array(b64: string): Uint8Array {
  const binaryString = typeof atob === "function" ? atob(b64) : "";
  const len = binaryString.length;
  const out = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    out[i] = binaryString.charCodeAt(i);
  }
  return out;
}

function meanLuminanceAndLapVar(
  rgba: Uint8Array,
  w: number,
  h: number
): { mean: number; lapVar: number } {
  const stride = 2;
  let sum = 0;
  let n = 0;
  for (let y = 0; y < h; y += stride) {
    for (let x = 0; x < w; x += stride) {
      const i = (y * w + x) * 4;
      const g = 0.299 * rgba[i] + 0.587 * rgba[i + 1] + 0.114 * rgba[i + 2];
      sum += g;
      n++;
    }
  }
  const mean = n > 0 ? sum / n : 128;

  const gray: number[] = [];
  const gw = Math.ceil(w / stride);
  const gh = Math.ceil(h / stride);
  for (let gy = 0; gy < gh; gy++) {
    for (let gx = 0; gx < gw; gx++) {
      const x = Math.min(gx * stride, w - 1);
      const y = Math.min(gy * stride, h - 1);
      const i = (y * w + x) * 4;
      gray.push(0.299 * rgba[i] + 0.587 * rgba[i + 1] + 0.114 * rgba[i + 2]);
    }
  }

  const vals: number[] = [];
  for (let gy = 1; gy < gh - 1; gy++) {
    for (let gx = 1; gx < gw - 1; gx++) {
      const i = gy * gw + gx;
      const L = -gray[i - gw] - gray[i - 1] + 4 * gray[i] - gray[i + 1] - gray[i + gw];
      vals.push(L);
    }
  }
  if (vals.length === 0) return { mean, lapVar: 20 };
  let m = 0;
  for (const v of vals) m += v;
  m /= vals.length;
  let vsum = 0;
  for (const v of vals) vsum += (v - m) * (v - m);
  const lapVar = vsum / vals.length;
  return { mean, lapVar };
}

export async function analyzeScanImageQuality(uri: string): Promise<ScanQualityResult> {
  if (Platform.OS === "web") {
    return { level: "good", issues: [], primaryIssue: null, pixelsAnalyzed: false };
  }

  let width = 0;
  let height = 0;
  try {
    const dim = await getImageSize(uri);
    width = dim.width;
    height = dim.height;
  } catch {
    return { level: "fair", issues: ["hard_to_read"], primaryIssue: "hard_to_read", pixelsAnalyzed: false };
  }

  let fileBytes: number | null = null;
  try {
    const info = await FileSystem.getInfoAsync(uri);
    if (info.exists && typeof info.size === "number") fileBytes = info.size;
  } catch {
    /* ignore */
  }

  const minE = Math.min(width, height);
  const maxE = Math.max(width, height);
  const aspect = minE > 0 ? maxE / minE : 1;
  const pixels = width * height;
  const bpp = fileBytes != null && pixels > 0 ? fileBytes / pixels : null;

  let pixelsAnalyzed = false;
  let mean = 128;
  let lapVar = 18;

  try {
    const manipulated = await manipulateAsync(
      uri,
      [{ resize: { width: 280 } }],
      { compress: 0.82, format: SaveFormat.JPEG, base64: true }
    );
    if (manipulated.base64) {
      const raw = base64ToUint8Array(manipulated.base64);
      const decoded = decode(raw, { useTArray: true, formatAsRGBA: true });
      if (decoded.data && decoded.width > 4 && decoded.height > 4) {
        const m = meanLuminanceAndLapVar(decoded.data, decoded.width, decoded.height);
        mean = m.mean;
        lapVar = m.lapVar;
        pixelsAnalyzed = true;
      }
    }
  } catch {
    /* keep defaults */
  }

  const poor = new Set<ScanIssueKey>();
  const fair = new Set<ScanIssueKey>();

  if (minE < MIN_EDGE_POOR) poor.add("too_small");
  else if (minE < MIN_EDGE_FAIR) fair.add("hard_to_read");

  if (aspect < ASPECT_MIN_POOR || aspect > ASPECT_MAX_POOR) poor.add("incomplete_frame");
  else if (aspect < ASPECT_MIN_FAIR || aspect > ASPECT_MAX_FAIR) fair.add("incomplete_frame");

  if (bpp != null) {
    if (bpp < BYTES_PER_PIXEL_POOR) poor.add("heavy_compression");
    else if (bpp < BYTES_PER_PIXEL_FAIR) fair.add("heavy_compression");
  }

  if (pixelsAnalyzed) {
    if (mean < MEAN_DARK_POOR) poor.add("dark");
    else if (mean < MEAN_DARK_FAIR) fair.add("dark");

    if (mean > MEAN_BRIGHT_POOR) poor.add("bright");
    else if (mean > MEAN_BRIGHT_FAIR) fair.add("bright");

    if (lapVar < LAP_VAR_POOR) poor.add("blurry");
    else if (lapVar < LAP_VAR_FAIR) fair.add("blurry");
  }

  let level: ScanQualityLevel;
  if (poor.size > 0) level = "poor";
  else if (fair.size > 0) level = "fair";
  else level = "good";

  const issues: ScanIssueKey[] = [];
  const addSet = (s: Set<ScanIssueKey>) => {
    s.forEach((k) => {
      if (!issues.includes(k)) issues.push(k);
    });
  };
  if (level === "poor") {
    addSet(poor);
    addSet(fair);
  } else if (level === "fair") {
    addSet(fair);
  }

  const primaryIssue = level === "good" ? null : pickPrimary(issues);

  return { level, issues, primaryIssue, pixelsAnalyzed };
}
