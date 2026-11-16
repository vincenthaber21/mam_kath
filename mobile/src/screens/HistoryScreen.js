import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { fetchClassifications } from "../api";
import { useAuth } from "../AuthContext";
import { colors, spacing } from "../theme";

function pct(value) {
  if (value == null) return "";
  return `${(Number(value) * 100).toFixed(0)}%`;
}

export default function HistoryScreen({ navigation }) {
  const { token, user, isSignedIn, signOut } = useAuth();
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!token) {
      setItems([]);
      setBusy(false);
      setError("");
      return;
    }
    setError("");
    try {
      const data = await fetchClassifications(token, 1);
      setItems(data.results || []);
    } catch (err) {
      setError(err.message || "Could not load reports.");
    } finally {
      setBusy(false);
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      setBusy(true);
      load();
    }, [load]),
  );

  if (!isSignedIn) {
    return (
      <View style={styles.root}>
        <View style={styles.header}>
          <View>
            <Text style={styles.heading}>My reports</Text>
            <Text style={styles.sub}>Sign in to see your history</Text>
          </View>
        </View>
        <View style={styles.guestBox}>
          <Text style={styles.guestLead}>
            You can report incidents without an account. Sign in only if you want reports linked to you
            and listed here.
          </Text>
          <Pressable style={styles.primary} onPress={() => navigation.navigate("Login")}>
            <Text style={styles.primaryText}>Sign in</Text>
          </Pressable>
          <Pressable style={styles.linkBtn} onPress={() => navigation.navigate("ReportTab")}>
            <Text style={styles.linkText}>Report an incident now</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View>
          <Text style={styles.heading}>My reports</Text>
          <Text style={styles.sub}>{user?.name || user?.email}</Text>
        </View>
        <Pressable onPress={signOut}>
          <Text style={styles.signOut}>Sign out</Text>
        </Pressable>
      </View>

      {busy && !items.length ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.brand} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={busy} onRefresh={load} tintColor={colors.brand} />}
          ListEmptyComponent={
            <Text style={styles.empty}>{error || "No reports yet. Capture an incident photo to begin."}</Text>
          }
          renderItem={({ item }) => (
            <Pressable
              style={styles.card}
              onPress={() => navigation.navigate("Result", { id: item.id })}
            >
              {item.image_url ? (
                <Image source={{ uri: item.image_url }} style={styles.thumb} />
              ) : (
                <View style={[styles.thumb, styles.thumbEmpty]} />
              )}
              <View style={styles.meta}>
                <Text style={styles.record}>{item.record_no}</Text>
                <Text style={styles.label}>
                  {item.predicted_label_name || item.status}
                  {item.confidence != null ? ` · ${pct(item.confidence)}` : ""}
                </Text>
                <Text style={styles.when} numberOfLines={1}>
                  {item.location_text || item.notes || item.created_at}
                </Text>
              </View>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  heading: { fontSize: 28, fontWeight: "800", color: colors.text },
  sub: { color: colors.muted, marginTop: 2 },
  signOut: { color: colors.accent, fontWeight: "700", marginTop: 8 },
  guestBox: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  guestLead: { color: colors.muted, lineHeight: 22, marginBottom: spacing.lg },
  primary: {
    backgroundColor: colors.brand,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
  },
  primaryText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  linkBtn: { marginTop: spacing.md, alignItems: "center", padding: 8 },
  linkText: { color: colors.brandSoft, fontWeight: "600" },
  list: { padding: spacing.lg, paddingTop: spacing.sm, gap: 10 },
  empty: { color: colors.muted, textAlign: "center", marginTop: 40, lineHeight: 22 },
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
    marginBottom: 10,
  },
  thumb: { width: 84, height: 84, backgroundColor: colors.border },
  thumbEmpty: { backgroundColor: "#E2EAE5" },
  meta: { flex: 1, padding: 12, justifyContent: "center" },
  record: { fontWeight: "800", color: colors.text },
  label: { marginTop: 2, color: colors.brand, fontWeight: "700" },
  when: { marginTop: 4, color: colors.muted, fontSize: 12 },
});
