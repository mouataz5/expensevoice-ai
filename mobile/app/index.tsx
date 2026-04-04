import { useEffect, useState } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../src/context/AuthContext";
import { getOnboardingComplete } from "../src/lib/onboarding";
import { colors } from "../src/theme/colors";

export default function Index() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const router = useRouter();
  const [onboardingDone, setOnboardingDone] = useState<boolean | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      setOnboardingDone(null);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isLoading || !isAuthenticated) return;
    let alive = true;
    void getOnboardingComplete().then((done) => {
      if (alive) setOnboardingDone(done);
    });
    return () => {
      alive = false;
    };
  }, [isLoading, isAuthenticated]);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (onboardingDone === null) return;
    if (!onboardingDone) {
      router.replace("/onboarding");
      return;
    }
    const isDirector = user?.role === "director" || user?.role === "admin";
    router.replace(isDirector ? "/(tabs-director)" : "/(tabs)");
  }, [isAuthenticated, isLoading, onboardingDone, user?.role, router]);

  return (
    <View style={styles.centered}>
      <ActivityIndicator size="large" color={colors.primary} />
    </View>
  );
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background,
  },
});
