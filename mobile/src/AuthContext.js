import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import * as api from "./api";
import { loadApiUrl } from "./config";

const STORAGE_KEY = "eic.auth.v1";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        await loadApiUrl();
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) {
          const saved = JSON.parse(raw);
          setToken(saved.token || null);
          setUser(saved.user || null);
        }
      } catch {
        // ignore corrupt storage
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const persist = useCallback(async (nextToken, nextUser) => {
    setToken(nextToken);
    setUser(nextUser);
    if (nextToken) {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify({ token: nextToken, user: nextUser }));
    } else {
      await AsyncStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const signIn = useCallback(async (identifier, password) => {
    const data = await api.login(String(identifier || "").trim(), password);
    await persist(data.token, data.user);
    return data.user;
  }, [persist]);

  const register = useCallback(async (payload) => {
    const data = await api.register(payload);
    await persist(data.token, data.user);
    return data.user;
  }, [persist]);

  const signOut = useCallback(async () => {
    try {
      if (token) await api.logout(token);
    } catch {
      // still clear local session
    }
    await persist(null, null);
  }, [persist, token]);

  /** Drop local credentials without calling logout (stale token / guest mode). */
  const clearSession = useCallback(async () => {
    await persist(null, null);
  }, [persist]);

  const value = useMemo(
    () => ({
      token,
      user,
      ready,
      signIn,
      register,
      signOut,
      clearSession,
      isSignedIn: Boolean(token),
    }),
    [token, user, ready, signIn, register, signOut, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
