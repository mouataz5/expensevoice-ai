import { useCallback, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  type ViewStyle,
} from "react-native";
import {
  useAudioRecorder,
  useAudioRecorderState,
  RecordingPresets,
  AudioModule,
  setAudioModeAsync,
} from "expo-audio";
import { colors } from "../theme/colors";

export type VoiceRecorderProps = {
  /** Bloque démarrage (ex. upload en cours) */
  busy?: boolean;
  /** Libellés / accessibilité */
  labels: {
    record: string;
    stop: string;
    micDenied: string;
    recordError: string;
  };
  /** Fichier prêt après stop (file://…) */
  onRecordingReady: (uri: string) => void;
  onError?: (message: string) => void;
  /** Style du conteneur boutons */
  style?: ViewStyle;
};

/**
 * Micro start/stop + préparation session iOS (expo-audio).
 * Le parent envoie l’URI vers speechApi ou purchases.
 */
export function VoiceRecorder({
  busy = false,
  labels,
  onRecordingReady,
  onError,
  style,
}: VoiceRecorderProps) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder, 250);
  const isRecording = recorderState.isRecording;
  const [starting, setStarting] = useState(false);

  const start = useCallback(async () => {
    try {
      setStarting(true);
      const status = await AudioModule.requestRecordingPermissionsAsync();
      if (!status.granted) {
        onError?.(labels.micDenied);
        return;
      }
      await setAudioModeAsync({
        allowsRecording: true,
        playsInSilentMode: true,
        interruptionMode: "doNotMix",
      });
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch (e) {
      onError?.(e instanceof Error ? e.message : labels.recordError);
    } finally {
      setStarting(false);
    }
  }, [labels.micDenied, labels.recordError, onError, recorder]);

  const stop = useCallback(async () => {
    try {
      await recorder.stop();
      const uri = recorder.uri ?? recorder.getStatus().url;
      if (!uri) {
        onError?.(labels.recordError);
        return;
      }
      onRecordingReady(uri);
    } catch (e) {
      onError?.(e instanceof Error ? e.message : labels.recordError);
    } finally {
      try {
        await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      } catch {
        /* ignore */
      }
    }
  }, [labels.recordError, onError, onRecordingReady, recorder]);

  const disabled = busy || starting;

  return (
    <View style={[styles.wrap, style]}>
      {!isRecording ? (
        <TouchableOpacity
          style={[styles.btn, styles.recordBtn, disabled && styles.btnDisabled]}
          onPress={start}
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel={labels.record}
        >
          {starting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.btnText}>{labels.record}</Text>
          )}
        </TouchableOpacity>
      ) : (
        <TouchableOpacity
          style={[styles.btn, styles.stopBtn]}
          onPress={stop}
          accessibilityRole="button"
          accessibilityLabel={labels.stop}
        >
          <View style={styles.recordingDot} />
          <Text style={styles.btnText}>{labels.stop}</Text>
        </TouchableOpacity>
      )}
      {isRecording && (
        <Text style={styles.hint}>{labels.stop}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: "center", gap: 8 },
  btn: {
    minWidth: 200,
    paddingVertical: 18,
    paddingHorizontal: 24,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 10,
  },
  recordBtn: { backgroundColor: colors.accent },
  stopBtn: { backgroundColor: colors.error },
  btnDisabled: { opacity: 0.55 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  recordingDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#fff",
  },
  hint: { fontSize: 13, color: colors.textMuted },
});
