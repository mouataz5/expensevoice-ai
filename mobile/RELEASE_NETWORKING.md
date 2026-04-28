# Android APK Networking / Release Checklist

## Root policy

- Release APK (`__DEV__ === false`) uses **only** `EXPO_PUBLIC_API_URL`.
- No localhost / `127.0.0.1` / Metro host fallback in release.
- If `EXPO_PUBLIC_API_URL` is missing or invalid, API calls are blocked with a clear configuration error.

## Required build env

Set at build time (EAS secrets or profile env):

- `EXPO_PUBLIC_API_URL=https://your-api-domain.tld` (recommended)
- `EXPO_PUBLIC_APP_ENV=prod`

For local LAN testing with HTTP:

- `EXPO_PUBLIC_API_URL=http://<PC_LAN_IP>:8000`
- Android cleartext is enabled via `android.usesCleartextTraffic=true`.

## Build commands

Preview APK (internal testing):

```bash
eas build --platform android --profile preview
```

Production:

```bash
eas build --platform android --profile production
```

## Runtime diagnostics

At startup, the client logs resolved API config:

- origin
- source (`env` / dev fallback source)
- release flag
- platform
- cleartext usage

In release, network errors are classified into:

- offline
- backend timeout
- backend unreachable
- API config missing/invalid

## Quick on-device verification

1. Install APK.
2. Open app and check login error message:
   - Missing config -> "API URL not set" style message.
   - Offline -> internet missing message.
   - Unreachable backend -> server reachability message.
3. Try valid login and verify requests hit expected backend URL.
