import * as ImagePicker from "expo-image-picker";
import * as Location from "expo-location";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { classifyIncident } from "../api";
import { useAuth } from "../AuthContext";
import { colors, spacing } from "../theme";

export default function CaptureScreen({ navigation }) {
  const { token } = useAuth();
  const [photo, setPhoto] = useState(null);
  const [notes, setNotes] = useState("");
  const [locationText, setLocationText] = useState("");
  const [coords, setCoords] = useState(null);
  const [busy, setBusy] = useState(false);
  const [locBusy, setLocBusy] = useState(false);
  const [error, setError] = useState("");

  async function pick(fromCamera) {
    setError("");
    const permission = fromCamera
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setError(fromCamera ? "Camera permission is required." : "Gallery permission is required.");
      return;
    }
    const result = fromCamera
      ? await ImagePicker.launchCameraAsync({
          quality: 0.85,
          allowsEditing: false,
          exif: false,
        })
      : await ImagePicker.launchImageLibraryAsync({
          quality: 0.85,
          allowsEditing: false,
          mediaTypes: ["images"],
        });
    if (result.canceled || !result.assets?.length) return;
    const asset = result.assets[0];
    setPhoto({
      uri: asset.uri,
      name: asset.fileName || `incident_${Date.now()}.jpg`,
      type: asset.mimeType || "image/jpeg",
    });
  }

  async function attachLocation() {
    setLocBusy(true);
    setError("");
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        setError("Location permission was denied.");
        return;
      }
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
      if (!locationText) {
        setLocationText(
          `${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}`,
        );
      }
    } catch (err) {
      setError(err.message || "Could not read location.");
    } finally {
      setLocBusy(false);
    }
  }

  async function submit() {
    if (!photo) {
      setError("Capture or choose a photo first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await classifyIncident(token, {
        uri: photo.uri,
        name: photo.name,
        type: photo.type,
        notes,
        locationText,
        latitude: coords?.latitude,
        longitude: coords?.longitude,
      });
      setPhoto(null);
      setNotes("");
      setLocationText("");
      setCoords(null);
      navigation.navigate("Result", { id: result.id, preview: result });
    } catch (err) {
      setError(err.message || "Report failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.heading}>Report an incident</Text>
      <Text style={styles.lead}>
        Take or pick one photo. The system classifies it and adds it to the classification log.
      </Text>

      <View style={styles.previewBox}>
        {photo ? (
          <Image source={{ uri: photo.uri }} style={styles.preview} />
        ) : (
          <Text style={styles.previewEmpty}>No photo yet</Text>
        )}
      </View>

      <View style={styles.row}>
        <Pressable style={styles.secondary} onPress={() => pick(true)}>
          <Text style={styles.secondaryText}>Camera</Text>
        </Pressable>
        <Pressable style={styles.secondary} onPress={() => pick(false)}>
          <Text style={styles.secondaryText}>Gallery</Text>
        </Pressable>
      </View>

      <Text style={styles.label}>What happened (optional)</Text>
      <TextInput
        style={[styles.input, styles.multiline]}
        multiline
        value={notes}
        onChangeText={setNotes}
        placeholder="Short description for responders / reviewers"
        placeholderTextColor={colors.muted}
      />

      <Text style={styles.label}>Location (optional)</Text>
      <TextInput
        style={styles.input}
        value={locationText}
        onChangeText={setLocationText}
        placeholder="Landmark or address"
        placeholderTextColor={colors.muted}
      />
      <Pressable style={styles.linkBtn} onPress={attachLocation} disabled={locBusy}>
        {locBusy ? (
          <ActivityIndicator color={colors.brand} />
        ) : (
          <Text style={styles.linkText}>
            {coords ? "GPS attached — tap to refresh" : "Use current GPS"}
          </Text>
        )}
      </Pressable>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable style={[styles.primary, busy && styles.disabled]} onPress={submit} disabled={busy}>
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.primaryText}>Classify & report</Text>
        )}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, paddingBottom: 48 },
  heading: { fontSize: 28, fontWeight: "800", color: colors.text },
  lead: { color: colors.muted, marginTop: 6, marginBottom: spacing.lg, lineHeight: 20 },
  previewBox: {
    height: 260,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  preview: { width: "100%", height: "100%" },
  previewEmpty: { color: colors.muted },
  row: { flexDirection: "row", gap: 10, marginTop: spacing.md },
  secondary: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  secondaryText: { color: colors.brand, fontWeight: "700" },
  label: { marginTop: spacing.lg, marginBottom: 6, color: colors.muted, fontWeight: "600", fontSize: 13 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.text,
    fontSize: 16,
  },
  multiline: { minHeight: 90, textAlignVertical: "top" },
  linkBtn: { marginTop: spacing.sm, paddingVertical: 8 },
  linkText: { color: colors.brandSoft, fontWeight: "600" },
  error: { color: colors.danger, marginTop: spacing.md },
  primary: {
    marginTop: spacing.lg,
    backgroundColor: colors.accent,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
  },
  disabled: { opacity: 0.7 },
  primaryText: { color: "#fff", fontWeight: "800", fontSize: 16 },
});
