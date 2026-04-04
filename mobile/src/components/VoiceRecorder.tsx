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
import { font, radius, shadow, space } from "../theme/tokens";

export type VoiceRecorderProps = {
  busy?: boolean;
  labels: {
    record: string;
    stop: string;
    micDenied: string;
    recordError: string;
  };
  onRecordingReady: (uri: string) => void;
  onError?: (message: string) => void;
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
          style={[styles.ringOuter, disabled && styles.ringDim]}
          onPress={start}
          disabled={disabled}
          activeOpacity={0.9}
          accessibilityRole="button"
          accessibilityLabel={labels.record}
        >
          <View style={styles.ringInner}>
            {starting ? (
              <ActivityIndicator color={colors.primary} size="large" />
            ) : (
              <View style={styles.micCore} />
            )}
          </View>
          <Text style={styles.caption}>{labels.record}</Text>
        </TouchableOpacity>
      ) : (
        <TouchableOpacity
          style={[styles.ringOuter, styles.ringRecording]}
          onPress={stop}
          activeOpacity={0.9}
          accessibilityRole="button"
          accessibilityLabel={labels.stop}
        >
          <View style={styles.ringInnerRec}>
            <View style={styles.stopSquare} />
          </View>
          <Text style={styles.captionRec}>{labels.stop}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: "center", gap: space.sm },
  ringOuter: {
    alignItems: "center",
    padding: space.md,
    borderRadius: radius.xxl,
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.primaryMuted,
    ...shadow.card,
  },
  ringDim: { opacity: 0.5 },
  ringRecording: {
    borderColor: colors.error,
    backgroundColor: colors.errorSoft,
  },
  ringInner: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 3,
    borderColor: colors.primary,
  },
  ringInnerRec: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.error,
    alignItems: "center",
    justifyContent: "center",
  },
  micCore: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  stopSquare: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: "#fff",
  },
  caption: {
    marginTop: space.sm,
    fontSize: font.sm,
    fontWeight: font.bold,
    color: colors.primaryDark,
    textAlign: "center",
  },
  captionRec: {
    marginTop: space.sm,
    fontSize: font.sm,
    fontWeight: font.bold,
    color: colors.error,
    textAlign: "center",
  },
});
