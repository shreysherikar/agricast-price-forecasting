# Way2Agribusiness Forecasting Mobile App (React Native / Expo)

This directory contains the cross-platform mobile client for the agricultural price forecasting system, built with React Native and Expo (SDK 51).

---

## 1. Overview & Capabilities

The mobile application connects directly to the forecasting gateway (`/api/forecast/latest/`) and provides:
- **Fan Chart Visualizer**: 80% and 95% confidence fan areas alongside central monthly point projections.
- **Stale Data Warning Banner**: Real-time indicator displaying when the gateway is serving cached or fallback forecasts (`stale: true`).
- **Interactive Pull-to-Refresh**: Trigger fresh forecast requests with `force_refresh=true`.
- **Monthly Horizon Cards**: Expandable breakdown of lower/upper bounds, uncertainty spread, and directional bias.
- **Configurable Backend Target**: Zero hardcoded URLs; configured through `EXPO_PUBLIC_API_URL`.

---

## 2. Directory Structure

```text
mobile_app/
├── App.js           # Core mobile dashboard component with fan-chart visualization
├── app.json         # Expo project configuration (bundle ID, permissions, Android package)
├── eas.json         # Expo Application Services build profiles (preview APK, development)
├── package.json     # React Native & Expo SDK dependencies
└── README.md        # Architecture, local execution, and EAS cloud build guide
```

---

## 3. Local Development Setup

### Prerequisites
- Node.js >= 18.0.0
- npm or yarn
- Expo Go on iOS/Android or an Android Emulator / iOS Simulator

### Installation & Integrity Verification
```bash
cd mobile_app
npm install
npx expo-doctor
```
*(All 17/17 dependency and configuration checks pass).*

### Running Locally
Target your backend API endpoint via environment variable:

```bash
# Targeting local Django gateway:
# On Android Emulator: use 10.0.2.2 (alias for host machine localhost)
export EXPO_PUBLIC_API_URL=http://10.0.2.2:8080/api/forecast/latest/

# On physical phone on same Wi-Fi: use your computer's LAN IP
export EXPO_PUBLIC_API_URL=http://192.168.1.100:8080/api/forecast/latest/

# Targeting deployed cloud backend:
export EXPO_PUBLIC_API_URL=https://forecasting-gateway-xxxx.onrender.com/api/forecast/latest/

npx expo start
```
Press `a` for Android Emulator, `w` for web preview, or scan the QR code with Expo Go.

---

## 4. Standalone Android APK Build (EAS Build)

To generate a standalone installable Android APK without releasing to the Google Play Store, use Expo Application Services (EAS).

### Step 1: Set Deployed Backend URL

> [!WARNING]
> **Production URL Required for EAS Build**:  
> In `mobile_app/eas.json`, the `preview` profile contains the placeholder `https://REPLACE-WITH-GATEWAY-HOST.onrender.com/api/forecast/latest/`. You **must** replace this placeholder with your real deployed Render gateway URL before executing `eas build`.  
> Note that `http://10.0.2.2:8080/` is an alias specifically for the Android emulator loopback and will **not** work on a physical Android device running an installed APK.

Configure `EXPO_PUBLIC_API_URL` to point to your live deployed Django Gateway URL. You can set it in two ways:

1. **In `mobile_app/eas.json`**:
   Edit the `preview` profile under `build`:
   ```json
   "preview": {
     "distribution": "internal",
     "android": {
       "buildType": "apk"
     },
     "env": {
       "EXPO_PUBLIC_API_URL": "https://forecasting-gateway-xxxx.onrender.com/api/forecast/latest/"
     }
   }
   ```
2. **Or in `mobile_app/.env`**:
   ```bash
   EXPO_PUBLIC_API_URL=https://forecasting-gateway-xxxx.onrender.com/api/forecast/latest/
   ```

### Step 2: Log In to EAS
```bash
npx eas login
```
Enter your Expo account credentials (create a free account at [expo.dev](https://expo.dev) if you do not have one).

### Step 3: Run the Preview Build Command
```bash
npx eas build -p android --profile preview
```

### What Happens Next:
- EAS Cloud will validate the project configuration (`app.json` package `com.way2agribusiness.forecast`).
- EAS will build a standalone `.apk` artifact in the cloud.
- Once completed (typically 5-10 minutes), EAS provides a download URL and QR code in your terminal.
- Open the link or scan the QR code on any Android device to download and install the APK directly.

> [!NOTE]
> Per project guidelines, remote cloud build execution (`npx eas build`) requires interactive user login and is meant to be run directly by the user following the steps above.
