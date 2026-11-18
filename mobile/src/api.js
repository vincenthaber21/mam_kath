import { getApiUrl } from "./config";

/** Lazy-load Expo FS / fetch so a broken Expo Go reload fails later with a clearer path. */
async function expoUploadModules() {
  const [{ fetch: expoFetch }, { File, Paths }] = await Promise.all([
    import("expo/fetch"),
    import("expo-file-system"),
  ]);
  return { expoFetch, File, Paths };
}

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
      "Cannot reach the API. Django must be running and Ports → 8000 → Public. " +
      "On Account tap Use public tunnel, then Test connection. " +
      `URL: ${getApiUrl()}`
    );
  }
  return msg || "Request failed.";
}

function statusHint(status, fallback) {
  if (status === 401 || status === 403) {
    const host = getApiUrl();
    if (/devtunnels\.ms/i.test(host)) {
      return (
        "Tunnel blocked this request (401). In Ports set Dev Tunnel 8000 to Public / Anonymous, " +
        "open the tunnel URL in the phone browser and Continue, then retry. " +
        "Guest reporting does not need a website login."
      );
    }
    return fallback || "Authentication failed. Sign in again, or continue as guest.";
  }
  return fallback || `Request failed (${status})`;
}

function authHeaders(token) {
  // Prefer X-EIC-Token over Authorization: Bearer so Dev Tunnels does not
  // intercept the header as a tunnel access token.
  if (!token) return {};
  return { "X-EIC-Token": token };
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
    throw new ApiError(statusHint(res.status, body?.error), res.status, body);
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

export async function login(identifier, password, deviceLabel = "mobile") {
  const login = String(identifier || "").trim();
  const payload = {
    username: login,
    password,
    device_label: deviceLabel,
  };
  // Keep email for older API builds that only read that field.
  if (login.includes("@")) payload.email = login.toLowerCase();
  return apiFetch("/auth/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** Create a Santa Maria resident account and return {token, user}. */
export async function register(payload, deviceLabel = "mobile") {
  return apiFetch("/auth/register/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      device_label: deviceLabel,
    }),
  });
}

export async function logout(token) {
  return apiFetch("/auth/logout/", {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function fetchMeta(token) {
  return apiFetch("/meta/", {
    headers: authHeaders(token),
  });
}

function imageUploadName(name) {
  const base = String(name || "incident.jpg").split(/[/\\]/).pop() || "incident.jpg";
  const safe = base.replace(/[^\w.\-]+/g, "_");
  return /\.(jpe?g|png)$/i.test(safe) ? safe : `${safe.replace(/\.[^.]+$/, "") || "incident"}.jpg`;
}

async function imageFileForUpload(File, Paths, uri, name) {
  const source = new File(uri);
  // Prefer a cache copy with a clean .jpg/.png name for Django's ImageField.
  try {
    if (source.exists) {
      const fileName = `${Date.now()}_${imageUploadName(name || source.name)}`;
      const uploadFile = new File(Paths.cache, fileName);
      if (uploadFile.exists) uploadFile.delete();
      await source.copy(uploadFile);
      return uploadFile;
    }
  } catch {
    // Fall through — some picker URIs still upload via File(uri) directly.
  }
  return source;
}

async function postClassify(expoFetch, form, token) {
  const headers = {
    Accept: "application/json",
    // Do not set Content-Type — fetch sets the multipart boundary automatically.
    ...authHeaders(token),
  };
  const url = `${getApiUrl()}/classify/`;
  const res = await expoFetch(url, { method: "POST", headers, body: form });
  return parseResponse(res);
}

export async function classifyIncident(token, { uri, name, notes, locationText, latitude, longitude }) {
  // Expo SDK 58 installs WinterCG fetch as global fetch. Classic React Native
  // FormData parts `{ uri, name, type }` throw "Unsupported FormDataPart implementation".
  // Append an expo-file-system File and post with expo/fetch instead.
  if (!uri) {
    throw new ApiError("Capture or choose a photo first.", 0, null);
  }

  let expoFetch;
  let File;
  let Paths;
  try {
    ({ expoFetch, File, Paths } = await expoUploadModules());
  } catch (err) {
    throw new ApiError(
      "Expo Go runtime is not ready (EventEmitter). Update Expo Go, force-quit it, " +
        "then open the project again from the Home screen (do not tap Refresh on the red error). " +
        String(err?.message || err || ""),
      0,
      null,
    );
  }

  const buildForm = async () => {
    const form = new FormData();
    form.append("image", await imageFileForUpload(File, Paths, uri, name));
    if (notes) form.append("notes", notes);
    if (locationText) form.append("location_text", locationText);
    if (latitude != null && latitude !== "") form.append("latitude", String(latitude));
    if (longitude != null && longitude !== "") form.append("longitude", String(longitude));
    return form;
  };

  try {
    return await postClassify(expoFetch, await buildForm(), token);
  } catch (err) {
    // Stale app token or Dev Tunnel reacting to auth headers: guest classify is allowed.
    if (err instanceof ApiError && err.status === 401 && token) {
      try {
        return await postClassify(expoFetch, await buildForm(), null);
      } catch (retryErr) {
        if (retryErr instanceof ApiError) throw retryErr;
        throw new ApiError(networkHint(retryErr), 0, null);
      }
    }
    if (err instanceof ApiError) throw err;
    throw new ApiError(networkHint(err), 0, null);
  }
}

export async function fetchClassifications(token, page = 1) {
  return apiFetch(`/classifications/?page=${page}`, {
    headers: authHeaders(token),
  });
}

export async function fetchClassification(token, id) {
  return apiFetch(`/classifications/${id}/`, {
    headers: authHeaders(token),
  });
}

export async function verifyClassification(token, id, verification, actualLabel = "") {
  return apiFetch(`/classifications/${id}/verify/`, {
    method: "POST",
    headers: {
      ...authHeaders(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ verification, actual_label: actualLabel }),
  });
}

export { ApiError };
