import { Stack } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Toast from "react-native-toast-message";
import { AuthProvider } from "../src/context/AuthContext";
import { LocaleProvider } from "../src/context/LocaleContext";
import { NetworkProvider } from "../src/context/NetworkContext";
import { RootChrome } from "../src/components/RootChrome";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 60 * 1000 },
  },
});

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <NetworkProvider>
          <AuthProvider>
            <RootChrome>
              <Stack screenOptions={{ headerShown: false }}>
                <Stack.Screen name="index" />
                <Stack.Screen name="onboarding" />
                <Stack.Screen name="login" />
                <Stack.Screen name="register" />
                <Stack.Screen name="success" />
                <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
                <Stack.Screen name="(tabs-director)" options={{ headerShown: false }} />
              </Stack>
              <Toast />
            </RootChrome>
          </AuthProvider>
        </NetworkProvider>
      </LocaleProvider>
    </QueryClientProvider>
  );
}
