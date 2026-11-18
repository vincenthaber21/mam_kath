import * as ImagePicker from "expo-image-picker";
import * as Location from "expo-location";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { classifyIncident } from "../api";
import { useAuth } from "../AuthContext";
import { barangayOptions, normalizeBarangay, resolveBarangayFromGps } from "../barangays";
import { colors, spacing } from "../theme";

function formatCoords(coords) {
  if (!coords) return "";
  return `${Number(coords.latitude).toFixed(5)}, ${Number(coords.longitude).toFixed(5)}`;
}

export default function CaptureScreen({ navigation }) {
  const { token, clearSession, user } = useAuth();
  const profileBarangay = normalizeBarangay(user?.barangay || "");
  const [photo, setPhoto] = useState(null);
  const [notes, setNotes] = useState("");
  const [locationText, setLocationText] = useState(profileBarangay);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [coords, setCoords] = useState(null);
  const [gpsBarangay, setGpsBarangay] = useState("");
  const [gpsStatus, setGpsStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [locBusy, setLocBusy] = useState(false);
  const [error, setError] = useState("");

  // After sign-in, adopt profile barangay when the field is still empty.
  useEffect(() => {
    if (!profileBarangay) return;
    setLocationText((current) => current || profileBarangay);
  }, [profileBarangay]);

  const pickerData = useMemo(
    () => barangayOptions(locationText || profileBarangay),
    [locationText, profileBarangay],
  );

  async function readGps({ fillBarangay = true } = {}) {
    const enabled = await Location.hasServicesEnabledAsync();
    if (!enabled) {
      throw new Error("Turn on Location / GPS on this device, then try again.");
    }
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") {
      throw new Error("Location permission was denied. Enable it in system settings.");
    }

    let pos = null;
    try {
      pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
        mayShowUserSettingsDialog: true,
      });
    } catch {
      // Emulators / brief GPS gaps: fall back to a recent cached fix.
      pos = await Location.getLastKnownPositionAsync({
        maxAge: 5 * 60 * 1000,
        requiredAccuracy: 500,
      });
    }
    if (!pos?.coords) {
      throw new Error("Could not get a GPS fix. Move outdoors or enable Location, then try again.");
    }
    const next = {
      latitude: pos.coords.latitude,
      longitude: pos.coords.longitude,
    };

    let places = null;
    try {
      places = await Location.reverseGeocodeAsync(next);
    } catch {
      // Nearest-centroid fallback still works without reverse geocode.
    }
    const matched = resolveBarangayFromGps(next, places);
    if (fillBarangay && matched) {
      setLocationText(matched);
    }
    setGpsBarangay(matched);
    setCoords(next);
    setGpsStatus(
      matched
        ? `Location attached · ${formatCoords(next)}`
        : `Location attached · ${formatCoords(next)} — barangay not detected`,
    );
    return { coords: next, matched };
  }

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
    setGpsStatus("Reading location…");
    try {
      await readGps({ fillBarangay: true });
    } catch (err) {
      setGpsStatus("");
      setError(err.message || "Could not read location.");
    } finally {
      setLocBusy(false);
    }
  }

  function clearGps() {
    setCoords(null);
    setGpsBarangay("");
    setGpsStatus("");
  }

  async function submit() {
    if (!photo) {
      setError("Add a photo to continue.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      // Prefer an already-attached fix; otherwise grab GPS once so the report can pin on the map.
      let submitCoords = coords;
      let submitBarangay = locationText;
      if (!submitCoords) {
        try {
          setGpsStatus("Reading location…");
          const gps = await readGps({ fillBarangay: !submitBarangay });
          submitCoords = gps.coords;
          if (gps.matched) submitBarangay = gps.matched;
        } catch {
          // GPS is optional — still submit photo + barangay without coordinates.
          setGpsStatus("");
        }
      }

      const result = await classifyIncident(token, {
        uri: photo.uri,
        name: photo.name,
        type: photo.type,
        notes,
        locationText: normalizeBarangay(submitBarangay),
        latitude: submitCoords?.latitude,
        longitude: submitCoords?.longitude,
      });
      const localImageUri = photo.uri;
      setPhoto(null);
      setNotes("");
      setLocationText(profileBarangay);
      setCoords(null);
      setGpsBarangay("");
      setGpsStatus("");
      navigation.navigate("Result", {
        id: result.id,
        preview: result,
        localImageUri,
      });
    } catch (err) {
      if (err?.status === 401 && token) {
        // Token was rejected (or Dev Tunnel blocked Bearer); keep reporting as guest.
        await clearSession();
      }
      setError(err.message || "Report failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.header}>
        <Text style={styles.kicker}>Incident report</Text>
        <Text style={styles.heading}>Capture & submit</Text>
        <Text style={styles.lead}>
          Add a photo, then optionally note what happened and where.
        </Text>
      </View>

      {/* Photo */}
      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Photo</Text>
        <Text style={styles.sectionHint}>Required · Take a new photo or choose from gallery</Text>

        <View style={[styles.previewBox, photo && styles.previewBoxFilled]}>
          {photo ? (
            <>
              <Image source={{ uri: photo.uri }} style={styles.preview} />
              <Pressable
                style={styles.removePhoto}
                onPress={() => setPhoto(null)}
                accessibilityRole="button"
                accessibilityLabel="Remove photo"
              >
                <Text style={styles.removePhotoText}>Remove</Text>
              </Pressable>
            </>
          ) : (
            <View style={styles.previewEmpty}>
              <View style={styles.previewIcon}>
                <Text style={styles.previewIconText}>+</Text>
              </View>
              <Text style={styles.previewEmptyTitle}>No photo yet</Text>
              <Text style={styles.previewEmptyHint}>Use the camera or gallery below</Text>
            </View>
          )}
        </View>

        <View style={styles.row}>
          <Pressable
            style={styles.secondary}
            onPress={() => pick(true)}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Take photo with camera"
          >
            <Text style={styles.secondaryText}>Camera</Text>
          </Pressable>
          <Pressable
            style={styles.secondary}
            onPress={() => pick(false)}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Choose photo from gallery"
          >
            <Text style={styles.secondaryText}>Gallery</Text>
          </Pressable>
        </View>
      </View>

      {/* Details */}
      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Details</Text>
        <Text style={styles.sectionHint}>Optional · Helps responders understand the scene</Text>

        <Text style={styles.label}>What happened</Text>
        <TextInput
          style={[styles.input, styles.multiline]}
          multiline
          value={notes}
          onChangeText={setNotes}
          placeholder="Short description for responders"
          placeholderTextColor={colors.muted}
          editable={!busy}
          accessibilityLabel="What happened"
        />
      </View>

      {/* Location */}
      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Location</Text>
        <Text style={styles.sectionHint}>Optional · Santa Maria barangay and GPS</Text>

        <Text style={styles.label}>Barangay</Text>
        <Pressable
          style={[styles.input, styles.selectRow]}
          onPress={() => setPickerOpen(true)}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="Select barangay"
        >
          <Text style={locationText ? styles.selectValue : styles.selectPlaceholder}>
            {locationText || "Select barangay"}
          </Text>
          <Text style={styles.chevron}>▾</Text>
        </Pressable>

        {locationText ? (
          <Pressable
            style={styles.linkBtn}
            onPress={() => setLocationText("")}
            accessibilityRole="button"
            accessibilityLabel="Clear barangay"
          >
            <Text style={styles.linkText}>Clear barangay</Text>
          </Pressable>
        ) : null}

        <View style={styles.gpsBlock}>
          <Pressable
            style={[styles.gpsBtn, (locBusy || busy) && styles.disabled]}
            onPress={attachLocation}
            disabled={locBusy || busy}
            accessibilityRole="button"
            accessibilityLabel={coords ? "Refresh GPS" : "Use current GPS"}
          >
            {locBusy ? (
              <ActivityIndicator color={colors.brand} />
            ) : (
              <Text style={styles.secondaryText}>
                {coords ? "Refresh location" : "Use current location"}
              </Text>
            )}
          </Pressable>

          {gpsStatus ? <Text style={styles.gpsStatus}>{gpsStatus}</Text> : null}

          {coords && gpsBarangay ? (
            <View style={styles.gpsDetected} accessibilityLiveRegion="polite">
              <Text style={styles.gpsDetectedLabel}>Detected barangay</Text>
              <Text style={styles.gpsDetectedName}>{gpsBarangay}</Text>
            </View>
          ) : null}

          {coords ? (
            <Pressable
              style={styles.linkBtn}
              onPress={clearGps}
              accessibilityRole="button"
              accessibilityLabel="Clear GPS"
            >
              <Text style={styles.linkText}>Clear location</Text>
            </Pressable>
          ) : null}
        </View>
      </View>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.error}>{error}</Text>
        </View>
      ) : null}

      <Pressable
        style={[styles.primary, (!photo || busy) && styles.disabled]}
        onPress={submit}
        disabled={busy}
        accessibilityRole="button"
        accessibilityLabel="Submit report"
      >
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.primaryText}>Submit report</Text>
        )}
      </Pressable>
      <Text style={styles.footerHint}>
        Your photo will be classified automatically and added to Incidents.
      </Text>

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
                const active = item === locationText;
                return (
                  <Pressable
                    style={[styles.option, active && styles.optionActive]}
                    onPress={() => {
                      setLocationText(item);
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
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, paddingBottom: 56 },

  header: { marginBottom: spacing.lg },
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
  lead: {
    color: colors.muted,
    marginTop: 8,
    lineHeight: 21,
    fontSize: 15,
  },

  card: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: "#0B3D2E",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: "700",
    color: colors.text,
  },
  sectionHint: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 4,
    marginBottom: spacing.md,
  },

  previewBox: {
    height: 240,
    borderRadius: 14,
    backgroundColor: "#F7FAF8",
    borderWidth: 1.5,
    borderColor: colors.border,
    borderStyle: "dashed",
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  previewBoxFilled: {
    borderStyle: "solid",
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  preview: { width: "100%", height: "100%" },
  previewEmpty: { alignItems: "center", paddingHorizontal: spacing.lg },
  previewIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  previewIconText: {
    color: "#fff",
    fontSize: 28,
    fontWeight: "600",
    marginTop: Platform.OS === "ios" ? -2 : 0,
  },
  previewEmptyTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
  },
  previewEmptyHint: {
    color: colors.muted,
    fontSize: 13,
    marginTop: 4,
  },
  removePhoto: {
    position: "absolute",
    top: 12,
    right: 12,
    backgroundColor: "rgba(20, 32, 27, 0.72)",
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
  },
  removePhotoText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "700",
  },

  row: { flexDirection: "row", gap: 10, marginTop: spacing.md },
  secondary: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "#FAFCFA",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  secondaryText: { color: colors.brand, fontWeight: "700", fontSize: 15 },

  label: {
    marginBottom: 6,
    color: colors.muted,
    fontWeight: "600",
    fontSize: 13,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "#FAFCFA",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === "ios" ? 14 : 12,
    color: colors.text,
    fontSize: 16,
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
  multiline: { minHeight: 96, textAlignVertical: "top" },

  gpsBlock: { marginTop: spacing.md },
  gpsBtn: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "#FAFCFA",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  gpsStatus: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 10,
    lineHeight: 17,
  },
  gpsDetected: {
    marginTop: spacing.md,
    backgroundColor: "#EEF6F1",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: "#C8DED3",
  },
  gpsDetectedLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "600",
  },
  gpsDetectedName: {
    color: colors.brand,
    fontSize: 18,
    fontWeight: "800",
    marginTop: 2,
  },
  linkBtn: { marginTop: spacing.sm, paddingVertical: 6, alignSelf: "flex-start" },
  linkText: { color: colors.brandSoft, fontWeight: "600", fontSize: 14 },

  errorBox: {
    backgroundColor: "#FDF2F1",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: "#F0C9C5",
  },
  error: { color: colors.danger, fontSize: 14, lineHeight: 20 },

  primary: {
    marginTop: spacing.sm,
    backgroundColor: colors.brand,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
  },
  disabled: { opacity: 0.55 },
  primaryText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  footerHint: {
    textAlign: "center",
    color: colors.muted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: spacing.md,
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
});
