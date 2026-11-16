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

  const signIn = useCallback(async (email, password) => {
    const data = await api.login(email.trim(), password);
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

  const value = useMemo(
    () => ({ token, user, ready, signIn, signOut, isSignedIn: Boolean(token) }),
    [token, user, ready, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
