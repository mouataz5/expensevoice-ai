import { api } from "./client";

const AUDIO_MIME: Record<string, string> = {
  ".m4a": "audio/mp4",
  ".mp4": "audio/mp4",
  ".caf": "audio/x-caf",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".ogg": "audio/ogg",
  ".webm": "audio/webm",
  ".aac": "audio/aac",
};

export type TranscribeApiResult = {
  success: boolean;
  text: string;
  language: string;
  confidence?: number | null;
};

export type ParseInvoiceVoiceResult = {
  success: boolean;
  transcription: {
    text: string;
    language?: string | null;
    confidence?: number | null;
    duration_sec?: number | null;
  };
  invoice: Record<string, unknown>;
};

function audioFormData(audioUri: string): FormData {
  const formData = new FormData();
  const filename = audioUri.split("/").pop() || "recording.m4a";
  const ext = filename.includes(".") ? filename.slice(filename.lastIndexOf(".")).toLowerCase() : ".m4a";
  const mime = AUDIO_MIME[ext] ?? "audio/mp4";
  formData.append("audio", {
    uri: audioUri,
    type: mime,
    name: filename,
  } as unknown as Blob);
  return formData;
}

/** POST /speech/transcribe — Whisper seul. `language`: auto | ar | fr | en | omit */
export async function transcribeSpeech(
  audioUri: string,
  options?: { language?: string }
): Promise<TranscribeApiResult> {
  const formData = audioFormData(audioUri);
  if (options?.language) {
    formData.append("language", options.language);
  }
  const { data } = await api.post<TranscribeApiResult>("/speech/transcribe", formData, {
    timeout: 180000,
  });
  return data;
}

/** POST /speech/parse-invoice — Whisper + pipeline facture Groq */
export async function parseInvoiceFromSpeech(
  audioUri: string,
  transactionType: "sell" | "buy",
  options?: { language?: string; debug?: boolean }
): Promise<ParseInvoiceVoiceResult> {
  const formData = audioFormData(audioUri);
  formData.append("transaction_type", transactionType);
  if (options?.language) {
    formData.append("language", options.language);
  }
  formData.append("debug", options?.debug ? "true" : "false");
  const { data } = await api.post<ParseInvoiceVoiceResult>("/speech/parse-invoice", formData, {
    timeout: 180000,
  });
  return data;
}
