import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Platform } from "react-native";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, space } from "../../src/theme/tokens";

export default function TabsLayout() {
  const { t } = useLocale();

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textSubtle,
        tabBarStyle: {
          backgroundColor: colors.tabBarBg,
          borderTopColor: colors.divider,
          borderTopWidth: 1,
          height: Platform.OS === "ios" ? 88 : 64,
          paddingBottom: Platform.OS === "ios" ? 28 : space.sm,
          paddingTop: space.sm,
        },
        tabBarLabelStyle: {
          fontSize: font.xs,
          fontWeight: font.semibold,
          marginTop: 2,
        },
        tabBarIconStyle: { marginTop: 4 },
        headerStyle: {
          backgroundColor: colors.primary,
        },
        headerTintColor: "#fff",
        headerTitleStyle: { fontWeight: font.bold, fontSize: font.lg },
        headerShadowVisible: false,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: t("home"),
          tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="record"
        options={{
          title: t("record"),
          tabBarIcon: ({ color, size }) => <Ionicons name="mic" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="scan"
        options={{
          title: t("scanInvoice"),
          tabBarIcon: ({ color, size }) => <Ionicons name="document-text" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="invoices"
        options={{
          title: t("myInvoices"),
          tabBarIcon: ({ color, size }) => <Ionicons name="receipt" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="purchases"
        options={{
          title: t("myPurchases"),
          tabBarIcon: ({ color, size }) => <Ionicons name="list" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: t("profile"),
          tabBarIcon: ({ color, size }) => <Ionicons name="person" size={size} color={color} />,
        }}
      />
      {/* Hidden screens (accessible via navigation, not in tab bar) */}
      <Tabs.Screen name="voice-studio" options={{ href: null }} />
      <Tabs.Screen name="alerts" options={{ href: null }} />
      <Tabs.Screen name="invoice/[id]" options={{ href: null }} />
      <Tabs.Screen name="purchases/[id]" options={{ href: null }} />
    </Tabs>
  );
}
