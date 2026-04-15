import { useMemo, useState } from "react";
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { colors } from "../../theme/colors";
import { font, radius, space } from "../../theme/tokens";
import { FormField, GhostButton, PrimaryButton, TextFieldInput } from "./primitives";

export type ListFilterState = {
  q?: string;
  transaction_type?: "buy" | "sell" | "";
  source?: "voice" | "scan" | "manual" | "";
  status?: string;
  qty_min?: string;
  qty_max?: string;
  unit_price_min?: string;
  unit_price_max?: string;
  ht_min?: string;
  ht_max?: string;
  tva_min?: string;
  tva_max?: string;
  ttc_min?: string;
  ttc_max?: string;
};

type Props = {
  title: string;
  visible: boolean;
  onClose: () => void;
  value: ListFilterState;
  statusOptions?: string[];
  allowQuantity?: boolean;
  onApply: (next: ListFilterState) => void;
};

function Chip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity style={[styles.chip, active && styles.chipOn]} onPress={onPress}>
      <Text style={[styles.chipText, active && styles.chipTextOn]}>{label}</Text>
    </TouchableOpacity>
  );
}

export function FilterSheet({
  title,
  visible,
  onClose,
  value,
  statusOptions = [],
  allowQuantity = false,
  onApply,
}: Props) {
  const [draft, setDraft] = useState<ListFilterState>(value);

  const normalizedStatusOptions = useMemo(
    () => Array.from(new Set(statusOptions.filter(Boolean))),
    [statusOptions]
  );

  const reset = () => {
    setDraft({});
  };

  const submit = () => {
    onApply(draft);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <Text style={styles.title}>{title}</Text>
          <ScrollView contentContainerStyle={styles.content}>
            <FormField label="Recherche">
              <TextFieldInput
                value={draft.q ?? ""}
                onChangeText={(q) => setDraft((s) => ({ ...s, q }))}
                placeholder="Produit, fournisseur, numéro..."
              />
            </FormField>

            <FormField label="Type transaction">
              <View style={styles.rowWrap}>
                <Chip
                  label="Tous"
                  active={!draft.transaction_type}
                  onPress={() => setDraft((s) => ({ ...s, transaction_type: "" }))}
                />
                <Chip
                  label="Achat"
                  active={draft.transaction_type === "buy"}
                  onPress={() => setDraft((s) => ({ ...s, transaction_type: "buy" }))}
                />
                <Chip
                  label="Vente"
                  active={draft.transaction_type === "sell"}
                  onPress={() => setDraft((s) => ({ ...s, transaction_type: "sell" }))}
                />
              </View>
            </FormField>

            <FormField label="Source">
              <View style={styles.rowWrap}>
                <Chip label="Toutes" active={!draft.source} onPress={() => setDraft((s) => ({ ...s, source: "" }))} />
                <Chip
                  label="Voice"
                  active={draft.source === "voice"}
                  onPress={() => setDraft((s) => ({ ...s, source: "voice" }))}
                />
                <Chip
                  label="Scan"
                  active={draft.source === "scan"}
                  onPress={() => setDraft((s) => ({ ...s, source: "scan" }))}
                />
                <Chip
                  label="Manuel"
                  active={draft.source === "manual"}
                  onPress={() => setDraft((s) => ({ ...s, source: "manual" }))}
                />
              </View>
            </FormField>

            {!!normalizedStatusOptions.length && (
              <FormField label="Statut">
                <View style={styles.rowWrap}>
                  <Chip label="Tous" active={!draft.status} onPress={() => setDraft((s) => ({ ...s, status: "" }))} />
                  {normalizedStatusOptions.map((st) => (
                    <Chip
                      key={st}
                      label={st}
                      active={draft.status === st}
                      onPress={() => setDraft((s) => ({ ...s, status: st }))}
                    />
                  ))}
                </View>
              </FormField>
            )}

            {allowQuantity && (
              <View style={styles.inline}>
                <View style={styles.col}>
                  <FormField label="Qte min">
                    <TextFieldInput
                      value={draft.qty_min ?? ""}
                      onChangeText={(qty_min) => setDraft((s) => ({ ...s, qty_min }))}
                      keyboardType="numeric"
                    />
                  </FormField>
                </View>
                <View style={styles.col}>
                  <FormField label="Qte max">
                    <TextFieldInput
                      value={draft.qty_max ?? ""}
                      onChangeText={(qty_max) => setDraft((s) => ({ ...s, qty_max }))}
                      keyboardType="numeric"
                    />
                  </FormField>
                </View>
              </View>
            )}

            <View style={styles.inline}>
              <View style={styles.col}>
                <FormField label="PU min">
                  <TextFieldInput
                    value={draft.unit_price_min ?? ""}
                    onChangeText={(unit_price_min) => setDraft((s) => ({ ...s, unit_price_min }))}
                    keyboardType="decimal-pad"
                  />
                </FormField>
              </View>
              <View style={styles.col}>
                <FormField label="PU max">
                  <TextFieldInput
                    value={draft.unit_price_max ?? ""}
                    onChangeText={(unit_price_max) => setDraft((s) => ({ ...s, unit_price_max }))}
                    keyboardType="decimal-pad"
                  />
                </FormField>
              </View>
            </View>

            <View style={styles.inline}>
              <View style={styles.col}>
                <FormField label="HT min">
                  <TextFieldInput
                    value={draft.ht_min ?? ""}
                    onChangeText={(ht_min) => setDraft((s) => ({ ...s, ht_min }))}
                    keyboardType="decimal-pad"
                  />
                </FormField>
              </View>
              <View style={styles.col}>
                <FormField label="HT max">
                  <TextFieldInput
                    value={draft.ht_max ?? ""}
                    onChangeText={(ht_max) => setDraft((s) => ({ ...s, ht_max }))}
                    keyboardType="decimal-pad"
                  />
                </FormField>
              </View>
            </View>

            <View style={styles.inline}>
              <View style={styles.col}>
                <FormField label="TVA min">
                  <TextFieldInput
                    value={draft.tva_min ?? ""}
                    onChangeText={(tva_min) => setDraft((s) => ({ ...s, tva_min }))}
                    keyboardType="decimal-pad"
                  />
                </FormField>
              </View>
              <View style={styles.col}>
                <FormField label="TVA max">
                  <TextFieldInput
                    value={draft.tva_max ?? ""}
                    onChangeText={(tva_max) => setDraft((s) => ({ ...s, tva_max }))}
                    keyboardType="decimal-pad"
                  />
                </FormField>
              </View>
            </View>

            <View style={styles.inline}>
              <View style={styles.col}>
                <FormField label="TTC min">
                  <TextFieldInput
                    value={draft.ttc_min ?? ""}
                    onChangeText={(ttc_min) => setDraft((s) => ({ ...s, ttc_min }))}
                    keyboardType="decimal-pad"
                  />
                </FormField>
              </View>
              <View style={styles.col}>
                <FormField label="TTC max">
                  <TextFieldInput
                    value={draft.ttc_max ?? ""}
                    onChangeText={(ttc_max) => setDraft((s) => ({ ...s, ttc_max }))}
                    keyboardType="decimal-pad"
                  />
                </FormField>
              </View>
            </View>
          </ScrollView>
          <View style={styles.actions}>
            <GhostButton title="Réinitialiser" onPress={reset} />
            <PrimaryButton title="Appliquer" onPress={submit} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.45)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    padding: space.lg,
    maxHeight: "88%",
  },
  title: { fontSize: font.lg, fontWeight: font.bold, color: colors.primaryDark, marginBottom: space.md },
  content: { gap: space.sm, paddingBottom: space.sm },
  rowWrap: { flexDirection: "row", flexWrap: "wrap", gap: space.xs },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.full,
    paddingHorizontal: space.sm,
    paddingVertical: space.xs,
    backgroundColor: colors.surfaceMuted,
  },
  chipOn: { borderColor: colors.primary, backgroundColor: colors.primaryMuted },
  chipText: { fontSize: font.xs, color: colors.textSecondary, fontWeight: font.semibold },
  chipTextOn: { color: colors.primaryDark },
  inline: { flexDirection: "row", gap: space.md },
  col: { flex: 1 },
  actions: { paddingTop: space.sm, gap: space.sm },
});

