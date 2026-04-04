/** Initiales pour avatar (sans backend : e-mail ou nom affiché). */
export function getUserInitials(email?: string | null, displayName?: string | null): string {
  const name = displayName?.trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0]!.charAt(0)}${parts[1]!.charAt(0)}`.toUpperCase();
    }
    if (parts.length === 1 && parts[0]!.length >= 2) {
      return parts[0]!.slice(0, 2).toUpperCase();
    }
    if (parts.length === 1) {
      const w = parts[0]!;
      if (w.length >= 2) return w.slice(0, 2).toUpperCase();
      return w.charAt(0).toUpperCase();
    }
  }
  const em = email?.trim();
  if (!em) return "?";
  const local = em.split("@")[0] ?? em;
  if (local.length >= 2) return local.slice(0, 2).toUpperCase();
  return (local.charAt(0) || "?").toUpperCase() + (local.charAt(1)?.toUpperCase() ?? "");
}

export function normalizeUserRole(role: string | undefined | null): "admin" | "director" | "employee" | null {
  if (role === "admin" || role === "director" || role === "employee") return role;
  return null;
}
