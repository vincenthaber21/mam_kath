import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { fetchClassification, verifyClassification } from "../api";
import { useAuth } from "../AuthContext";
import { colors, spacing } from "../theme";

function pct(value) {
  if (value == null) return "—";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

export default function ResultScreen({ route, navigation }) {
  const { token, isSignedIn } = useAuth();
  const [rec, setRec] = useState(route.params?.preview || null);
  const [busy, setBusy] = useState(!route.params?.preview && Boolean(route.params?.id));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const id = route.params?.id;

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!id) {
        if (alive) setBusy(false);
        return;
      }
      // Guests already have the classify response as preview; detail/list need auth.
      if (!token) {
        if (alive) {
          if (!route.params?.preview) setError("Sign in to reload this report.");
          setBusy(false);
        }
        return;
      }
      try {
        const data = await fetchClassification(token, id);
        if (alive) setRec(data);
      } catch (err) {
        if (alive) setError(err.message || "Could not load result.");
      } finally {
        if (alive) setBusy(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [id, token, route.params?.preview]);

  async function confirm(verification) {
    if (!token) {
      setError("Sign in to save a verification.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const data = await verifyClassification(token, id, verification);
      setRec(data);
    } catch (err) {
      setError(err.message || "Could not save verification.");
    } finally {
      setSaving(false);
    }
  }

  if (busy || !rec) {
    return (
      <View style={styles.center}>
        {error ? <Text style={styles.error}>{error}</Text> : <ActivityIndicator color={colors.brand} />}
      </View>
    );
  }

  const failed = rec.status === "failed";

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>Record {rec.record_no}</Text>
      <Text style={styles.heading}>{failed ? "Report saved (failed)" : "Reported to system"}</Text>
      <Text style={styles.lead}>
        {failed
          ? rec.error || "Classification failed, but the attempt is logged."
          : "This incident is now in the website classification log for review."}
      </Text>

      {rec.image_url ? <Image source={{ uri: rec.image_url }} style={styles.image} /> : null}

      {!failed ? (
        <View style={styles.card}>
          <Text style={styles.label}>Predicted category</Text>
          <Text style={styles.prediction}>{rec.predicted_label_name || rec.predicted_label}</Text>
          <View style={styles.stats}>
            <View style={styles.stat}>
              <Text style={styles.label}>Confidence</Text>
              <Text style={styles.statValue}>{pct(rec.confidence)}</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.label}>Inference</Text>
              <Text style={styles.statValue}>
                {rec.inference_ms != null ? `${Math.round(rec.inference_ms)} ms` : "—"}
              </Text>
            </View>
          </View>
          {rec.low_confidence ? (
            <Text style={styles.warn}>Low confidence — please verify before relying on this label.</Text>
          ) : null}
          {rec.notes ? <Text style={styles.meta}>Notes: {rec.notes}</Text> : null}
          {rec.location_text ? <Text style={styles.meta}>Location: {rec.location_text}</Text> : null}
        </View>
      ) : null}

      {!failed && !rec.verification && isSignedIn ? (
        <View style={styles.card}>
          <Text style={styles.label}>Quick verification</Text>
          <View style={styles.row}>
            <Pressable style={[styles.secondary, saving && styles.disabled]} disabled={saving} onPress={() => confirm("correct")}>
              <Text style={styles.secondaryText}>Looks correct</Text>
            </Pressable>
            <Pressable style={[styles.secondary, saving && styles.disabled]} disabled={saving} onPress={() => confirm("unclear")}>
              <Text style={styles.secondaryText}>Unclear</Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      {!failed && !rec.verification && !isSignedIn ? (
        <Text style={styles.meta}>Sign in later if you want to verify this label from My reports.</Text>
      ) : null}

      {rec.verification ? (
        <Text style={styles.ok}>Verification saved: {rec.verification}</Text>
      ) : null}

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable style={styles.primary} onPress={() => navigation.navigate("Capture")}>
        <Text style={styles.primaryText}>Report another</Text>
      </Pressable>
      <Pressable
        style={styles.linkBtn}
        onPress={() => (isSignedIn ? navigation.navigate("History") : navigation.navigate("Login"))}
      >
        <Text style={styles.linkText}>{isSignedIn ? "View my reports" : "Sign in for history"}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, paddingBottom: 48 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  eyebrow: { color: colors.muted, fontWeight: "700", letterSpacing: 0.4 },
  heading: { fontSize: 28, fontWeight: "800", color: colors.text, marginTop: 4 },
  lead: { color: colors.muted, marginTop: 6, marginBottom: spacing.lg, lineHeight: 20 },
  image: { width: "100%", height: 240, borderRadius: 16, backgroundColor: colors.border },
  card: {
    marginTop: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  label: { color: colors.muted, fontSize: 12, fontWeight: "700", textTransform: "uppercase" },
  prediction: { fontSize: 30, fontWeight: "800", color: colors.brand, marginTop: 6 },
  stats: { flexDirection: "row", gap: 16, marginTop: spacing.md },
  stat: { flex: 1 },
  statValue: { fontSize: 20, fontWeight: "700", color: colors.text, marginTop: 4 },
  warn: { marginTop: spacing.md, color: colors.warning, fontWeight: "600" },
  meta: { marginTop: spacing.sm, color: colors.text, lineHeight: 20 },
  row: { flexDirection: "row", gap: 10, marginTop: spacing.md },
  secondary: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: "#FAFCFA",
  },
  secondaryText: { color: colors.brand, fontWeight: "700" },
  disabled: { opacity: 0.6 },
  ok: { marginTop: spacing.md, color: colors.success, fontWeight: "700" },
  error: { color: colors.danger, marginTop: spacing.md },
  primary: {
    marginTop: spacing.lg,
    backgroundColor: colors.brand,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
  },
  primaryText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  linkBtn: { marginTop: spacing.md, alignItems: "center", padding: 8 },
  linkText: { color: colors.brandSoft, fontWeight: "600" },
});
