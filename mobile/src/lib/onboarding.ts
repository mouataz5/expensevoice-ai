import * as SecureStore from "expo-secure-store";

const KEY = "ev_onboarding_v1";

export async function getOnboardingComplete(): Promise<boolean> {
  try {
    const v = await SecureStore.getItemAsync(KEY);
    return v === "1";
  } catch {
    return true;
  }
}

export async function setOnboardingComplete(): Promise<void> {
  await SecureStore.setItemAsync(KEY, "1");
}
