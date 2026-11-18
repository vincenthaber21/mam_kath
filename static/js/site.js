/* Small progressive enhancements. Every page also works with plain form posts. */
(function () {
  "use strict";
  var MAX_BYTES = 10 * 1024 * 1024;
  var EIC = (window.EIC = {});

  // Fade out flash messages.
  document.querySelectorAll(".toast").forEach(function (t) {
    setTimeout(function () { t.style.opacity = "0"; setTimeout(function () { t.remove(); }, 450); }, 4500);
  });

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function validateImage(file) {
    var okType = file.type === "image/jpeg" || file.type === "image/png" || (!file.type && /\.(jpe?g|png)$/i.test(file.name));
    if (!okType) return "Only JPG or PNG images are accepted.";
    if (file.size === 0) return "This file is empty.";
    if (file.size > MAX_BYTES) return "This image is " + (file.size / 1024 / 1024).toFixed(1) + " MB. The maximum is 10 MB.";
    return null;
  }

  function setFiles(input, file) {
    var dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
  }

  function wireDrop(zone, input, onFile) {
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("drag"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("drag"); });
    });
    zone.addEventListener("drop", function (e) {
      var f = e.dataTransfer && e.dataTransfer.files[0];
      if (f) onFile(f, true);
    });
    zone.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });
    input.addEventListener("change", function () { if (input.files[0]) onFile(input.files[0], false); });
  }

  EIC.initClassify = function () {
    var form = document.getElementById("classify-form");
    var input = document.getElementById("image-input");
    var zone = document.getElementById("dropzone");
    var preview = document.getElementById("preview");
    var text = document.getElementById("dropzone-text");
    var info = document.getElementById("file-info");
    var err = document.getElementById("file-error");
    var btn = document.getElementById("classify-btn");
    var dialog = document.getElementById("camera-dialog");
    var video = document.getElementById("camera-video");
    var canvas = document.getElementById("camera-canvas");
    var shotBtn = document.getElementById("camera-shot");
    var camErr = document.getElementById("camera-error");
    var url = null;
    var stream = null;

    function showError(msg) { err.textContent = msg; err.hidden = !msg; }
    function showCamError(msg) { camErr.textContent = msg; camErr.hidden = !msg; }

    function pick(file, fromDrop) {
      var problem = validateImage(file);
      if (problem) {
        input.value = "";
        showError(problem);
        preview.hidden = true; text.hidden = false; info.hidden = true; zone.classList.remove("filled");
        return;
      }
      if (fromDrop) setFiles(input, file);
      showError("");
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(file);
      preview.src = url; preview.hidden = false; text.hidden = true; zone.classList.add("filled");
      info.textContent = file.name + " · " + Math.round(file.size / 1024) + " KB";
      info.hidden = false;
    }
    wireDrop(zone, input, pick);

    function stopCamera() {
      if (stream) {
        stream.getTracks().forEach(function (t) { t.stop(); });
        stream = null;
      }
      if (video) video.srcObject = null;
      if (shotBtn) shotBtn.disabled = true;
    }

    function requestCamera(constraints) {
      return navigator.mediaDevices.getUserMedia(constraints);
    }

    function startCameraStream() {
      // Prefer the back camera on phones; fall back to any webcam on desktops.
      var attempts = [
        { audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } } },
        { audio: false, video: { facingMode: "user" } },
        { audio: false, video: true }
      ];
      var i = 0;
      function next(err) {
        if (i >= attempts.length) return Promise.reject(err || new Error("Camera unavailable"));
        return requestCamera(attempts[i++]).catch(next);
      }
      return next();
    }

    function cameraFailMessage(e) {
      var name = e && e.name;
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        return "Camera permission was blocked. Click the camera/lock icon in the address bar, allow camera access, then try again.";
      }
      if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        return "No camera was found on this device. Plug in a webcam or use Choose file.";
      }
      if (name === "NotReadableError" || name === "TrackStartError") {
        return "The camera is already in use by another app. Close that app and try again.";
      }
      if (!window.isSecureContext) {
        return "Camera needs a secure page (http://127.0.0.1 or https). Open the site with 127.0.0.1, not a LAN IP.";
      }
      return "Could not open the camera" + (e && e.message ? " (" + e.message + ")" : "") + ". Use Choose file if needed.";
    }

    function openWebcam() {
      showError("");
      if (!dialog) {
        showError("Camera dialog is missing. Refresh the page and try again.");
        return;
      }
      if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showError(cameraFailMessage({ name: "SecurityError", message: "getUserMedia unavailable" }));
        return;
      }

      showCamError("Starting camera…");
      shotBtn.disabled = true;
      if (!dialog.open) dialog.showModal();

      startCameraStream().then(function (media) {
        stream = media;
        video.srcObject = media;
        return video.play();
      }).then(function () {
        showCamError("");
        shotBtn.disabled = false;
      }).catch(function (e) {
        stopCamera();
        showCamError(cameraFailMessage(e));
      });
    }

    document.getElementById("gallery-btn").addEventListener("click", function () {
      input.removeAttribute("capture"); input.accept = "image/jpeg,image/png"; input.click();
    });
    document.getElementById("camera-btn").addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      openWebcam();
    });

    if (dialog) {
      wireDialog(dialog);
      dialog.addEventListener("close", stopCamera);
      shotBtn.addEventListener("click", function () {
        if (!stream || !video.videoWidth) {
          showCamError("Camera is not ready yet. Wait a moment and try again.");
          return;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);
        if (!canvas.toBlob) {
          showCamError("This browser cannot capture a photo from the camera.");
          return;
        }
        canvas.toBlob(function (blob) {
          if (!blob) {
            showCamError("Could not capture the photo. Try again.");
            return;
          }
          var file = new File([blob], "camera-" + Date.now() + ".jpg", { type: "image/jpeg" });
          setFiles(input, file);
          pick(file, false);
          dialog.close();
        }, "image/jpeg", 0.92);
      });
    }

    form.addEventListener("submit", function (e) {
      if (!input.files.length) { e.preventDefault(); showError("Choose or capture an image first."); return; }
      btn.disabled = true; btn.textContent = "Classifying…";
    });

    var gpsBtn = document.getElementById("gps-btn");
    var gpsStatus = document.getElementById("gps-status");
    var latInput = document.getElementById("latitude");
    var lonInput = document.getElementById("longitude");
    var locationSelect = document.getElementById("location_text");
    if (gpsBtn && latInput && lonInput) {
      var BARANGAY_COORDS = {
        "Ag-agrao": [17.3791, 120.5080],
        "Ampuagan": [17.3553, 120.4963],
        "Baballasioan": [17.3859, 120.5190],
        "Baliw Daya": [17.3697, 120.4840],
        "Baliw Laud": [17.3730, 120.4740],
        "Bia-o": [17.3848, 120.4556],
        "Butir": [17.3751, 120.5046],
        "Cabaroan": [17.3707, 120.4978],
        "Danuman East": [17.3755, 120.4695],
        "Danuman West": [17.3735, 120.4625],
        "Dunglayan": [17.3467, 120.4803],
        "Gusing": [17.3836, 120.5144],
        "Langaoan": [17.3644, 120.4973],
        "Laslasong Norte": [17.3905, 120.4944],
        "Laslasong Sur": [17.3860, 120.4975],
        "Laslasong West": [17.3880, 120.4895],
        "Lesseb": [17.3448, 120.5054],
        "Lingsat": [17.3769, 120.4540],
        "Lubong": [17.3513, 120.4800],
        "Maynganay Norte": [17.3861, 120.4951],
        "Maynganay Sur": [17.3807, 120.4764],
        "Nagsayaoan": [17.3520, 120.4680],
        "Nagtupacan": [17.3830, 120.4790],
        "Nalvo": [17.3631, 120.4551],
        "Pacang": [17.3566, 120.4944],
        "Penned": [17.3485, 120.4920],
        "Poblacion Norte": [17.3685, 120.4825],
        "Poblacion Sur": [17.3651, 120.4815],
        "Silag": [17.3609, 120.5091],
        "Sumagui": [17.3580, 120.4720],
        "Suso": [17.3594, 120.4611],
        "Tangaoan": [17.3364, 120.4804],
        "Tinaan": [17.3817, 120.4846]
      };

      function haversineKm(lat1, lon1, lat2, lon2) {
        var r = 6371;
        var toRad = function (deg) { return deg * Math.PI / 180; };
        var p1 = toRad(lat1), p2 = toRad(lat2);
        var dp = toRad(lat2 - lat1), dl = toRad(lon2 - lon1);
        var a = Math.sin(dp / 2) * Math.sin(dp / 2) +
          Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
        return 2 * r * Math.asin(Math.sqrt(a));
      }

      function nearestBarangay(lat, lon) {
        var bestName = "";
        var bestKm = Infinity;
        Object.keys(BARANGAY_COORDS).forEach(function (name) {
          var point = BARANGAY_COORDS[name];
          var dist = haversineKm(lat, lon, point[0], point[1]);
          if (dist < bestKm) {
            bestKm = dist;
            bestName = name;
          }
        });
        return bestKm <= 12 ? bestName : "";
      }

      function setGpsStatus(msg) { if (gpsStatus) gpsStatus.textContent = msg || ""; }

      function applyGpsBarangay(lat, lon) {
        var name = nearestBarangay(lat, lon);
        if (locationSelect && name) {
          locationSelect.value = name;
          if (locationSelect.value !== name) {
            var opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name;
            locationSelect.appendChild(opt);
            locationSelect.value = name;
          }
        }
        if (name) {
          setGpsStatus("Detected barangay: " + name + " (" + lat.toFixed(5) + ", " + lon.toFixed(5) + ")");
        } else {
          setGpsStatus("GPS attached (" + lat.toFixed(5) + ", " + lon.toFixed(5) + ") — barangay not detected");
        }
        return name;
      }

      if (latInput.value && lonInput.value) {
        applyGpsBarangay(Number(latInput.value), Number(lonInput.value));
      }
      gpsBtn.addEventListener("click", function () {
        if (!navigator.geolocation) {
          setGpsStatus("Geolocation is not supported in this browser.");
          return;
        }
        gpsBtn.disabled = true;
        setGpsStatus("Reading GPS…");
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            var lat = pos.coords.latitude;
            var lon = pos.coords.longitude;
            latInput.value = String(lat);
            lonInput.value = String(lon);
            applyGpsBarangay(lat, lon);
            gpsBtn.disabled = false;
          },
          function () {
            setGpsStatus("Location permission denied or unavailable.");
            gpsBtn.disabled = false;
          },
          { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 }
        );
      });
    }
  };

  EIC.initVerification = function () {
    var sel = document.getElementById("verification");
    var wrap = document.getElementById("actual-wrap");
    sel.addEventListener("change", function () { wrap.hidden = sel.value !== "incorrect"; });
  };

  EIC.initHistory = function () {
    var form = document.getElementById("filters");
    if (!form) return;
    form.querySelectorAll("[data-autosubmit]").forEach(function (el) {
      el.addEventListener("change", function () { form.submit(); });
    });
    var search = document.getElementById("search");
    if (search) {
      var timer = null;
      var initial = search.value;
      search.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(function () { if (search.value.trim() !== initial.trim()) form.submit(); }, 500);
      });
      if (initial) { search.focus(); search.setSelectionRange(initial.length, initial.length); }
    }
    document.querySelectorAll(".row-link").forEach(function (row) {
      function go() { window.location.href = row.dataset.href; }
      row.addEventListener("click", function (e) {
        if (e.target.closest("a, button, form, .actions-cell")) return;
        go();
      });
      row.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.target.closest("a, button, form, .actions-cell")) go();
      });
    });
  };

  function readJsonScript(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (err) { return null; }
  }

  EIC.initIncidentMap = function () {
    var canvas = document.getElementById("incident-map");
    if (!canvas || !window.google || !google.maps) return;
    var markers = readJsonScript("incident-map-markers") || [];
    var center = readJsonScript("incident-map-center") || { lat: 17.35712, lng: 120.49634 };
    var boundary = readJsonScript("incident-map-boundary") || [];
    var map = new google.maps.Map(canvas, {
      center: center,
      zoom: markers.length ? 13 : 12,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true,
      clickableIcons: false,
    });
    var info = new google.maps.InfoWindow();
    var bounds = new google.maps.LatLngBounds();
    var byId = {};
    var boundaryBounds = new google.maps.LatLngBounds();
    var hasBoundary = false;

    if (boundary.length) {
      boundary.forEach(function (pt) {
        var lat = Number(pt.lat);
        var lng = Number(pt.lng);
        if (!isFinite(lat) || !isFinite(lng)) return;
        boundaryBounds.extend({ lat: lat, lng: lng });
        hasBoundary = true;
      });
      new google.maps.Polygon({
        paths: boundary,
        strokeColor: "#0369a1",
        strokeOpacity: 1,
        strokeWeight: 3,
        fillColor: "#0369a1",
        fillOpacity: 0.08,
        map: map,
        clickable: false,
        zIndex: 1,
      });
    }

    markers.forEach(function (m) {
      var position = { lat: Number(m.lat), lng: Number(m.lng) };
      if (!isFinite(position.lat) || !isFinite(position.lng)) return;
      var pin = new google.maps.Marker({
        map: map,
        position: position,
        title: m.record + " · " + m.label_name,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 9,
          fillColor: m.color || "#64748b",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
        },
        zIndex: 2,
      });
      byId[String(m.id)] = { marker: pin, data: m, position: position };
      bounds.extend(position);
      pin.addListener("click", function () {
        info.setContent(
          "<div class=\"map-info\">" +
            "<strong>" + m.record + "</strong> · " + m.label_name +
            "<br><span>" + m.status_label + " · " + m.when + "</span>" +
            (m.location ? "<br>" + m.location : "") +
            "<br><a href=\"" + m.url + "\">Open record</a>" +
          "</div>"
        );
        info.open({ map: map, anchor: pin });
      });
    });

    var agencies = readJsonScript("incident-map-agencies") || [];
    var agencyById = {};
    agencies.forEach(function (a) {
      var position = { lat: Number(a.lat), lng: Number(a.lng) };
      if (!isFinite(position.lat) || !isFinite(position.lng)) return;
      var pin = new google.maps.Marker({
        map: map,
        position: position,
        title: a.name + " · " + a.type_label,
        icon: {
          path: "M 0,-10 10,0 0,10 -10,0 z",
          scale: 1,
          fillColor: "#7c3aed",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
        },
        zIndex: 3,
      });
      agencyById[String(a.id)] = { marker: pin, position: position };
      pin.addListener("click", function () {
        var div = document.createElement("div");
        div.className = "map-info";
        var strong = document.createElement("strong");
        strong.textContent = a.name;
        div.appendChild(strong);
        div.appendChild(document.createTextNode(" · " + a.type_label));
        [a.barangay, a.address, a.phone].forEach(function (t) {
          if (!t) return;
          div.appendChild(document.createElement("br"));
          div.appendChild(document.createTextNode(t));
        });
        info.setContent(div);
        info.open({ map: map, anchor: pin });
      });
    });
    document.querySelectorAll("[data-agency-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var entry = agencyById[String(btn.getAttribute("data-agency-id"))];
        if (!entry) return;
        map.panTo(entry.position);
        map.setZoom(Math.max(map.getZoom(), 15));
        google.maps.event.trigger(entry.marker, "click");
      });
    });

    if (markers.length === 1) {
      map.setCenter(bounds.getCenter());
      map.setZoom(15);
    } else if (markers.length > 1) {
      map.fitBounds(bounds, 48);
    } else if (hasBoundary) {
      map.fitBounds(boundaryBounds, 40);
    }

    document.querySelectorAll("[data-marker-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var entry = byId[String(btn.getAttribute("data-marker-id"))];
        if (!entry) return;
        map.panTo(entry.position);
        map.setZoom(Math.max(map.getZoom(), 15));
        google.maps.event.trigger(entry.marker, "click");
      });
    });
  };

  // Agency station location: keep lat/lng inputs and the "Clear" button in sync.
  EIC.initAgencyLocationFields = function () {
    document.querySelectorAll("[data-agency-location]").forEach(function (box) {
      var clear = box.querySelector("[data-agency-clear]");
      if (!clear) return;
      clear.addEventListener("click", function () {
        var lat = box.querySelector("[data-agency-lat]");
        var lng = box.querySelector("[data-agency-lng]");
        if (lat) lat.value = "";
        if (lng) lng.value = "";
        if (lat) lat.dispatchEvent(new Event("input", { bubbles: true }));
      });
    });
  };

  // Google Map pickers on the agency create dialog and edit page.
  EIC.initAgencyPickers = function () {
    if (!window.google || !google.maps) return;
    var center = readJsonScript("incident-map-center") || { lat: 17.35712, lng: 120.49634 };
    var boundary = readJsonScript("incident-map-boundary") || [];
    document.querySelectorAll("[data-agency-location]").forEach(function (box) {
      var canvas = box.querySelector(".agency-picker");
      var latIn = box.querySelector("[data-agency-lat]");
      var lngIn = box.querySelector("[data-agency-lng]");
      if (!canvas || !latIn || !lngIn) return;
      var map = new google.maps.Map(canvas, {
        center: center, zoom: 12, mapTypeControl: false, streetViewControl: false,
        fullscreenControl: false, clickableIcons: false,
      });
      var boundaryBounds = new google.maps.LatLngBounds();
      if (boundary.length) {
        boundary.forEach(function (pt) { boundaryBounds.extend({ lat: Number(pt.lat), lng: Number(pt.lng) }); });
        new google.maps.Polygon({
          paths: boundary, strokeColor: "#0369a1", strokeOpacity: 1, strokeWeight: 2,
          fillColor: "#0369a1", fillOpacity: 0.06, map: map, clickable: false,
        });
      }
      var marker = null;
      function current() {
        var lat = parseFloat(latIn.value), lng = parseFloat(lngIn.value);
        return isFinite(lat) && isFinite(lng) ? { lat: lat, lng: lng } : null;
      }
      function setInputs(pos) {
        latIn.value = pos.lat().toFixed(6);
        lngIn.value = pos.lng().toFixed(6);
      }
      function place(pos, pan) {
        if (!marker) {
          marker = new google.maps.Marker({ map: map, position: pos, draggable: true, title: "Agency location" });
          marker.addListener("dragend", function () { setInputs(marker.getPosition()); });
        } else {
          marker.setMap(map);
          marker.setPosition(pos);
        }
        if (pan) map.panTo(pos);
      }
      var start = current();
      if (start) { place(start, false); map.setCenter(start); map.setZoom(15); }
      else if (boundary.length) { map.fitBounds(boundaryBounds, 16); }
      map.addListener("click", function (e) { place(e.latLng, false); setInputs(e.latLng); });
      function syncFromInputs() {
        var pos = current();
        if (pos) place(pos, true);
        else if (marker) marker.setMap(null);
      }
      latIn.addEventListener("input", syncFromInputs);
      lngIn.addEventListener("input", syncFromInputs);
      // The create dialog's map is hidden until opened; redraw when shown.
      var dialog = box.closest("dialog");
      if (dialog && window.MutationObserver) {
        new MutationObserver(function () {
          if (!dialog.open) return;
          var pos = current();
          google.maps.event.trigger(map, "resize");
          if (pos) map.setCenter(pos); else if (boundary.length) map.fitBounds(boundaryBounds, 16);
        }).observe(dialog, { attributes: true, attributeFilter: ["open"] });
      }
    });
  };

  EIC.initEvaluation = function () {
    var input = document.getElementById("id_test_set");
    var zone = document.getElementById("zip-zone");
    var text = document.getElementById("zip-text");
    var err = document.getElementById("zip-error");
    if (input && zone) {
      wireDrop(zone, input, function (file, fromDrop) {
        if (!/\.zip$/i.test(file.name)) {
          input.value = ""; err.textContent = "Upload a .zip file with one folder per category."; err.hidden = false; return;
        }
        if (fromDrop) setFiles(input, file);
        err.hidden = true;
        zone.classList.add("filled");
        text.innerHTML = "";
        var a = document.createElement("span"); a.textContent = file.name + " · " + (file.size / 1024 / 1024).toFixed(1) + " MB";
        var b = document.createElement("span"); b.className = "muted small"; b.textContent = "Click to choose a different file";
        text.appendChild(a); text.appendChild(b);
      });
      zone.closest("form").addEventListener("submit", function (e) {
        if (!input.files.length) { e.preventDefault(); err.textContent = "Choose a .zip test set first."; err.hidden = false; return; }
        var btn = document.getElementById("run-btn"); btn.disabled = true; btn.textContent = "Uploading…";
      });
    }

    var box = document.getElementById("progress");
    if (!box || box.dataset.status !== "running") return;
    var fill = document.getElementById("progress-fill");
    var label = document.getElementById("progress-text");
    var bar = box.querySelector("[role=progressbar]");
    function poll() {
      fetch(box.dataset.statusUrl, { headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (s) {
          var pct = s.total ? (s.processed / s.total) * 100 : 0;
          fill.style.width = pct + "%";
          bar.setAttribute("aria-valuenow", s.processed); bar.setAttribute("aria-valuemax", s.total);
          label.textContent = "Progress: " + s.processed + " / " + s.total + " images";
          if (s.status !== "running") {
            var u = new URL(window.location.href); u.searchParams.set("id", s.id); u.searchParams.set("toast", "1");
            window.location.replace(u.toString());
          } else setTimeout(poll, 1500);
        })
        .catch(function () { setTimeout(poll, 4000); });
    }
    setTimeout(poll, 1000);
  };

  function lineChart(canvas, history, trainKey, valKey, yMin) {
    return new Chart(canvas, {
      type: "line",
      data: {
        labels: history.map(function (h) { return h.epoch; }),
        datasets: [
          { label: "Training", data: history.map(function (h) { return h[trainKey]; }), borderColor: cssVar("--bar-muted"), backgroundColor: cssVar("--bar-muted"), borderWidth: 2, pointRadius: 0, tension: 0.3 },
          { label: "Validation", data: history.map(function (h) { return h[valKey]; }), borderColor: cssVar("--brand"), backgroundColor: cssVar("--brand"), borderWidth: 2, pointRadius: 0, tension: 0.3 }
        ]
      },
      options: {
        maintainAspectRatio: false, animation: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { boxWidth: 12, font: { size: 12 } } }, tooltip: { callbacks: { title: function (i) { return "Epoch " + i[0].label; }, label: function (c) { return c.dataset.label + ": " + Number(c.parsed.y).toFixed(3); } } } },
        scales: { x: { title: { display: true, text: "Epoch" }, grid: { color: cssVar("--accent") } }, y: { min: yMin, grid: { color: cssVar("--accent") } } }
      }
    });
  }

  function wireDialog(dialog) {
    dialog.querySelectorAll("[data-close]").forEach(function (b) { b.addEventListener("click", function () { dialog.close(); }); });
    dialog.addEventListener("click", function (e) { if (e.target === dialog) dialog.close(); });
  }

  EIC.initModels = function () {
    var dataEl = document.getElementById("chart-data");
    if (dataEl && window.Chart) {
      var data = JSON.parse(dataEl.textContent);
      var select = document.getElementById("chart-model");
      var charts = [];
      var draw = function () {
        charts.forEach(function (c) { c.destroy(); }); charts = [];
        var entry = data[select.value] || { history: [] };
        var h = entry.history || [];
        var fitEl = document.getElementById("chart-fit");
        if (fitEl) {
          var fit = entry.fit || {};
          fitEl.textContent = fit.label ? "Overfitting check: " + fit.label + (fit.reasons && fit.reasons.length ? " — " + fit.reasons.join(" ") : "") : "";
        }
        document.querySelectorAll(".chart").forEach(function (box) {
          box.querySelector("canvas").hidden = !h.length;
          box.querySelector(".chart-empty").hidden = !!h.length;
        });
        if (!h.length) return;
        charts.push(lineChart(document.getElementById("acc-chart"), h, "train_acc", "val_acc", undefined));
        charts.push(lineChart(document.getElementById("loss-chart"), h, "train_loss", "val_loss", 0));
      };
      select.addEventListener("change", draw);
      draw();
    }

    var actDialog = document.getElementById("activate-dialog");
    var actForm = document.getElementById("activate-form");
    if (actDialog && actForm) {
      wireDialog(actDialog);
      document.querySelectorAll("[data-activate]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          actForm.action = btn.dataset.activate;
          document.getElementById("activate-title").textContent = "Set " + btn.dataset.name + " as the active model?";
          document.getElementById("activate-text").textContent = "All new classifications will use " + btn.dataset.name + " v" + btn.dataset.version + ". Past records keep the model they were classified with.";
          actDialog.showModal();
        });
      });
    }

    var upDialog = document.getElementById("upload-dialog");
    var upOpen = document.getElementById("upload-open");
    if (upDialog && upOpen) {
      wireDialog(upDialog);
      upOpen.addEventListener("click", function () { upDialog.showModal(); });
      if (upDialog.hasAttribute("data-open")) upDialog.showModal();
    }

    var trainDialog = document.getElementById("train-dialog");
    var trainOpen = document.getElementById("train-open");
    if (trainDialog && trainOpen) {
      wireDialog(trainDialog);
      trainOpen.addEventListener("click", function () {
        if (!trainOpen.disabled) trainDialog.showModal();
      });
      if (trainDialog.hasAttribute("data-open")) trainDialog.showModal();
      var trainForm = trainDialog.querySelector("form");
      if (trainForm) {
        trainForm.addEventListener("submit", function () {
          var btn = document.getElementById("train-submit");
          if (btn) { btn.disabled = true; btn.textContent = "Starting…"; }
        });
      }
    }

    var box = document.getElementById("train-progress");
    if (!box || (box.dataset.status !== "running" && box.dataset.status !== "pending")) return;
    var fill = document.getElementById("train-progress-fill");
    var label = document.getElementById("train-progress-text");
    var bar = box.querySelector("[role=progressbar]");
    function pollTrain() {
      fetch(box.dataset.statusUrl, { headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (s) {
          var pct = s.total ? (s.processed / s.total) * 100 : 0;
          if (fill) fill.style.width = pct + "%";
          if (bar) {
            bar.setAttribute("aria-valuenow", s.processed);
            bar.setAttribute("aria-valuemax", s.total);
          }
          if (label) {
            label.textContent = "Progress: " + s.processed + " / " + s.total + " models"
              + (s.message ? " · " + s.message : "");
          }
          if (s.status !== "running" && s.status !== "pending") {
            var u = new URL(window.location.href);
            u.searchParams.set("run", s.id);
            u.searchParams.set("toast", "1");
            window.location.replace(u.toString());
          } else setTimeout(pollTrain, 2500);
        })
        .catch(function () { setTimeout(pollTrain, 5000); });
    }
    setTimeout(pollTrain, 1500);
  };

  EIC.initDataset = function () {
    var el = document.getElementById("dataset-data");
    if (!el || !window.Chart) return;
    var d = JSON.parse(el.textContent);
    new Chart(document.getElementById("dataset-chart"), {
      type: "bar",
      data: { labels: d.labels, datasets: [{ label: "Images", data: d.values, backgroundColor: cssVar("--brand"), borderRadius: 4 }] },
      options: {
        maintainAspectRatio: false, animation: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { title: function (i) { return d.full[i[0].dataIndex]; } } } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid: { color: cssVar("--accent") } } }
      }
    });
  };

  function normalizeFullName(value) {
    return String(value || "")
      .replace(/[\t\r\n]+/g, " ")
      .replace(/ +/g, " ")
      .trim()
      .split(" ")
      .filter(Boolean)
      .map(function (word) {
        return word.split(/([-'])/).map(function (piece) {
          if (piece === "-" || piece === "'") return piece;
          if (!piece) return "";
          return piece.charAt(0).toUpperCase() + piece.slice(1).toLowerCase();
        }).join("");
      })
      .join(" ");
  }

  EIC.initUserForm = function () {
    var fields = document.querySelectorAll("[data-normalize-name]");
    if (!fields.length) return;
    function applyOne(field) {
      var next = normalizeFullName(field.value);
      if (next !== field.value) field.value = next;
    }
    function applyAll() {
      fields.forEach(applyOne);
    }
    fields.forEach(function (field) {
      field.addEventListener("blur", function () { applyOne(field); });
    });
    var form = fields[0].closest("form");
    if (form) form.addEventListener("submit", applyAll);
  };

  EIC.initUsers = function () {
    var dialog = document.getElementById("user-create-dialog");
    var openBtn = document.getElementById("user-create-open");
    if (dialog) {
      wireDialog(dialog);
      if (dialog.hasAttribute("data-open")) dialog.showModal();
    }
    if (openBtn && dialog) {
      openBtn.addEventListener("click", function () { dialog.showModal(); });
    }
    EIC.initUserForm();
  };

  EIC.initAgencies = function () {
    var dialog = document.getElementById("agency-create-dialog");
    var openBtn = document.getElementById("agency-create-open");
    if (dialog) {
      wireDialog(dialog);
      if (dialog.hasAttribute("data-open")) dialog.showModal();
    }
    if (openBtn && dialog) {
      openBtn.addEventListener("click", function () { dialog.showModal(); });
    }
  };
})();
