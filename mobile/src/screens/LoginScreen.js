import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ping } from "../api";
import { useAuth } from "../AuthContext";
import { DEFAULT_API_URL, getApiUrl, loadApiUrl, setApiUrl } from "../config";
import { colors, spacing } from "../theme";

export default function LoginScreen({ navigation }) {
  const { signIn, signOut, isSignedIn, user } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [apiField, setApiField] = useState(DEFAULT_API_URL);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    loadApiUrl().then((url) => setApiField(url));
  }, []);

  async function applyApiUrl() {
    const next = await setApiUrl(apiField);
    setApiField(next);
    return next;
  }

  async function onTest() {
    setError("");
    setStatus("");
    setTesting(true);
    try {
      await applyApiUrl();
      const data = await ping();
      setStatus(`Connected ✓ ${data.service || "eic-api"}`);
    } catch (err) {
      setError(err.message || "Connection failed.");
    } finally {
      setTesting(false);
    }
  }

  async function onSubmit() {
    setError("");
    setStatus("");
    setBusy(true);
    try {
      await applyApiUrl();
      await signIn(email, password);
      if (navigation?.canGoBack?.()) navigation.goBack();
    } catch (err) {
      setError(err.message || "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  async function onContinueAsGuest() {
    setError("");
    try {
      await applyApiUrl();
    } catch {
      // still allow continuing with previous URL
    }
    if (navigation?.canGoBack?.()) navigation.goBack();
  }

  async function onSignOut() {
    setBusy(true);
    setError("");
    try {
      await signOut();
    } catch (err) {
      setError(err.message || "Could not sign out.");
    } finally {
      setBusy(false);
    }
  }

  const siteRoot = getApiUrl().replace(/\/api$/i, "");

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.hero}>
          <Text style={styles.brand}>EIC</Text>
          <Text style={styles.title}>Incident Reporter</Text>
          <Text style={styles.subtitle}>
            Report without an account, or sign in to keep your reports under your name.
          </Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.label}>API URL (Dev Tunnel)</Text>
          <TextInput
            style={styles.input}
            autoCapitalize="none"
            autoCorrect={false}
            value={apiField}
            onChangeText={setApiField}
            placeholder={DEFAULT_API_URL}
            placeholderTextColor={colors.muted}
          />
          <View style={styles.row}>
            <Pressable style={styles.secondary} onPress={onTest} disabled={testing || busy}>
              {testing ? (
                <ActivityIndicator color={colors.brand} />
              ) : (
                <Text style={styles.secondaryText}>Test connection</Text>
              )}
            </Pressable>
            <Pressable
              style={styles.secondary}
              onPress={() => Linking.openURL(siteRoot || DEFAULT_API_URL.replace(/\/api$/i, ""))}
            >
              <Text style={styles.secondaryText}>Open in browser</Text>
            </Pressable>
          </View>

          {isSignedIn ? (
            <>
              <Text style={[styles.signedIn, styles.mt]}>
                Signed in as {user?.name || user?.email}
              </Text>
              {status ? <Text style={styles.ok}>{status}</Text> : null}
              {error ? <Text style={styles.error}>{error}</Text> : null}
              <Pressable style={[styles.btn, busy && styles.btnDisabled]} onPress={onSignOut} disabled={busy}>
                {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Sign out</Text>}
              </Pressable>
              <Pressable style={styles.guestBtn} onPress={onContinueAsGuest} disabled={busy}>
                <Text style={styles.guestText}>Back to reporting</Text>
              </Pressable>
            </>
          ) : (
            <>
              <Text style={[styles.label, styles.mt]}>Email</Text>
              <TextInput
                style={styles.input}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                value={email}
                onChangeText={setEmail}
                placeholder="you@example.com"
                placeholderTextColor={colors.muted}
              />
              <Text style={[styles.label, styles.mt]}>Password</Text>
              <TextInput
                style={styles.input}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
                placeholder="Password"
                placeholderTextColor={colors.muted}
              />
              {status ? <Text style={styles.ok}>{status}</Text> : null}
              {error ? <Text style={styles.error}>{error}</Text> : null}
              <Pressable style={[styles.btn, busy && styles.btnDisabled]} onPress={onSubmit} disabled={busy}>
                {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Sign in</Text>}
              </Pressable>
              <Pressable style={styles.guestBtn} onPress={onContinueAsGuest} disabled={busy}>
                <Text style={styles.guestText}>Continue without signing in</Text>
              </Pressable>
              <Text style={styles.hint}>
                Guest reports still go to the classification log. Sign in if you want them linked to your
                account and listed under My reports.
              </Text>
            </>
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.brand },
  scroll: { flexGrow: 1, justifyContent: "center", padding: spacing.lg, paddingVertical: 40 },
  hero: { marginBottom: spacing.lg },
  brand: { color: "#E8F5EF", fontSize: 42, fontWeight: "800", letterSpacing: 2 },
  title: { color: "#fff", fontSize: 26, fontWeight: "700", marginTop: 4 },
  subtitle: { color: "#C9DED4", fontSize: 15, lineHeight: 22, marginTop: spacing.sm, maxWidth: 320 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    padding: spacing.lg,
  },
  label: { color: colors.muted, fontSize: 13, fontWeight: "600", marginBottom: 6 },
  mt: { marginTop: spacing.md },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === "ios" ? 14 : 10,
    fontSize: 15,
    color: colors.text,
    backgroundColor: "#FAFCFA",
  },
  row: { flexDirection: "row", gap: 8, marginTop: spacing.sm },
  secondary: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: "#FAFCFA",
  },
  secondaryText: { color: colors.brand, fontWeight: "700", fontSize: 13 },
  signedIn: { color: colors.text, fontSize: 15, fontWeight: "600", lineHeight: 22 },
  error: { color: colors.danger, marginTop: spacing.sm, fontSize: 13, lineHeight: 18 },
  ok: { color: colors.success, marginTop: spacing.sm, fontSize: 13, fontWeight: "700" },
  btn: {
    marginTop: spacing.lg,
    backgroundColor: colors.brand,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  btnDisabled: { opacity: 0.7 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  guestBtn: {
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    backgroundColor: "#FAFCFA",
  },
  guestText: { color: colors.brand, fontSize: 15, fontWeight: "700" },
  hint: { marginTop: spacing.md, color: colors.muted, fontSize: 11, lineHeight: 16 },
});
