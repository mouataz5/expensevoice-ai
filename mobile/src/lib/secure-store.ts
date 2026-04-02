import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "abes_access_token";

const isWeb = typeof Platform !== "undefined" && Platform.OS === "web";

export async function getStoredToken(): Promise<string | null> {
  if (isWeb && typeof localStorage !== "undefined") {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  }
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function setStoredToken(token: string): Promise<void> {
  if (isWeb && typeof localStorage !== "undefined") {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // ignore
    }
    return;
  }
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } catch {
    // ignore
  }
}

export async function clearStoredToken(): Promise<void> {
  if (isWeb && typeof localStorage !== "undefined") {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      // ignore
    }
    return;
  }
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    // ignore
  }
}
