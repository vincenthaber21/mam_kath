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
    var url = null;

    function showError(msg) { err.textContent = msg; err.hidden = !msg; }

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

    document.getElementById("gallery-btn").addEventListener("click", function () {
      input.removeAttribute("capture"); input.accept = "image/jpeg,image/png"; input.click();
    });
    document.getElementById("camera-btn").addEventListener("click", function () {
      input.setAttribute("capture", "environment"); input.accept = "image/*"; input.click();
    });
    form.addEventListener("submit", function (e) {
      if (!input.files.length) { e.preventDefault(); showError("Choose or capture an image first."); return; }
      btn.disabled = true; btn.textContent = "Classifying…";
    });
  };

  EIC.initVerification = function () {
    var sel = document.getElementById("verification");
    var wrap = document.getElementById("actual-wrap");
    sel.addEventListener("change", function () { wrap.hidden = sel.value !== "incorrect"; });
  };

  EIC.initHistory = function () {
    var form = document.getElementById("filters");
    form.querySelectorAll("[data-autosubmit]").forEach(function (el) {
      el.addEventListener("change", function () { form.submit(); });
    });
    var search = document.getElementById("search");
    var timer = null;
    var initial = search.value;
    search.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { if (search.value.trim() !== initial.trim()) form.submit(); }, 500);
    });
    if (initial) { search.focus(); search.setSelectionRange(initial.length, initial.length); }
    document.querySelectorAll(".row-link").forEach(function (row) {
      function go() { window.location.href = row.dataset.href; }
      row.addEventListener("click", function (e) { if (!e.target.closest("a")) go(); });
      row.addEventListener("keydown", function (e) { if (e.key === "Enter") go(); });
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
})();
