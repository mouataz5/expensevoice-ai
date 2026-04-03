import { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Toast from "react-native-toast-message";
import { useLocale } from "../../../src/context/LocaleContext";
import { colors } from "../../../src/theme/colors";
import { queryKeys } from "../../../src/queryKeys";
import {
  getPurchase,
  fetchPurchaseAlerts,
  extractPurchase,
  confirmPurchase,
  type PurchaseAlertRow,
} from "../../../src/api/purchases";
import { fetchAllowedCategories } from "../../../src/api/categories-public";

function fmtTn(val: number): string {
  return new Intl.NumberFormat("fr-TN", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  }).format(val);
}

export default function PurchaseDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const purchaseId = typeof id === "string" ? id : id?.[0] ?? "";
  const { t } = useLocale();
  const router = useRouter();
  const qc = useQueryClient();

  const purchaseQ = useQuery({
    queryKey: queryKeys.purchaseDetail(purchaseId),
    queryFn: () => getPurchase(purchaseId),
    enabled: !!purchaseId,
    refetchInterval: (q) => (q.state.data?.processing_status === "processing" ? 2500 : false),
  });

  const alertsQ = useQuery({
    queryKey: queryKeys.purchaseAlerts(purchaseId),
    queryFn: () => fetchPurchaseAlerts(purchaseId),
    enabled: !!purchaseId,
  });

  const categoriesQ = useQuery({
    queryKey: queryKeys.allowedCategories,
    queryFn: fetchAllowedCategories,
  });

  const [form, setForm] = useState({
    product_name: "",
    category: "",
    quantity: "1",
    unit_price: "0",
  });

  useEffect(() => {
    const p = purchaseQ.data;
    if (!p) return;
    setForm({
      product_name: p.product_name ?? "",
      category: p.category ?? "",
      quantity: String(p.quantity ?? 1),
      unit_price: String(p.unit_price ?? 0),
    });
  }, [purchaseQ.data]);

  const quantityN = Number(form.quantity) || 0;
  const unitPriceN = Number(form.unit_price) || 0;
  const total = useMemo(() => quantityN * unitPriceN, [quantityN, unitPriceN]);

  const extractM = useMutation({
    mutationFn: () => extractPurchase(purchaseId),
    onSuccess: (data) => {
      const ex = data.extracted;
      setForm({
        product_name: String(ex.product_name ?? ""),
        category: String(ex.category ?? ""),
        quantity: String(ex.quantity ?? 1),
        unit_price: String(ex.unit_price ?? 0),
      });
      Toast.show({ type: "success", text1: t("reExtractDone") });
      void qc.invalidateQueries({ queryKey: queryKeys.purchaseDetail(purchaseId) });
    },
    onError: () => Toast.show({ type: "error", text1: t("error"), text2: t("reExtractFail") }),
  });

  const confirmM = useMutation({
    mutationFn: () =>
      confirmPurchase(purchaseId, {
        product_name: form.product_name,
        category: form.category || null,
        quantity: quantityN,
        unit_price: unitPriceN,
        total_amount: total,
      }),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("confirmDone") });
      void qc.invalidateQueries({ queryKey: queryKeys.purchaseDetail(purchaseId) });
      void qc.invalidateQueries({ queryKey: queryKeys.purchasesMe });
      void qc.invalidateQueries({ queryKey: queryKeys.purchaseAlerts(purchaseId) });
    },
    onError: () => Toast.show({ type: "error", text1: t("error"), text2: t("confirmFail") }),
  });

  if (!purchaseId) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{t("error")}</Text>
      </View>
    );
  }

  if (purchaseQ.isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (purchaseQ.isError || !purchaseQ.data) {
    return (
      <View style={styles.centered}>
        <Text style={styles.err}>{t("purchaseLoadFail")}</Text>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>{t("back")}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const p = purchaseQ.data;
  const allowed = categoriesQ.data ?? [];
  const approved = p.status === "approved";

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backLink}>
        <Text style={styles.backLinkText}>{t("back")}</Text>
      </TouchableOpacity>
      <Text style={styles.title}>{t("purchaseDetailTitle")}</Text>
      <Text style={styles.subId}>{p.id}</Text>
      <View style={styles.chip}>
        <Text style={styles.chipText}>{p.status}</Text>
      </View>

      <Text style={styles.section}>{t("transcriptionLabel")}</Text>
      <View style={styles.transcriptionBox}>
        <Text style={styles.transcriptionText}>{p.transcription || "—"}</Text>
      </View>
      <View style={styles.rowBtn}>
        <TouchableOpacity
          style={[styles.secondaryBtn, extractM.isPending && styles.btnDisabled]}
          onPress={() => extractM.mutate()}
          disabled={extractM.isPending}
        >
          <Text style={styles.secondaryBtnText}>
            {extractM.isPending ? "…" : t("reExtract")}
          </Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.section}>{t("purchaseForm")}</Text>
      <Text style={styles.label}>{t("productName")}</Text>
      <TextInput
        style={styles.input}
        value={form.product_name}
        onChangeText={(product_name) => setForm((f) => ({ ...f, product_name }))}
        editable={!approved}
      />
      <Text style={styles.label}>{t("category")}</Text>
      <TextInput
        style={styles.input}
        value={form.category}
        onChangeText={(category) => setForm((f) => ({ ...f, category }))}
        placeholder={allowed.slice(0, 3).join(", ")}
        editable={!approved}
      />
      <Text style={styles.label}>{t("quantity")}</Text>
      <TextInput
        style={styles.input}
        value={form.quantity}
        onChangeText={(quantity) => setForm((f) => ({ ...f, quantity }))}
        keyboardType="decimal-pad"
        editable={!approved}
      />
      <Text style={styles.label}>{t("unitPrice")}</Text>
      <TextInput
        style={styles.input}
        value={form.unit_price}
        onChangeText={(unit_price) => setForm((f) => ({ ...f, unit_price }))}
        keyboardType="decimal-pad"
        editable={!approved}
      />
      <Text style={styles.totalLine}>
        {t("totalAmount")}: {fmtTn(total)} TND
      </Text>

      <TouchableOpacity
        style={[styles.primaryBtn, (approved || confirmM.isPending) && styles.btnDisabled]}
        onPress={() => confirmM.mutate()}
        disabled={approved || confirmM.isPending}
      >
        <Text style={styles.primaryBtnText}>
          {approved ? t("alreadyConfirmed") : confirmM.isPending ? "…" : t("confirm")}
        </Text>
      </TouchableOpacity>

      <Text style={styles.section}>{t("relatedAlerts")}</Text>
      {alertsQ.isLoading ? (
        <ActivityIndicator color={colors.primary} />
      ) : (alertsQ.data ?? []).length === 0 ? (
        <Text style={styles.muted}>{t("noAlerts")}</Text>
      ) : (
        (alertsQ.data as PurchaseAlertRow[]).map((a) => (
          <View key={a.id} style={styles.alertRow}>
            <Text style={styles.alertSev}>{a.severity}</Text>
            <Text style={styles.alertMsg}>{a.message}</Text>
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  backLink: { marginBottom: 8 },
  backLinkText: { color: colors.primary, fontSize: 16, fontWeight: "600" },
  title: { fontSize: 20, fontWeight: "700", color: colors.text },
  subId: { fontSize: 12, color: colors.textMuted, marginBottom: 8 },
  chip: {
    alignSelf: "flex-start",
    backgroundColor: colors.surfaceMuted,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    marginBottom: 16,
  },
  chipText: { fontSize: 12, fontWeight: "600", color: colors.text },
  section: { fontSize: 16, fontWeight: "700", color: colors.primary, marginTop: 16, marginBottom: 8 },
  transcriptionBox: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    maxHeight: 160,
  },
  transcriptionText: { fontSize: 14, color: colors.text },
  rowBtn: { flexDirection: "row", marginTop: 8, gap: 8 },
  secondaryBtn: {
    flex: 1,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary,
    alignItems: "center",
  },
  secondaryBtnText: { color: colors.primary, fontWeight: "600" },
  label: { fontSize: 14, color: colors.textMuted, marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    fontSize: 16,
    marginBottom: 12,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  totalLine: { fontSize: 15, fontWeight: "600", color: colors.text, marginBottom: 12 },
  primaryBtn: {
    backgroundColor: colors.primary,
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  primaryBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  btnDisabled: { opacity: 0.55 },
  alertRow: {
    backgroundColor: colors.surface,
    padding: 12,
    borderRadius: 10,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  alertSev: { fontSize: 12, fontWeight: "700", color: colors.warning, marginBottom: 4 },
  alertMsg: { fontSize: 14, color: colors.text },
  muted: { color: colors.textMuted, fontSize: 14 },
  err: { color: colors.error, marginBottom: 12 },
  backBtn: { padding: 12 },
  backBtnText: { color: colors.primary, fontWeight: "600" },
});
