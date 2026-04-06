import { useNetwork } from "../context/NetworkContext";

/**
 * Statut réseau appareil (expo-network) — à utiliser pour les messages d’erreur et la bannière hors ligne.
 * Ne reflète pas l’état du backend Docker (voir erreurs Axios sans `response`).
 */
export function useNetworkStatus() {
  const n = useNetwork();
  return {
    isConnected: n.isConnected,
    isInternetReachable: n.isInternetReachable,
    isOffline: n.showOfflineBanner,
    refreshNetworkState: n.refreshNetworkState,
  };
}
