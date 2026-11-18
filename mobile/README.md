# EIC Mobile Reporter

Expo (React Native) app for capturing an emergency incident photo and reporting it into the Emergency Incident Classifier website.

## What it does

1. Opens straight to **Report** — login is optional  
2. Capture or pick a JPG/PNG photo (guest or signed-in)  
3. Optionally add notes + GPS / place text  
4. Upload → classify → show result  
5. The report appears in the website **Incidents** page (`source=mobile`)  
6. Sign in (Account / My reports) only if you want history linked to your account

## Prerequisites

- Django site running (`python manage.py runserver 0.0.0.0:8000`)
- Node.js 18+
- **Expo Go for SDK 58** on your phone (App Store / Play Store → update to **58.0.6+**; this project uses Expo SDK 58)

### Fix: `EventEmitter` / `[runtime not ready]` red screen

This is an Expo Go iOS bug after a bad reload — not the Django API.

1. Update **Expo Go** (must be SDK 58, ideally 58.0.6 or newer)  
2. **Force-quit** Expo Go (swipe it away from the app switcher) — do **not** tap Refresh on the red error  
3. On the laptop: `cd mobile` → `npm start`  
4. In Expo Go tap **Home**, then scan the QR again  

If it still crashes, delete Expo Go and reinstall from the store, then repeat steps 3–4.

## Setup

```bash
cd mobile
npm install
```

### Point the app at your server (any network)

Default API URL is the public Microsoft Dev Tunnel — works on **any** phone network (Wi‑Fi or mobile data), not only the laptop’s LAN:

`https://bb6cjv85-8000.asse.devtunnels.ms/api`

The app **rejects** `localhost` / `192.168.*` API URLs. On Account, tap **Use public tunnel** to reset, or set `mobile/app.json` → `extra.apiUrl`, or:

```bash
# Windows PowerShell
$env:EXPO_PUBLIC_API_URL="https://bb6cjv85-8000.asse.devtunnels.ms/api"
npm start
```

Keep Django listening (`python manage.py runserver 0.0.0.0:8000`) and keep Ports → `8000` → **Visibility: Public**.

**Important:** Do **not** open `https://bb6cjv85-8000.asse.devtunnels.ms/` inside Expo Go. That URL is the website/API. Expo Go must load the app via the Metro QR / `exp://…` link from `npm start`.

## Run (phone-friendly tunnel)

```bash
npm start
```

This uses **ngrok tunnel mode** (`expo start --tunnel ngrok`) so Expo Go can load the app without an Expo account login and without being on the same Wi‑Fi.

1. Install **Expo Go** on your phone  
2. Scan the QR code from the terminal (Android: Expo Go / Camera; iOS: Camera → Expo Go)  
3. Tap **Sign in** (top right) → **Use public tunnel** → **Test connection**  
4. Tap **Continue without signing in** to report immediately, or sign in with your website username or email + password  

API default: `https://bb6cjv85-8000.asse.devtunnels.ms/api` (editable on the Account screen).

## API used by the app

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login/` | username or email + password → bearer token |
| POST | `/api/auth/logout/` | revoke token |
| GET | `/api/meta/` | labels / active model |
| POST | `/api/classify/` | multipart image + notes/location (auth optional) |
| GET | `/api/classifications/` | reporter’s history (auth required) |
| GET | `/api/classifications/<id>/` | result detail (auth required) |
| POST | `/api/classifications/<id>/verify/` | quick verification (auth required) |

Authorization header (when signed in): `Authorization: Bearer <token>`
