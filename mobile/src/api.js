import { getApiUrl } from "./config";

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function networkHint(err) {
  const msg = String(err?.message || err || "");
  if (/Network request failed|Failed to fetch|network/i.test(msg)) {
    return (
      "Cannot reach the API. Open the Dev Tunnel URL once in your phone browser " +
      "(accept any Continue prompt), confirm Django is running, then tap Test connection. " +
      `URL: ${getApiUrl()}`
    );
  }
  return msg || "Request failed.";
}

async function parseResponse(res) {
  const text = await res.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      // Dev Tunnels sometimes return an HTML interstitial instead of JSON.
      if (/devtunnels|tunnel|sign in|continue/i.test(text) && text.includes("<")) {
        throw new ApiError(
          "Dev Tunnel blocked the app (HTML page instead of API). Open the tunnel URL in your phone browser, click Continue / allow anonymous access, then try again.",
          res.status,
          { error: "tunnel_interstitial" },
        );
      }
      body = { error: text.slice(0, 200) };
    }
  }
  if (!res.ok) {
    throw new ApiError(body?.error || `Request failed (${res.status})`, res.status, body);
  }
  return body;
}

async function apiFetch(path, options = {}) {
  const url = `${getApiUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
    return parseResponse(res);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(networkHint(err), 0, null);
  }
}

export async function ping() {
  return apiFetch("/health/", { method: "GET" });
}

export async function login(email, password, deviceLabel = "mobile") {
  return apiFetch("/auth/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, device_label: deviceLabel }),
  });
}

export async function logout(token) {
  return apiFetch("/auth/logout/", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchMeta(token) {
  return apiFetch("/meta/", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function classifyIncident(token, { uri, name, type, notes, locationText, latitude, longitude }) {
  const form = new FormData();
  form.append("image", {
    uri,
    name: name || "incident.jpg",
    type: type || "image/jpeg",
  });
  if (notes) form.append("notes", notes);
  if (locationText) form.append("location_text", locationText);
  if (latitude != null && latitude !== "") form.append("latitude", String(latitude));
  if (longitude != null && longitude !== "") form.append("longitude", String(longitude));

  const headers = {
    // Do not set Content-Type — RN sets multipart boundary automatically.
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  return apiFetch("/classify/", {
    method: "POST",
    headers,
    body: form,
  });
}

export async function fetchClassifications(token, page = 1) {
  return apiFetch(`/classifications/?page=${page}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchClassification(token, id) {
  return apiFetch(`/classifications/${id}/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function verifyClassification(token, id, verification, actualLabel = "") {
  return apiFetch(`/classifications/${id}/verify/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ verification, actual_label: actualLabel }),
  });
}

export { ApiError };
