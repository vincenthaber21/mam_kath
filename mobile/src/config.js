import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

/**
 * Default API base URL — Dev Tunnel to the Django site.
 * Override in the login screen, or with EXPO_PUBLIC_API_URL.
 */
export const DEFAULT_API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  Constants.expoConfig?.extra?.apiUrl ||
  "https://bb6cjv85-8000.asse.devtunnels.ms/api";

const STORAGE_KEY = "eic.apiUrl.v1";

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

export async function loadApiUrl() {
  try {
    const saved = await AsyncStorage.getItem(STORAGE_KEY);
    if (saved && /^https?:\/\//i.test(saved)) {
      _apiUrl = saved.trim().replace(/\/+$/, "");
    }
  } catch {
    // ignore
  }
  return getApiUrl();
}

export async function setApiUrl(url) {
  _apiUrl = normalizeApiUrl(url);
  await AsyncStorage.setItem(STORAGE_KEY, _apiUrl);
  return _apiUrl;
}
