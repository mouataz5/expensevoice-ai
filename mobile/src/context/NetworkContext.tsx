import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AppState, type AppStateStatus } from "react-native";
import * as Network from "expo-network";
import type { NetworkState } from "expo-network";

export type NetworkCtx = {
  /** Données / Wi‑Fi connecté au niveau OS */
  isConnected: boolean;
  /** null si le système ne fournit pas l’info (souvent iOS) — ne pas traiter comme « en ligne » falsifié */
  isInternetReachable: boolean | null;
  /** Bannière « pas d’internet » (pas la même chose que « backend Docker éteint ») */
  showOfflineBanner: boolean;
  refreshNetworkState: () => Promise<void>;
};

const Ctx = createContext<NetworkCtx | null>(null);

function stateFromNetwork(s: NetworkState): Omit<NetworkCtx, "refreshNetworkState"> {
  const connected = s.isConnected !== false;
  const reachable = s.isInternetReachable;
  const showOffline = s.isConnected === false || reachable === false;
  return {
    isConnected: connected,
    isInternetReachable: reachable ?? null,
    showOfflineBanner: showOffline,
  };
}

export function NetworkProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<NetworkCtx, "refreshNetworkState">>({
    isConnected: true,
    isInternetReachable: null,
    showOfflineBanner: false,
  });

  const refreshNetworkState = useCallback(async () => {
    try {
      const s = await Network.getNetworkStateAsync();
      setState(stateFromNetwork(s));
    } catch {
      setState({
        isConnected: true,
        isInternetReachable: null,
        showOfflineBanner: false,
      });
    }
  }, []);

  useEffect(() => {
    void refreshNetworkState();
    const sub = Network.addNetworkStateListener((ev) => {
      setState(stateFromNetwork(ev));
    });
    return () => sub.remove();
  }, [refreshNetworkState]);

  useEffect(() => {
    const onChange = (st: AppStateStatus) => {
      if (st === "active") void refreshNetworkState();
    };
    const sub = AppState.addEventListener("change", onChange);
    return () => sub.remove();
  }, [refreshNetworkState]);

  const value = useMemo<NetworkCtx>(
    () => ({
      ...state,
      refreshNetworkState,
    }),
    [state, refreshNetworkState]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useNetwork(): NetworkCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useNetwork must be used within NetworkProvider");
  return v;
}
