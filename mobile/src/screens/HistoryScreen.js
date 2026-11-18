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
import { resolveImageUri } from "../config";
import { colors, spacing } from "../theme";

function pct(value) {
  if (value == null) return "";
  return `${(Number(value) * 100).toFixed(0)}%`;
}

function formatWhen(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
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
          <Text style={styles.kicker}>History</Text>
          <Text style={styles.heading}>My reports</Text>
          <Text style={styles.sub}>Sign in to see reports linked to your account.</Text>
        </View>

        <View style={styles.guestCard}>
          <View style={styles.guestIcon}>
            <Text style={styles.guestIconText}>EIC</Text>
          </View>
          <Text style={styles.guestTitle}>Reporting as guest</Text>
          <Text style={styles.guestLead}>
            You can still submit incidents without an account. Sign in to keep a personal history
            here.
          </Text>
          <Pressable
            style={styles.primary}
            onPress={() => navigation.navigate("Login")}
            accessibilityRole="button"
            accessibilityLabel="Sign in"
          >
            <Text style={styles.primaryText}>Sign in</Text>
          </Pressable>
          <Pressable
            style={styles.secondary}
            onPress={() => navigation.navigate("Register")}
            accessibilityRole="button"
            accessibilityLabel="Create resident account"
          >
            <Text style={styles.secondaryText}>Create resident account</Text>
          </Pressable>
          <Pressable
            style={styles.linkBtn}
            onPress={() => navigation.navigate("ReportTab")}
            accessibilityRole="button"
            accessibilityLabel="Report an incident"
          >
            <Text style={styles.linkText}>Report an incident as guest</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  const displayName = user?.name || user?.username || user?.email || "Account";

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View style={styles.headerText}>
            <Text style={styles.kicker}>History</Text>
            <Text style={styles.heading}>My reports</Text>
            <Text style={styles.sub} numberOfLines={1}>
              {displayName}
            </Text>
          </View>
          <Pressable
            style={styles.signOutBtn}
            onPress={signOut}
            accessibilityRole="button"
            accessibilityLabel="Sign out"
          >
            <Text style={styles.signOut}>Sign out</Text>
          </Pressable>
        </View>
      </View>

      {busy && !items.length ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.brand} size="large" />
          <Text style={styles.loadingText}>Loading reports…</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={busy} onRefresh={load} tintColor={colors.brand} />
          }
          ListEmptyComponent={
            <View style={styles.emptyCard}>
              {error ? (
                <>
                  <Text style={styles.emptyTitle}>Couldn’t load reports</Text>
                  <Text style={styles.emptyBody}>{error}</Text>
                  <Pressable style={styles.secondary} onPress={load}>
                    <Text style={styles.secondaryText}>Try again</Text>
                  </Pressable>
                </>
              ) : (
                <>
                  <Text style={styles.emptyTitle}>No reports yet</Text>
                  <Text style={styles.emptyBody}>
                    Capture an incident photo to start your history.
                  </Text>
                  <Pressable
                    style={styles.primary}
                    onPress={() => navigation.navigate("ReportTab")}
                  >
                    <Text style={styles.primaryText}>Report an incident</Text>
                  </Pressable>
                </>
              )}
            </View>
          }
          renderItem={({ item }) => {
            const label = item.predicted_label_name || item.status || "Pending";
            const confidence = item.confidence != null ? pct(item.confidence) : "";
            const place = item.location_text || "";
            const when = formatWhen(item.created_at);

            return (
              <Pressable
                style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
                onPress={() => navigation.navigate("Result", { id: item.id })}
                accessibilityRole="button"
                accessibilityLabel={`Open report ${item.record_no || item.id}`}
              >
                {item.image_url ? (
                  <Image
                    source={{ uri: resolveImageUri(item.image_url) }}
                    style={styles.thumb}
                  />
                ) : (
                  <View style={[styles.thumb, styles.thumbEmpty]}>
                    <Text style={styles.thumbEmptyText}>No photo</Text>
                  </View>
                )}
                <View style={styles.meta}>
                  <View style={styles.metaTop}>
                    <Text style={styles.record} numberOfLines={1}>
                      {item.record_no || `#${item.id}`}
                    </Text>
                    {confidence ? (
                      <View style={styles.badge}>
                        <Text style={styles.badgeText}>{confidence}</Text>
                      </View>
                    ) : null}
                  </View>
                  <Text style={styles.label} numberOfLines={1}>
                    {label}
                  </Text>
                  {place ? (
                    <Text style={styles.place} numberOfLines={1}>
                      {place}
                    </Text>
                  ) : null}
                  {when ? (
                    <Text style={styles.when} numberOfLines={1}>
                      {when}
                    </Text>
                  ) : null}
                </View>
              </Pressable>
            );
          }}
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
    paddingBottom: spacing.md,
  },
  headerTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  headerText: { flex: 1 },
  kicker: {
    color: colors.brandSoft,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.2,
    textTransform: "uppercase",
  },
  heading: {
    fontSize: 28,
    fontWeight: "800",
    color: colors.text,
    marginTop: 6,
  },
  sub: {
    color: colors.muted,
    marginTop: 6,
    fontSize: 15,
    lineHeight: 20,
  },
  signOutBtn: {
    marginTop: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  signOut: {
    color: colors.brand,
    fontWeight: "700",
    fontSize: 13,
  },

  guestCard: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: 18,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: "#0B3D2E",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
    alignItems: "center",
  },
  guestIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  guestIconText: {
    color: "#E8F5EF",
    fontWeight: "800",
    fontSize: 14,
    letterSpacing: 1,
  },
  guestTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.text,
    textAlign: "center",
  },
  guestLead: {
    color: colors.muted,
    lineHeight: 22,
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
    textAlign: "center",
    fontSize: 15,
  },

  loading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingBottom: 40,
  },
  loadingText: {
    marginTop: spacing.md,
    color: colors.muted,
    fontSize: 14,
  },

  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: 48,
    paddingTop: spacing.xs,
    flexGrow: 1,
  },

  emptyCard: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    marginTop: spacing.md,
  },
  emptyTitle: {
    fontSize: 17,
    fontWeight: "700",
    color: colors.text,
    textAlign: "center",
  },
  emptyBody: {
    color: colors.muted,
    textAlign: "center",
    marginTop: 8,
    marginBottom: spacing.lg,
    lineHeight: 21,
    fontSize: 14,
  },

  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
    marginBottom: 12,
    shadowColor: "#0B3D2E",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 1,
  },
  cardPressed: {
    opacity: 0.92,
    transform: [{ scale: 0.995 }],
  },
  thumb: {
    width: 92,
    height: 108,
    backgroundColor: colors.border,
  },
  thumbEmpty: {
    backgroundColor: "#EEF3F0",
    alignItems: "center",
    justifyContent: "center",
  },
  thumbEmptyText: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "600",
  },
  meta: {
    flex: 1,
    paddingHorizontal: 14,
    paddingVertical: 12,
    justifyContent: "center",
  },
  metaTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  record: {
    flex: 1,
    fontWeight: "800",
    color: colors.text,
    fontSize: 15,
  },
  badge: {
    backgroundColor: "#EEF6F1",
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: "#C8DED3",
  },
  badgeText: {
    color: colors.brand,
    fontSize: 11,
    fontWeight: "700",
  },
  label: {
    marginTop: 4,
    color: colors.brand,
    fontWeight: "700",
    fontSize: 14,
  },
  place: {
    marginTop: 4,
    color: colors.text,
    fontSize: 13,
  },
  when: {
    marginTop: 4,
    color: colors.muted,
    fontSize: 12,
  },

  primary: {
    backgroundColor: colors.brand,
    borderRadius: 14,
    paddingVertical: 15,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    alignSelf: "stretch",
  },
  primaryText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  secondary: {
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "#FAFCFA",
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    alignSelf: "stretch",
  },
  secondaryText: { color: colors.brand, fontWeight: "700", fontSize: 15 },
  linkBtn: { marginTop: spacing.md, paddingVertical: 8 },
  linkText: { color: colors.brandSoft, fontWeight: "600", fontSize: 14, textAlign: "center" },
});
