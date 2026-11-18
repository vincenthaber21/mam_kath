import React, { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { useAuth } from "../AuthContext";
import { colors, spacing } from "../theme";

export default function LoginScreen({ navigation }) {
  const { signIn, signOut, clearSession, isSignedIn, user } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    const id = identifier.trim();
    if (!id || !password) {
      setError("Enter your username or email and password.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await signIn(id, password);
      if (navigation?.canGoBack?.()) navigation.goBack();
    } catch (err) {
      setError(err.message || "Could not sign in. Check your details and try again.");
    } finally {
      setBusy(false);
    }
  }

  async function onContinueAsGuest() {
    setError("");
    setBusy(true);
    try {
      if (isSignedIn) await clearSession();
      if (navigation?.canGoBack?.()) navigation.goBack();
    } catch (err) {
      setError(err.message || "Could not continue.");
    } finally {
      setBusy(false);
    }
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

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.hero}>
          <Text style={styles.brand}>EIC</Text>
          <Text style={styles.title}>Welcome back</Text>
          <Text style={styles.subtitle}>
            Sign in to save reports under your name, or continue as a guest.
          </Text>
        </View>

        <View style={styles.card}>
          {isSignedIn ? (
            <>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>
                  {(user?.name || user?.username || user?.email || "?")
                    .charAt(0)
                    .toUpperCase()}
                </Text>
              </View>
              <Text style={styles.signedInLabel}>Signed in</Text>
              <Text style={styles.signedInName}>
                {user?.name || user?.username || user?.email}
              </Text>
              {user?.email && user?.name ? (
                <Text style={styles.signedInEmail}>{user.email}</Text>
              ) : null}

              {error ? <Text style={styles.error}>{error}</Text> : null}

              <Pressable
                style={[styles.btn, busy && styles.btnDisabled]}
                onPress={onSignOut}
                disabled={busy}
                accessibilityRole="button"
                accessibilityLabel="Sign out"
              >
                {busy ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.btnText}>Sign out</Text>
                )}
              </Pressable>
              <Pressable
                style={[styles.guestBtn, busy && styles.btnDisabled]}
                onPress={onContinueAsGuest}
                disabled={busy}
                accessibilityRole="button"
                accessibilityLabel="Back to reporting"
              >
                <Text style={styles.guestText}>Back to reporting</Text>
              </Pressable>
            </>
          ) : (
            <>
              <Text style={styles.label}>Username or email</Text>
              <TextInput
                style={styles.input}
                autoCapitalize="none"
                autoCorrect={false}
                autoComplete="username"
                textContentType="username"
                keyboardType="email-address"
                returnKeyType="next"
                value={identifier}
                onChangeText={(v) => {
                  setIdentifier(v);
                  if (error) setError("");
                }}
                placeholder="username or you@example.com"
                placeholderTextColor={colors.muted}
                editable={!busy}
                accessibilityLabel="Username or email"
              />

              <Text style={[styles.label, styles.mt]}>Password</Text>
              <View style={styles.passwordRow}>
                <TextInput
                  style={styles.passwordInput}
                  secureTextEntry={!showPassword}
                  autoComplete="password"
                  textContentType="password"
                  returnKeyType="go"
                  value={password}
                  onChangeText={(v) => {
                    setPassword(v);
                    if (error) setError("");
                  }}
                  onSubmitEditing={onSubmit}
                  placeholder="Enter your password"
                  placeholderTextColor={colors.muted}
                  editable={!busy}
                  accessibilityLabel="Password"
                />
                <Pressable
                  style={styles.showBtn}
                  onPress={() => setShowPassword((v) => !v)}
                  hitSlop={8}
                  accessibilityRole="button"
                  accessibilityLabel={showPassword ? "Hide password" : "Show password"}
                >
                  <Text style={styles.showBtnText}>{showPassword ? "Hide" : "Show"}</Text>
                </Pressable>
              </View>

              {error ? <Text style={styles.error}>{error}</Text> : null}

              <Pressable
                style={[styles.btn, busy && styles.btnDisabled]}
                onPress={onSubmit}
                disabled={busy}
                accessibilityRole="button"
                accessibilityLabel="Sign in"
              >
                {busy ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.btnText}>Sign in</Text>
                )}
              </Pressable>

              <Pressable
                style={[styles.registerBtn, busy && styles.btnDisabled]}
                onPress={() => navigation.navigate("Register")}
                disabled={busy}
                accessibilityRole="button"
                accessibilityLabel="Create resident account"
              >
                <Text style={styles.registerText}>Create resident account</Text>
              </Pressable>
              <Text style={styles.registerHint}>
                For residents of Santa Maria, Ilocos Sur
              </Text>

              <View style={styles.divider}>
                <View style={styles.dividerLine} />
                <Text style={styles.dividerText}>or</Text>
                <View style={styles.dividerLine} />
              </View>

              <Pressable
                style={[styles.guestBtn, busy && styles.btnDisabled]}
                onPress={onContinueAsGuest}
                disabled={busy}
                accessibilityRole="button"
                accessibilityLabel="Continue without signing in"
              >
                <Text style={styles.guestText}>Continue as guest</Text>
              </Pressable>
              <Text style={styles.hint}>
                Guests can still submit incident reports. Sign in later to attach them to your
                account.
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
  scroll: {
    flexGrow: 1,
    justifyContent: "center",
    padding: spacing.lg,
    paddingVertical: 48,
  },
  hero: { marginBottom: spacing.lg },
  brand: {
    color: "#E8F5EF",
    fontSize: 40,
    fontWeight: "800",
    letterSpacing: 3,
  },
  title: {
    color: "#fff",
    fontSize: 28,
    fontWeight: "700",
    marginTop: 8,
  },
  subtitle: {
    color: "#C9DED4",
    fontSize: 15,
    lineHeight: 22,
    marginTop: spacing.sm,
    maxWidth: 320,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: spacing.lg,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 16,
    elevation: 4,
  },
  label: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  mt: { marginTop: spacing.md },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === "ios" ? 14 : 12,
    fontSize: 16,
    color: colors.text,
    backgroundColor: "#FAFCFA",
  },
  passwordRow: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    backgroundColor: "#FAFCFA",
  },
  passwordInput: {
    flex: 1,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === "ios" ? 14 : 12,
    fontSize: 16,
    color: colors.text,
  },
  showBtn: {
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  showBtnText: {
    color: colors.brand,
    fontSize: 14,
    fontWeight: "700",
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "center",
    marginBottom: spacing.sm,
  },
  avatarText: {
    color: "#fff",
    fontSize: 22,
    fontWeight: "700",
  },
  signedInLabel: {
    textAlign: "center",
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
  },
  signedInName: {
    textAlign: "center",
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
    marginTop: 4,
  },
  signedInEmail: {
    textAlign: "center",
    color: colors.muted,
    fontSize: 14,
    marginTop: 2,
  },
  error: {
    color: colors.danger,
    marginTop: spacing.md,
    fontSize: 13,
    lineHeight: 18,
  },
  btn: {
    marginTop: spacing.lg,
    backgroundColor: colors.brand,
    borderRadius: 12,
    paddingVertical: 15,
    alignItems: "center",
  },
  btnDisabled: { opacity: 0.65 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  registerBtn: {
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.brand,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    backgroundColor: "#EEF6F1",
  },
  registerText: { color: colors.brand, fontSize: 15, fontWeight: "700" },
  registerHint: {
    marginTop: 8,
    color: colors.muted,
    fontSize: 12,
    textAlign: "center",
  },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.lg,
    gap: 10,
  },
  dividerLine: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.border,
  },
  dividerText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
  },
  guestBtn: {
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingVertical: 15,
    alignItems: "center",
    backgroundColor: "#FAFCFA",
  },
  guestText: { color: colors.brand, fontSize: 15, fontWeight: "700" },
  hint: {
    marginTop: spacing.md,
    color: colors.muted,
    fontSize: 12,
    lineHeight: 17,
    textAlign: "center",
  },
});
