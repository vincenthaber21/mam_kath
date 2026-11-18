import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { useAuth } from "../AuthContext";
import { barangayOptions } from "../barangays";
import { colors, spacing } from "../theme";

function Field({
  label,
  value,
  onChangeText,
  placeholder,
  secureTextEntry,
  keyboardType,
  autoComplete,
  textContentType,
  autoCapitalize = "none",
  editable = true,
  hint,
  required,
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>
        {label}
        {required ? <Text style={styles.required}> *</Text> : null}
      </Text>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.muted}
        secureTextEntry={secureTextEntry}
        keyboardType={keyboardType}
        autoComplete={autoComplete}
        textContentType={textContentType}
        autoCapitalize={autoCapitalize}
        autoCorrect={false}
        editable={editable}
        accessibilityLabel={label}
      />
      {hint ? <Text style={styles.fieldHint}>{hint}</Text> : null}
    </View>
  );
}

export default function RegisterScreen({ navigation }) {
  const { register, isSignedIn } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [barangay, setBarangay] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const pickerData = useMemo(() => barangayOptions(barangay), [barangay]);

  function clearErrors() {
    if (error) setError("");
    if (Object.keys(fieldErrors).length) setFieldErrors({});
  }

  function validateLocal() {
    const next = {};
    if (!firstName.trim()) next.first_name = ["Enter your first name."];
    if (!lastName.trim()) next.last_name = ["Enter your last name."];
    if (!username.trim()) next.username = ["Enter a username."];
    if (!email.trim()) next.email = ["Enter your email address."];
    if (!barangay) next.barangay = ["Select your barangay in Santa Maria."];
    if (!password) next.password = ["Enter a password."];
    else if (password.length < 8) next.password = ["Password must be at least 8 characters."];
    if (password !== passwordConfirm) {
      next.password_confirm = ["The two password fields did not match."];
    }
    return next;
  }

  async function onSubmit() {
    if (isSignedIn) {
      setError("You are already signed in. Sign out first to create another account.");
      return;
    }
    const local = validateLocal();
    if (Object.keys(local).length) {
      setFieldErrors(local);
      setError(Object.values(local)[0][0]);
      return;
    }

    setBusy(true);
    setError("");
    setFieldErrors({});
    try {
      await register({
        first_name: firstName.trim(),
        middle_name: middleName.trim(),
        last_name: lastName.trim(),
        username: username.trim(),
        email: email.trim(),
        phone: phone.trim(),
        barangay,
        password,
        password_confirm: passwordConfirm,
      });
      navigation.navigate("Main");
    } catch (err) {
      const fields = err?.body?.fields || {};
      setFieldErrors(fields);
      setError(err.message || "Could not create your account. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function fieldMessage(key) {
    const msgs = fieldErrors[key];
    if (!msgs?.length) return null;
    return <Text style={styles.fieldError}>{msgs[0]}</Text>;
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
          <Text style={styles.title}>Create resident account</Text>
          <Text style={styles.subtitle}>
            For residents of Santa Maria, Ilocos Sur. Reports you submit will be saved under your
            name.
          </Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.section}>Personal details</Text>

          <Field
            label="First name"
            required
            value={firstName}
            onChangeText={(v) => {
              setFirstName(v);
              clearErrors();
            }}
            placeholder="e.g. Juan"
            autoCapitalize="words"
            autoComplete="given-name"
            textContentType="givenName"
            editable={!busy}
          />
          {fieldMessage("first_name")}

          <Field
            label="Middle name"
            value={middleName}
            onChangeText={(v) => {
              setMiddleName(v);
              clearErrors();
            }}
            placeholder="Optional"
            autoCapitalize="words"
            autoComplete="additional-name"
            textContentType="middleName"
            editable={!busy}
          />

          <Field
            label="Last name"
            required
            value={lastName}
            onChangeText={(v) => {
              setLastName(v);
              clearErrors();
            }}
            placeholder="e.g. Dela Cruz"
            autoCapitalize="words"
            autoComplete="family-name"
            textContentType="familyName"
            editable={!busy}
          />
          {fieldMessage("last_name")}

          <Text style={[styles.section, styles.sectionGap]}>Account</Text>

          <Field
            label="Username"
            required
            value={username}
            onChangeText={(v) => {
              setUsername(v);
              clearErrors();
            }}
            placeholder="e.g. juan.delacruz"
            autoComplete="username"
            textContentType="username"
            hint="Letters, numbers, dots, underscores, or hyphens"
            editable={!busy}
          />
          {fieldMessage("username")}

          <Field
            label="Email"
            required
            value={email}
            onChangeText={(v) => {
              setEmail(v);
              clearErrors();
            }}
            placeholder="you@example.com"
            keyboardType="email-address"
            autoComplete="email"
            textContentType="emailAddress"
            editable={!busy}
          />
          {fieldMessage("email")}

          <Field
            label="Phone"
            value={phone}
            onChangeText={(v) => {
              setPhone(v);
              clearErrors();
            }}
            placeholder="Optional mobile number"
            keyboardType="phone-pad"
            autoComplete="tel"
            textContentType="telephoneNumber"
            editable={!busy}
          />

          <View style={styles.field}>
            <Text style={styles.label}>
              Barangay <Text style={styles.required}>*</Text>
            </Text>
            <Pressable
              style={[styles.input, styles.selectRow]}
              onPress={() => setPickerOpen(true)}
              disabled={busy}
              accessibilityRole="button"
              accessibilityLabel="Select barangay"
            >
              <Text style={barangay ? styles.selectValue : styles.selectPlaceholder}>
                {barangay || "Select your barangay"}
              </Text>
              <Text style={styles.chevron}>▾</Text>
            </Pressable>
            <Text style={styles.fieldHint}>Must be a barangay in Santa Maria</Text>
            {fieldMessage("barangay")}
          </View>

          <Text style={[styles.section, styles.sectionGap]}>Password</Text>

          <View style={styles.field}>
            <Text style={styles.label}>
              Password <Text style={styles.required}>*</Text>
            </Text>
            <View style={styles.passwordRow}>
              <TextInput
                style={styles.passwordInput}
                value={password}
                onChangeText={(v) => {
                  setPassword(v);
                  clearErrors();
                }}
                placeholder="At least 8 characters"
                placeholderTextColor={colors.muted}
                secureTextEntry={!showPassword}
                autoComplete="new-password"
                textContentType="newPassword"
                editable={!busy}
                accessibilityLabel="Password"
              />
              <Pressable
                style={styles.showBtn}
                onPress={() => setShowPassword((v) => !v)}
                hitSlop={8}
              >
                <Text style={styles.showBtnText}>{showPassword ? "Hide" : "Show"}</Text>
              </Pressable>
            </View>
            {fieldMessage("password")}
          </View>

          <Field
            label="Confirm password"
            required
            value={passwordConfirm}
            onChangeText={(v) => {
              setPasswordConfirm(v);
              clearErrors();
            }}
            placeholder="Re-enter password"
            secureTextEntry={!showPassword}
            autoComplete="new-password"
            textContentType="newPassword"
            editable={!busy}
          />
          {fieldMessage("password_confirm")}

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Pressable
            style={[styles.btn, busy && styles.btnDisabled]}
            onPress={onSubmit}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Create account"
          >
            {busy ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.btnText}>Create account</Text>
            )}
          </Pressable>

          <Pressable
            style={styles.linkBtn}
            onPress={() => navigation.goBack()}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Back to sign in"
          >
            <Text style={styles.linkText}>Already have an account? Sign in</Text>
          </Pressable>
        </View>
      </ScrollView>

      <Modal
        visible={pickerOpen}
        animationType="slide"
        transparent
        onRequestClose={() => setPickerOpen(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHandle} />
            <Text style={styles.modalTitle}>Select barangay</Text>
            <Text style={styles.modalSubtitle}>Santa Maria, Ilocos Sur</Text>
            <FlatList
              data={pickerData}
              keyExtractor={(item) => item}
              keyboardShouldPersistTaps="handled"
              renderItem={({ item }) => {
                const active = item === barangay;
                return (
                  <Pressable
                    style={[styles.option, active && styles.optionActive]}
                    onPress={() => {
                      setBarangay(item);
                      clearErrors();
                      setPickerOpen(false);
                    }}
                  >
                    <Text style={[styles.optionText, active && styles.optionTextActive]}>
                      {item}
                    </Text>
                    {active ? <Text style={styles.optionCheck}>✓</Text> : null}
                  </Pressable>
                );
              }}
            />
            <Pressable style={styles.modalClose} onPress={() => setPickerOpen(false)}>
              <Text style={styles.secondaryText}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.brand },
  scroll: {
    flexGrow: 1,
    padding: spacing.lg,
    paddingVertical: 40,
  },
  hero: { marginBottom: spacing.lg },
  brand: {
    color: "#E8F5EF",
    fontSize: 36,
    fontWeight: "800",
    letterSpacing: 3,
  },
  title: {
    color: "#fff",
    fontSize: 26,
    fontWeight: "700",
    marginTop: 8,
  },
  subtitle: {
    color: "#C9DED4",
    fontSize: 15,
    lineHeight: 22,
    marginTop: spacing.sm,
    maxWidth: 340,
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
  section: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.sm,
  },
  sectionGap: { marginTop: spacing.lg },
  field: { marginBottom: spacing.md },
  label: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  required: { color: colors.accent },
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
  fieldHint: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 6,
    lineHeight: 16,
  },
  fieldError: {
    color: colors.danger,
    fontSize: 12,
    marginTop: -8,
    marginBottom: spacing.sm,
    lineHeight: 16,
  },
  selectRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  selectValue: { color: colors.text, fontSize: 16, flex: 1, paddingRight: 8 },
  selectPlaceholder: {
    color: colors.muted,
    fontSize: 16,
    flex: 1,
    paddingRight: 8,
  },
  chevron: { color: colors.muted, fontSize: 16 },
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
  showBtn: { paddingHorizontal: 14, paddingVertical: 12 },
  showBtnText: { color: colors.brand, fontSize: 14, fontWeight: "700" },
  error: {
    color: colors.danger,
    marginBottom: spacing.sm,
    fontSize: 13,
    lineHeight: 18,
  },
  btn: {
    marginTop: spacing.sm,
    backgroundColor: colors.brand,
    borderRadius: 12,
    paddingVertical: 15,
    alignItems: "center",
  },
  btnDisabled: { opacity: 0.65 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  linkBtn: {
    marginTop: spacing.md,
    paddingVertical: 10,
    alignItems: "center",
  },
  linkText: {
    color: colors.brandSoft,
    fontSize: 14,
    fontWeight: "600",
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.45)",
    justifyContent: "flex-end",
  },
  modalSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "78%",
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
  },
  modalHandle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    marginBottom: spacing.md,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.text,
    paddingHorizontal: spacing.lg,
  },
  modalSubtitle: {
    fontSize: 13,
    color: colors.muted,
    paddingHorizontal: spacing.lg,
    marginTop: 2,
    marginBottom: spacing.md,
  },
  option: {
    paddingHorizontal: spacing.lg,
    paddingVertical: 15,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  optionActive: { backgroundColor: "#EEF6F1" },
  optionText: { color: colors.text, fontSize: 16 },
  optionTextActive: { color: colors.brand, fontWeight: "700" },
  optionCheck: { color: colors.brand, fontWeight: "700", fontSize: 16 },
  modalClose: {
    marginTop: spacing.md,
    marginHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    backgroundColor: "#FAFCFA",
  },
  secondaryText: { color: colors.brand, fontWeight: "700", fontSize: 15 },
});
