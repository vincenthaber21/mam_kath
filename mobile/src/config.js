import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

/**
 * Public Dev Tunnel → Django API. Works on any network (Wi‑Fi or mobile data).
 * Override in the login screen, or with EXPO_PUBLIC_API_URL.
 */
export const DEFAULT_API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  Constants.expoConfig?.extra?.apiUrl ||
  "https://bb6cjv85-8000.asse.devtunnels.ms/api";

const STORAGE_KEY = "eic.apiUrl.v3";
const LEGACY_KEYS = ["eic.apiUrl.v2", "eic.apiUrl.v1"];

/** Mutable at runtime so the login screen can point at a new tunnel without rebuild. */
let _apiUrl = DEFAULT_API_URL;

export function getApiUrl() {
  return _apiUrl.replace(/\/+$/, "");
}

/** @deprecated prefer getApiUrl() */
export const API_URL = DEFAULT_API_URL;

function normalizeApiUrl(url) {
  let cleaned = (url || "").trim().replace(/\/+$/, "");
  if (!cleaned) {
    throw new Error("API URL cannot be empty.");
  }
  if (!/^https?:\/\//i.test(cleaned)) {
    throw new Error("API URL must start with http:// or https://");
  }
  // Paste of site root → append /api
  if (!/\/api$/i.test(cleaned)) {
    cleaned = `${cleaned}/api`;
  }
  return cleaned;
}

/** LAN / loopback hosts only work on the same Wi‑Fi — not on mobile data or other networks. */
export function isLocalOnlyApiUrl(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    if (host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0" || host === "10.0.2.2") {
      return true;
    }
    if (/^192\.168\.\d{1,3}\.\d{1,3}$/.test(host)) return true;
    if (/^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host)) return true;
    if (/^172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}$/.test(host)) return true;
    return false;
  } catch {
    return false;
  }
}

function isUsableSavedUrl(url) {
  if (!url || !/^https?:\/\//i.test(url)) return false;
  // Dead Cloudflare quick tunnels, or private IPs that break off-LAN.
  if (/trycloudflare\.com/i.test(url)) return false;
  if (isLocalOnlyApiUrl(url)) return false;
  return true;
}

export async function loadApiUrl() {
  try {
    let saved = await AsyncStorage.getItem(STORAGE_KEY);
    if (!saved) {
      for (const key of LEGACY_KEYS) {
        const legacy = await AsyncStorage.getItem(key);
        if (isUsableSavedUrl(legacy)) {
          saved = legacy;
          break;
        }
      }
    }
    if (isUsableSavedUrl(saved)) {
      _apiUrl = normalizeApiUrl(saved);
    } else {
      // Force public tunnel so phones on any network can reach the API.
      _apiUrl = normalizeApiUrl(DEFAULT_API_URL);
    }
    await AsyncStorage.setItem(STORAGE_KEY, _apiUrl);
  } catch {
    _apiUrl = normalizeApiUrl(DEFAULT_API_URL);
  }
  return getApiUrl();
}

export async function setApiUrl(url) {
  const next = normalizeApiUrl(url);
  if (isLocalOnlyApiUrl(next)) {
    throw new Error(
      "That address only works on the same Wi‑Fi. Use the public tunnel: " +
        "https://bb6cjv85-8000.asse.devtunnels.ms/api",
    );
  }
  _apiUrl = next;
  await AsyncStorage.setItem(STORAGE_KEY, _apiUrl);
  return _apiUrl;
}

/** Reset to the bundled public Dev Tunnel (any network). */
export async function usePublicTunnel() {
  _apiUrl = normalizeApiUrl(DEFAULT_API_URL);
  await AsyncStorage.setItem(STORAGE_KEY, _apiUrl);
  return _apiUrl;
}

/** Site root (without `/api`) for media URLs. */
export function getSiteRoot() {
  return getApiUrl().replace(/\/api$/i, "");
}

/**
 * Make an image URI loadable on the phone.
 * Prefers local capture URIs; rewrites localhost / LAN media URLs to the public tunnel host.
 */
export function resolveImageUri(url) {
  if (!url) return null;
  if (/^(file|content|ph|assets-library):/i.test(url)) return url;
  const root = getSiteRoot();
  try {
    if (/^https?:\/\//i.test(url)) {
      const parsed = new URL(url);
      if (isLocalOnlyApiUrl(`${parsed.protocol}//${parsed.hostname}`)) {
        return `${root}${parsed.pathname}${parsed.search}`;
      }
      return url;
    }
  } catch {
    // fall through
  }
  return `${root}${url.startsWith("/") ? url : `/${url}`}`;
}
