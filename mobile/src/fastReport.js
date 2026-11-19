import { classifyIncident } from "./api";
import { normalizeBarangay } from "./barangays";

/**
 * Fast submit: classify the photo first, then the API saves the incident report.
 * The image is sent as a normal JPG/PNG file (same "image" field as the website form)
 * so it is stored on the classification record.
 */
export async function fastSubmitReport(token, report, { onStage } = {}) {
  const photo = report?.photo;
  if (!photo?.uri) {
    const err = new Error("Add a photo to continue.");
    err.status = 0;
    throw err;
  }

  onStage?.("classifying");
  const saved = await classifyIncident(token, {
    uri: photo.uri,
    name: photo.name,
    notes: report.notes,
    locationText: normalizeBarangay(report.locationText || ""),
    latitude: report.latitude,
    longitude: report.longitude,
  });
  onStage?.("sent");
  return saved;
}
