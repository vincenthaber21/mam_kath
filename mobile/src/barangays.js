/** Official barangays of Santa Maria, Ilocos Sur. */
export const SANTA_MARIA_BARANGAYS = [
  "Ag-agrao",
  "Ampuagan",
  "Baballasioan",
  "Baliw Daya",
  "Baliw Laud",
  "Bia-o",
  "Butir",
  "Cabaroan",
  "Danuman East",
  "Danuman West",
  "Dunglayan",
  "Gusing",
  "Langaoan",
  "Laslasong Norte",
  "Laslasong Sur",
  "Laslasong West",
  "Lesseb",
  "Lingsat",
  "Lubong",
  "Maynganay Norte",
  "Maynganay Sur",
  "Nagsayaoan",
  "Nagtupacan",
  "Nalvo",
  "Pacang",
  "Penned",
  "Poblacion Norte",
  "Poblacion Sur",
  "Silag",
  "Sumagui",
  "Suso",
  "Tangaoan",
  "Tinaan",
];

/** Approximate barangay centers for GPS → name resolution. */
export const SANTA_MARIA_BARANGAY_COORDS = {
  "Ag-agrao": { latitude: 17.3791, longitude: 120.508 },
  Ampuagan: { latitude: 17.3553, longitude: 120.4963 },
  Baballasioan: { latitude: 17.3859, longitude: 120.519 },
  "Baliw Daya": { latitude: 17.3697, longitude: 120.484 },
  "Baliw Laud": { latitude: 17.373, longitude: 120.474 },
  "Bia-o": { latitude: 17.3848, longitude: 120.4556 },
  Butir: { latitude: 17.3751, longitude: 120.5046 },
  Cabaroan: { latitude: 17.3707, longitude: 120.4978 },
  "Danuman East": { latitude: 17.3755, longitude: 120.4695 },
  "Danuman West": { latitude: 17.3735, longitude: 120.4625 },
  Dunglayan: { latitude: 17.3467, longitude: 120.4803 },
  Gusing: { latitude: 17.3836, longitude: 120.5144 },
  Langaoan: { latitude: 17.3644, longitude: 120.4973 },
  "Laslasong Norte": { latitude: 17.3905, longitude: 120.4944 },
  "Laslasong Sur": { latitude: 17.386, longitude: 120.4975 },
  "Laslasong West": { latitude: 17.388, longitude: 120.4895 },
  Lesseb: { latitude: 17.3448, longitude: 120.5054 },
  Lingsat: { latitude: 17.3769, longitude: 120.454 },
  Lubong: { latitude: 17.3513, longitude: 120.48 },
  "Maynganay Norte": { latitude: 17.3861, longitude: 120.4951 },
  "Maynganay Sur": { latitude: 17.3807, longitude: 120.4764 },
  Nagsayaoan: { latitude: 17.352, longitude: 120.468 },
  Nagtupacan: { latitude: 17.383, longitude: 120.479 },
  Nalvo: { latitude: 17.3631, longitude: 120.4551 },
  Pacang: { latitude: 17.3566, longitude: 120.4944 },
  Penned: { latitude: 17.3485, longitude: 120.492 },
  "Poblacion Norte": { latitude: 17.3685, longitude: 120.4825 },
  "Poblacion Sur": { latitude: 17.3651, longitude: 120.4815 },
  Silag: { latitude: 17.3609, longitude: 120.5091 },
  Sumagui: { latitude: 17.358, longitude: 120.472 },
  Suso: { latitude: 17.3594, longitude: 120.4611 },
  Tangaoan: { latitude: 17.3364, longitude: 120.4804 },
  Tinaan: { latitude: 17.3817, longitude: 120.4846 },
};

const BARANGAY_SET = new Set(SANTA_MARIA_BARANGAYS.map((name) => name.toLowerCase()));

/** Match a known barangay name (case-insensitive), else return trimmed text. */
export function normalizeBarangay(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const found = SANTA_MARIA_BARANGAYS.find((name) => name.toLowerCase() === text.toLowerCase());
  return found || text.slice(0, 120);
}

/** Dropdown options; keeps a legacy / free-text value selectable when editing. */
export function barangayOptions(extra = "") {
  const extras = [];
  const value = normalizeBarangay(extra);
  if (value && !BARANGAY_SET.has(value.toLowerCase())) {
    extras.push(value);
  }
  return extras.concat(SANTA_MARIA_BARANGAYS);
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const r = 6371;
  const toRad = (deg) => (deg * Math.PI) / 180;
  const p1 = toRad(lat1);
  const p2 = toRad(lat2);
  const dp = toRad(lat2 - lat1);
  const dl = toRad(lon2 - lon1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

/** Nearest Santa Maria barangay for a GPS fix (empty when outside the town). */
export function nearestBarangay(latitude, longitude, maxKm = 12) {
  const lat = Number(latitude);
  const lon = Number(longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return "";

  let bestName = "";
  let bestKm = Infinity;
  for (const [name, point] of Object.entries(SANTA_MARIA_BARANGAY_COORDS)) {
    const dist = haversineKm(lat, lon, point.latitude, point.longitude);
    if (dist < bestKm) {
      bestKm = dist;
      bestName = name;
    }
  }
  return bestKm <= maxKm ? bestName : "";
}

/**
 * Best-effort match from expo-location reverseGeocodeAsync place fields
 * (district / subregion / city / name / street / formattedAddress).
 */
export function matchBarangayFromGeocode(places) {
  const list = Array.isArray(places) ? places : places ? [places] : [];
  for (const place of list) {
    const fields = [
      place?.district,
      place?.subregion,
      place?.city,
      place?.name,
      place?.street,
      place?.formattedAddress,
    ]
      .filter(Boolean)
      .map((value) => String(value));

    for (const field of fields) {
      const exact = normalizeBarangay(field);
      if (exact && BARANGAY_SET.has(exact.toLowerCase())) return exact;
    }

    const haystack = fields.join(" ").toLowerCase();
    for (const name of SANTA_MARIA_BARANGAYS) {
      if (haystack.includes(name.toLowerCase())) return name;
    }
  }
  return "";
}

/** Prefer reverse-geocode name; fall back to nearest centroid. */
export function resolveBarangayFromGps({ latitude, longitude }, places = null) {
  const fromGeo = matchBarangayFromGeocode(places);
  if (fromGeo) return fromGeo;
  return nearestBarangay(latitude, longitude);
}
