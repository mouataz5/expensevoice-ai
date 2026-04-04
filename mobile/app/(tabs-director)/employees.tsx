import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  TouchableOpacity,
  Modal,
  TextInput,
  Switch,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
} from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../src/context/AuthContext";
import { useLocale } from "../../src/context/LocaleContext";
import { colors } from "../../src/theme/colors";
import { font, radius, space } from "../../src/theme/tokens";
import {
  fetchAdminUsers,
  fetchUsersMap,
  createUser,
  updateUser,
  resetUserPassword,
  type UserOut,
  type UserMapItem,
} from "../../src/api/users";
import Toast from "react-native-toast-message";
import {
  EmptyState,
  ErrorState,
  PrimaryButton,
  ProductBrandMark,
  UserAvatar,
  UsersListSkeleton,
} from "../../src/components/ui";
import { AdminAccentStripe, AdminErrorShell, AdminHeader } from "../../src/components/admin";
import { formatApiError } from "../../src/utils/apiError";

const ROLES = ["employee", "director", "admin"] as const;

export default function DirectorEmployeesScreen() {
  const { user } = useAuth();
  const { t } = useLocale();
  const qc = useQueryClient();
  const role = user?.role;
  const isAdmin = role === "admin";
  const isDirector = role === "director";
  const isReady = !!role;

  const [addOpen, setAddOpen] = useState(false);
  const [addEmail, setAddEmail] = useState("");
  const [addPassword, setAddPassword] = useState("");
  const [addRole, setAddRole] = useState<string>("employee");
  const [resettingId, setResettingId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const adminQ = useQuery({
    queryKey: ["admin-users"],
    queryFn: fetchAdminUsers,
    enabled: isReady && isAdmin,
    retry: false,
  });

  const mapQ = useQuery({
    queryKey: ["users-map"],
    queryFn: fetchUsersMap,
    enabled: isReady && isDirector,
    retry: false,
  });

  const list = isAdmin ? (adminQ.data ?? []) : (mapQ.data ?? []);
  const isLoading = isAdmin ? adminQ.isLoading : mapQ.isLoading;
  const error = isAdmin ? adminQ.error : mapQ.error;
  const refetch = isAdmin ? adminQ.refetch : mapQ.refetch;
  const isRefetching = isAdmin ? adminQ.isRefetching : mapQ.isRefetching;

  const createM = useMutation({
    mutationFn: (payload: { email: string; password: string; role: string }) =>
      createUser(payload),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("usersCreated") });
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      setAddOpen(false);
      setAddEmail("");
      setAddPassword("");
      setAddRole("employee");
    },
    onError: (e: unknown) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message || t("usersCreateFail") });
    },
  });

  const updateM = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: { role?: string; is_active?: boolean };
    }) => updateUser(id, payload),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("usersUpdated") });
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (e: unknown) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message || t("usersUpdateFail") });
    },
  });

  const resetM = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      resetUserPassword(id, password),
    onSuccess: () => {
      Toast.show({ type: "success", text1: t("usersPasswordReset") });
      setResettingId(null);
      setNewPassword("");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (e: unknown) => {
      const { message } = formatApiError(e, t);
      Toast.show({ type: "error", text1: t("error"), text2: message || t("usersResetFail") });
    },
  });

  const handleRoleChange = (u: UserOut, role: string) => {
    if (!ROLES.includes(role as (typeof ROLES)[number])) return;
    updateM.mutate({ id: u.id, payload: { role } });
  };

  const handleActiveChange = (u: UserOut, isActive: boolean) => {
    updateM.mutate({ id: u.id, payload: { is_active: isActive } });
  };

  if (!isReady) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  const errFmt = error ? formatApiError(error, t) : null;

  if (isLoading) {
    return (
      <View style={styles.container}>
        <View style={styles.listHeaderPad}>
          <AdminAccentStripe />
          <ProductBrandMark title={t("appName")} subtitle={t("employees")} />
        </View>
        <UsersListSkeleton count={8} />
      </View>
    );
  }

  if (error && errFmt) {
    return (
      <AdminErrorShell>
        <ErrorState
          title={t("error")}
          message={errFmt.message}
          hint={errFmt.hint}
          onRetry={() => refetch()}
          retryLabel={t("retry")}
        />
      </AdminErrorShell>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.listHeaderPad}>
        <AdminAccentStripe />
        <ProductBrandMark title={t("appName")} subtitle={t("employees")} />
        <AdminHeader eyebrow={t("adminEyebrow")} subtitle={t("adminEmployeesWorkspaceSubtitle")} />
        {isAdmin ? (
          <PrimaryButton title={t("usersAddUser")} onPress={() => setAddOpen(true)} />
        ) : null}
      </View>

      {isDirector ? <Text style={styles.hint}>{t("usersDirectorHint")}</Text> : null}

      <FlatList
        data={list}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[styles.list, list.length === 0 && styles.listFlex]}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        ListEmptyComponent={
          <EmptyState
            icon="people-outline"
            title={t("directorEmployeesEmpty")}
            subtitle={isAdmin ? t("directorEmployeesEmptyHint") : t("usersDirectorHint")}
            primaryCtaTitle={isAdmin ? t("usersAddUser") : t("retry")}
            onPrimaryCta={isAdmin ? () => setAddOpen(true) : () => refetch()}
          />
        }
        renderItem={({ item }) => (
          <UserRow
            item={item}
            isAdmin={isAdmin}
            resettingId={resettingId}
            newPassword={newPassword}
            setNewPassword={setNewPassword}
            setResettingId={setResettingId}
            onRoleChange={handleRoleChange}
            onActiveChange={handleActiveChange}
            onReset={() =>
              newPassword ? resetM.mutate({ id: item.id, password: newPassword }) : null
            }
            resetM={resetM}
            updateM={updateM}
            t={t}
          />
        )}
      />

      <Modal visible={addOpen} animationType="slide" transparent>
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.modalOverlay}
        >
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>{t("usersAddUser")}</Text>
            <ScrollView keyboardShouldPersistTaps="handled">
              <Text style={styles.label}>{t("email")}</Text>
              <TextInput
                style={styles.input}
                value={addEmail}
                onChangeText={setAddEmail}
                placeholder="user@example.com"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="none"
                keyboardType="email-address"
              />
              <Text style={styles.label}>{t("password")}</Text>
              <TextInput
                style={styles.input}
                value={addPassword}
                onChangeText={setAddPassword}
                placeholder="••••••••"
                placeholderTextColor={colors.textMuted}
                secureTextEntry
              />
              <Text style={styles.label}>{t("usersRole")}</Text>
              <View style={styles.roleRow}>
                {ROLES.map((r) => (
                  <TouchableOpacity
                    key={r}
                    style={[
                      styles.roleBtn,
                      addRole === r && styles.roleBtnActive,
                    ]}
                    onPress={() => setAddRole(r)}
                  >
                    <Text
                      style={[
                        styles.roleBtnText,
                        addRole === r && styles.roleBtnTextActive,
                      ]}
                      pointerEvents="none"
                    >
                      {r}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnPrimary]}
                onPress={() =>
                  addEmail.trim() &&
                  addPassword &&
                  createM.mutate({
                    email: addEmail.trim(),
                    password: addPassword,
                    role: addRole,
                  })
                }
                disabled={!addEmail.trim() || !addPassword || createM.isPending}
              >
                <Text style={styles.modalBtnText} pointerEvents="none">
                  {createM.isPending ? t("usersCreating") : t("usersCreate")}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnSecondary]}
                onPress={() => setAddOpen(false)}
              >
                <Text style={styles.modalBtnTextSecondary} pointerEvents="none">
                  {t("cancel")}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

function UserRow({
  item,
  isAdmin,
  resettingId,
  newPassword,
  setNewPassword,
  setResettingId,
  onRoleChange,
  onActiveChange,
  onReset,
  resetM,
  updateM,
  t,
}: {
  item: UserOut | UserMapItem;
  isAdmin: boolean;
  resettingId: string | null;
  newPassword: string;
  setNewPassword: (v: string) => void;
  setResettingId: (v: string | null) => void;
  onRoleChange: (u: UserOut, role: string) => void;
  onActiveChange: (u: UserOut, isActive: boolean) => void;
  onReset: () => void;
  resetM: { mutate: (p: { id: string; password: string }) => void; isPending: boolean };
  updateM: { isPending: boolean };
  t: (key: string) => string;
}) {
  const u = item as UserOut;
  const hasActive = "is_active" in u;
  const isResetting = resettingId === item.id;

  const roleTxt =
    item.role === "admin"
      ? t("roleAdmin")
      : item.role === "director"
        ? t("roleDirector")
        : item.role === "employee"
          ? t("roleEmployee")
          : item.role;

  return (
    <View style={styles.row}>
      <View style={styles.rowTop}>
        <UserAvatar
          email={item.email}
          size="sm"
          role={item.role}
          showRoleBadge
          accessible={false}
          style={styles.rowAvatar}
        />
        <View style={styles.rowMain}>
          <Text style={styles.rowEmail}>{item.email}</Text>
          <Text style={styles.rowRole}>{roleTxt}</Text>
        {hasActive && (
          <View style={styles.rowActive}>
            <Text style={styles.rowActiveLabel}>
              {u.is_active ?? true ? t("usersActive") : t("usersDisabled")}
            </Text>
            {isAdmin && (
              <Switch
                value={u.is_active ?? true}
                onValueChange={(v) => onActiveChange(u, v)}
                disabled={updateM.isPending}
                trackColor={{ false: colors.textMuted, true: colors.primary }}
                thumbColor="#fff"
              />
            )}
          </View>
        )}
        </View>
      </View>
      {isAdmin && (
        <View style={styles.rowActions}>
          {hasActive && (
            <View style={styles.roleRow}>
              {ROLES.map((r) => (
                <TouchableOpacity
                  key={r}
                  style={[
                    styles.roleBtnSmall,
                    u.role === r && styles.roleBtnActive,
                  ]}
                  onPress={() => onRoleChange(u, r)}
                  disabled={updateM.isPending}
                >
                  <Text
                    style={[
                      styles.roleBtnTextSmall,
                      u.role === r && styles.roleBtnTextActive,
                    ]}
                    pointerEvents="none"
                  >
                    {r}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
          {isResetting ? (
            <View style={styles.resetRow}>
              <TextInput
                style={styles.inputSmall}
                value={newPassword}
                onChangeText={setNewPassword}
                placeholder={t("usersNewPassword")}
                placeholderTextColor={colors.textMuted}
                secureTextEntry
              />
              <TouchableOpacity
                style={styles.resetSubmitBtn}
                onPress={onReset}
                disabled={!newPassword || resetM.isPending}
              >
                <Text style={styles.resetSubmitText} pointerEvents="none">
                  {t("usersReset")}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => {
                  setResettingId(null);
                  setNewPassword("");
                }}
              >
                <Text style={styles.cancelBtnText} pointerEvents="none">
                  {t("cancel")}
                </Text>
              </TouchableOpacity>
            </View>
          ) : (
            hasActive && (
              <TouchableOpacity
                style={styles.resetBtn}
                onPress={() => setResettingId(item.id)}
              >
                <Text style={styles.resetBtnText} pointerEvents="none">
                  {t("usersResetPassword")}
                </Text>
              </TouchableOpacity>
            )
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  listHeaderPad: {
    paddingHorizontal: space.lg,
    paddingTop: space.md,
    paddingBottom: space.sm,
    gap: space.md,
  },
  hint: {
    fontSize: font.sm,
    color: colors.textMuted,
    paddingHorizontal: space.lg,
    marginBottom: space.sm,
  },
  list: { paddingHorizontal: space.lg, paddingBottom: space.xxxl },
  listFlex: { flexGrow: 1 },
  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.md,
    marginBottom: space.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowTop: { flexDirection: "row", alignItems: "flex-start", marginBottom: space.sm },
  rowAvatar: { marginRight: space.md, marginTop: 2 },
  rowMain: { flex: 1, minWidth: 0, marginBottom: 0 },
  rowEmail: { fontSize: 16, fontWeight: "600", color: colors.text },
  rowRole: { fontSize: 14, color: colors.textMuted, marginTop: 4 },
  rowActive: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 8,
    gap: 8,
  },
  rowActiveLabel: { fontSize: 14, color: colors.textMuted },
  rowActions: { marginTop: 12, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 12 },
  roleRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 8 },
  roleBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: colors.surfaceMuted,
  },
  roleBtnActive: { backgroundColor: colors.primary },
  roleBtnText: { fontSize: 14, color: colors.text },
  roleBtnTextActive: { color: "#fff", fontWeight: "600" },
  roleBtnSmall: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: colors.surfaceMuted,
  },
  roleBtnTextSmall: { fontSize: 12, color: colors.text },
  resetRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  inputSmall: {
    flex: 1,
    minWidth: 100,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
  },
  resetSubmitBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
  },
  resetSubmitText: { color: "#fff", fontSize: 14, fontWeight: "600" },
  cancelBtn: { paddingHorizontal: 12, paddingVertical: 8 },
  cancelBtnText: { color: colors.textMuted, fontSize: 14 },
  resetBtn: {
    alignSelf: "flex-start",
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  resetBtnText: { color: colors.primary, fontSize: 14, fontWeight: "600" },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    padding: 24,
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: 24,
    maxHeight: "80%",
  },
  modalTitle: { fontSize: 18, fontWeight: "700", color: colors.primary, marginBottom: 16 },
  label: { fontSize: 14, fontWeight: "600", color: colors.text, marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 16,
  },
  modalActions: { flexDirection: "row", gap: 12, marginTop: 20 },
  modalBtn: { flex: 1, paddingVertical: 14, borderRadius: 12, alignItems: "center" },
  modalBtnPrimary: { backgroundColor: colors.primary },
  modalBtnSecondary: { borderWidth: 1, borderColor: colors.border },
  modalBtnText: { color: "#fff", fontWeight: "600", fontSize: 16 },
  modalBtnTextSecondary: { color: colors.text, fontSize: 16 },
});
