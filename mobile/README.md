# EIC Mobile Reporter

Expo (React Native) app for capturing an emergency incident photo and reporting it into the Emergency Incident Classifier website.

## What it does

1. Opens straight to **Report** — login is optional  
2. Capture or pick a JPG/PNG photo (guest or signed-in)  
3. Optionally add notes + GPS / place text  
4. Upload → classify → show result  
5. The report appears in the website **Classification log** (`source=mobile`)  
6. Sign in (Account / My reports) only if you want history linked to your account

## Prerequisites

- Django site running (`python manage.py runserver 0.0.0.0:8000`)
- Node.js 18+
- **Expo Go for SDK 58** on your phone (this project uses Expo SDK 58)

## Setup

```bash
cd mobile
npm install
```

### Point the app at your server

Default API URL is the Dev Tunnel:

`https://bb6cjv85-8000.asse.devtunnels.ms/api`

If the tunnel URL changes, update `mobile/app.json` → `extra.apiUrl`, or set:

```bash
# Windows PowerShell
$env:EXPO_PUBLIC_API_URL="https://YOUR-TUNNEL.asse.devtunnels.ms/api"
npm start
```

Django must allow the tunnel host in `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` (already set for the current tunnel in `eic_site/settings.py`).

## Run (phone-friendly tunnel)

```bash
npm start
```

This uses **ngrok tunnel mode** (`expo start --tunnel ngrok`) so Expo Go can load the app without an Expo account login and without being on the same Wi‑Fi.

1. Install **Expo Go** on your phone  
2. Scan the QR code from the terminal (Android: Expo Go / Camera; iOS: Camera → Expo Go)  
3. Tap **Sign in** (top right) → **Test connection** if needed  
4. If that fails, tap **Open in browser**, accept any Dev Tunnel “Continue” prompt, then test again  
5. Tap **Continue without signing in** to report immediately, or sign in with your website email/password  

API default: `https://bb6cjv85-8000.asse.devtunnels.ms/api` (editable on the Account screen).

## API used by the app

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login/` | email + password → bearer token |
| POST | `/api/auth/logout/` | revoke token |
| GET | `/api/meta/` | labels / active model |
| POST | `/api/classify/` | multipart image + notes/location (auth optional) |
| GET | `/api/classifications/` | reporter’s history (auth required) |
| GET | `/api/classifications/<id>/` | result detail (auth required) |
| POST | `/api/classifications/<id>/verify/` | quick verification (auth required) |

Authorization header (when signed in): `Authorization: Bearer <token>`
