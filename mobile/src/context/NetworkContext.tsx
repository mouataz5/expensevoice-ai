import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { AppState, type AppStateStatus } from "react-native";
import { subscribeNetworkStatus } from "../lib/networkStatus";

type NetworkCtx = {
  isOnline: boolean;
  setAssumedOnline: () => void;
};

const Ctx = createContext<NetworkCtx | null>(null);

export function NetworkProvider({ children }: { children: ReactNode }) {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    return subscribeNetworkStatus(setIsOnline);
  }, []);

  useEffect(() => {
    const onChange = (s: AppStateStatus) => {
      if (s === "active") setIsOnline(true);
    };
    const sub = AppState.addEventListener("change", onChange);
    return () => sub.remove();
  }, []);

  const setAssumedOnline = useCallback(() => setIsOnline(true), []);

  const value = useMemo(() => ({ isOnline, setAssumedOnline }), [isOnline, setAssumedOnline]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useNetwork(): NetworkCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useNetwork outside NetworkProvider");
  return v;
}
