import React, {
  createContext,
  useContext,
  useMemo,
  useState,
} from "react";

type AuthState = {
  token: string | null;
  setToken: (t: string | null) => void;
  logout: () => void;
};

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(
    () => localStorage.getItem("access_token")
  );

  const setToken = (t: string | null) => {
    if (t) localStorage.setItem("access_token", t);
    else localStorage.removeItem("access_token");
    setTokenState(t);
  };

  const logout = () => setToken(null);

  const value = useMemo(() => ({ token, setToken, logout }), [token]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
