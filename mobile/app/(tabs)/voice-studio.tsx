import { useEffect } from "react";
import { useRouter } from "expo-router";

export default function VoiceStudioRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/(tabs)/record");
  }, [router]);
  return null;
}
