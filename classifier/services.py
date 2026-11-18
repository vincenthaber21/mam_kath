"""Image validation and inference.

The active Keras model is loaded once and cached in memory; it is reloaded
automatically when a different model is activated. TensorFlow is imported
lazily so the website (and its tests) start without it.
"""
import hashlib
import io
import logging
import os
import sys
import threading
import time

import numpy as np
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

from .labels import LABELS

logger = logging.getLogger(__name__)


class ClassificationError(Exception):
    """A user-facing reason why an image could not be classified."""


# ---------------------------------------------------------------- validation

ALLOWED_FORMATS = {"JPEG", "PNG"}


def read_and_validate(upload):
    """Return (bytes, PIL.Image) for a JPG/PNG upload of at most MAX_IMAGE_MB, or raise ClassificationError."""
    max_bytes = settings.MAX_IMAGE_MB * 1024 * 1024
    if upload is None:
        raise ClassificationError("Choose or capture an image first.")
    if upload.size == 0:
        raise ClassificationError("This file is empty.")
    if upload.size > max_bytes:
        raise ClassificationError(
            f"This image is {upload.size / 1024 / 1024:.1f} MB. The maximum is {settings.MAX_IMAGE_MB} MB."
        )
    data = upload.read()
    return data, open_image(data)


def open_image(data):
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()  # detects truncated / corrupt files
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ClassificationError("The file is not a readable image.")
    if fmt not in ALLOWED_FORMATS:
        raise ClassificationError("Only JPG or PNG images are accepted.")
    img = Image.open(io.BytesIO(data))  # verify() leaves the image unusable; reopen
    img.load()
    return img


# ---------------------------------------------------------------- model cache

# (model pk, file name) -> (keras model, preprocess fn). Several models stay loaded so voting is fast.
_cache = {}
_lock = threading.Lock()
_warmup_started = False
# No background preloading under "manage.py test" (threads cannot share the in-memory test database).
_PRELOAD = not (len(sys.argv) > 1 and sys.argv[1] == "test")


def _silence_tf_logs():
    # Must be set before the first TensorFlow import.
    # Keep oneDNN on (do not set TF_ENABLE_ONEDNN_OPTS=0) — it speeds up CPU inference.
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


def _import_tf():
    _silence_tf_logs()
    import tensorflow as tf  # noqa: WPS433 (lazy import keeps startup fast)

    return tf


def _preprocess_fn(name):
    tf = _import_tf()
    return {
        "efficientnet": tf.keras.applications.efficientnet.preprocess_input,
        "mobilenet_v2": tf.keras.applications.mobilenet_v2.preprocess_input,
        "resnet50": tf.keras.applications.resnet50.preprocess_input,
    }[name]


def _forward(model, x):
    """Single-image forward pass. Prefer model() over model.predict() — predict() has
    large per-call overhead for batch size 1."""
    out = model(x, training=False)
    return np.asarray(out[0], dtype=np.float64)


def _warmup(model, size):
    """Force graph tracing so the first real upload is not the cold compile."""
    dummy = np.zeros((1, size, size, 3), dtype=np.float32)
    _forward(model, dummy)


def _load_keras(meta):
    key = (meta.pk, meta.file.name)
    with _lock:
        if key not in _cache:
            for old in [k for k in _cache if k[0] == meta.pk]:  # model file was replaced
                del _cache[old]
            try:
                tf = _import_tf()
            except ImportError:
                raise ClassificationError(
                    "TensorFlow is not installed on the server. Run: pip install tensorflow-cpu"
                )
            try:
                model = tf.keras.models.load_model(meta.file.path, compile=False)
            except Exception as exc:  # corrupted or incompatible model file
                raise ClassificationError(f"Could not load model file: {exc}")
            size = meta.input_size or 224
            _warmup(model, size)
            _cache[key] = (model, _preprocess_fn(meta.preprocessing))
        return _cache[key]


def _keras_predict(meta, img):
    model, preprocess = _load_keras(meta)
    size = meta.input_size or 224
    arr = np.asarray(img.convert("RGB").resize((size, size)), dtype=np.float32)
    x = preprocess(np.expand_dims(arr, 0))
    t0 = time.perf_counter()
    probs = _forward(model, x)
    ms = (time.perf_counter() - t0) * 1000
    return probs, ms


def ensure_model_loaded(meta=None):
    """Import TensorFlow and load+warm the model(s) the current selection mode uses
    (safe to call from a background thread)."""
    metas = [meta] if meta is not None else models_in_use()
    metas = [m for m in metas if m is not None and m.file]
    for m in metas:
        _load_keras(m)
    return bool(metas)


def preload_active_model():
    """Start a one-shot background load so the first classify is not cold."""
    global _warmup_started
    if not _PRELOAD:
        return
    with _lock:
        if _warmup_started:
            return
        _warmup_started = True

    def _run():
        try:
            if ensure_model_loaded():
                logger.info("Active model preloaded for classify.")
        except Exception:
            logger.exception("Model preload failed; first classify will load on demand.")

    threading.Thread(target=_run, name="eic-model-preload", daemon=True).start()


def preload_models_in_use():
    """Background-load every model the current selection mode needs (called when the mode changes).
    The model list is read here, in the request thread; the background thread only loads files."""
    if not _PRELOAD:
        return
    metas = [m for m in models_in_use() if m is not None and m.file]

    def _run():
        try:
            for m in metas:
                _load_keras(m)
        except Exception:
            logger.exception("Preloading models for the new selection mode failed.")

    threading.Thread(target=_run, name="eic-model-preload-mode", daemon=True).start()


def _demo_predict(img):
    """Deterministic simulated scores (same photo -> same result). Only used in demo mode."""
    small = img.convert("RGB").resize((32, 32))
    seed = int(hashlib.sha256(small.tobytes()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    alpha = np.full(len(LABELS), 0.6)
    alpha[seed % len(LABELS)] = 4.0
    probs = rng.dirichlet(alpha)
    ms = (time.perf_counter() - t0) * 1000 + 60 + rng.random() * 90
    return probs, ms


def predict(meta, img):
    """Run one image through `meta` (an MLModel or None). Returns (result dict, used_demo)."""
    if meta is not None and meta.file:
        probs, ms = _keras_predict(meta, img)
        labels = meta.labels_json or LABELS
        demo = False
    elif settings.EIC_DEMO_MODE:
        probs, ms = _demo_predict(img)
        labels = LABELS
        demo = True
    elif meta is None:
        raise ClassificationError("No active model. Set one on the Models page.")
    else:
        raise ClassificationError(f"{meta} has no model file. Upload the .h5/.keras file on the Models page.")

    if len(probs) != len(labels):
        raise ClassificationError(
            f"The model returned {len(probs)} scores but {len(labels)} labels are configured."
        )
    total = float(np.sum(probs))
    if total > 0 and abs(total - 1.0) > 1e-3:  # model without a softmax layer
        exp = np.exp(probs - np.max(probs))
        probs = exp / np.sum(exp)
    i = int(np.argmax(probs))
    confidence = float(probs[i])
    return {
        "predicted_label": labels[i],
        "confidence": confidence,
        "scores": {label: round(float(p), 6) for label, p in zip(labels, probs)},
        "inference_ms": round(ms, 1),
        "low_confidence": confidence < settings.LOW_CONFIDENCE_THRESHOLD,
    }, demo


# ---------------------------------------------------------------- model selection

def selection_mode():
    """"auto" (highest validation accuracy), "voting" (all trained models) or "manual" (Set active)."""
    from registry.models import SelectionSetting

    # Read-only (no get_or_create) so it is safe from background threads; no row yet = "auto".
    return SelectionSetting.objects.filter(pk=1).values_list("mode", flat=True).first() or "auto"


def trained_models():
    """Models that have a file, best first: not overfitting, validation accuracy, macro F1, newest."""
    from django.db.models import F

    from registry.models import MLModel

    ranked = list(
        MLModel.objects.exclude(file="").order_by(
            F("val_accuracy").desc(nulls_last=True), F("val_macro_f1").desc(nulls_last=True), "-created_at", "-id",
        )
    )
    # Models flagged as overfitting go last (stable sort keeps the accuracy order otherwise).
    ranked.sort(key=lambda m: m.fit.is_overfit)
    return ranked


def best_model():
    ranked = trained_models()
    return ranked[0] if ranked else None


def active_model(sync=False):
    """The single model the site uses. In auto/voting mode it follows the highest validation accuracy.
    With sync=True (page requests only, never background threads) the Active badge is moved to it."""
    from registry.models import MLModel

    if selection_mode() != "manual":
        best = best_model()
        if best is not None:
            if sync and not best.is_active:
                best.is_active = True
                best.save()  # MLModel.save() deactivates the others
            return best
    return MLModel.objects.filter(is_active=True).first()


def models_in_use(sync=False):
    """All trained models in voting mode (when there are at least two), otherwise the active one."""
    if selection_mode() == "voting":
        ranked = trained_models()
        if len(ranked) >= 2:
            return ranked
    return [active_model(sync=sync)]


def predict_by_vote(metas, img):
    """Every model classifies the image and votes for its top label. The label with the most votes wins;
    on a tie, the label backed by the single most confident model wins. The most confident model among
    the winners is the deciding model: its confidence and class scores are reported.
    Returns (result dict incl. "votes", deciding MLModel)."""
    runs, failures = [], []
    for m in metas:
        try:
            result, _ = predict(m, img)
        except ClassificationError as exc:
            failures.append(f"{m}: {exc}")
            continue
        runs.append((m, result))
    if not runs:
        raise ClassificationError("No model could classify the image. " + " ".join(failures))

    tally = {}
    for _, r in runs:
        tally[r["predicted_label"]] = tally.get(r["predicted_label"], 0) + 1
    top = max(tally.values())
    deciding_meta, deciding = max(
        ((m, r) for m, r in runs if tally[r["predicted_label"]] == top), key=lambda mr: mr[1]["confidence"]
    )
    result = dict(deciding)
    result["inference_ms"] = round(sum(r["inference_ms"] for _, r in runs), 1)
    result["votes"] = [
        {
            "model_id": m.pk,
            "model": f"{m.name} v{m.version}",
            "val_accuracy": m.val_accuracy,
            "label": r["predicted_label"],
            "confidence": round(r["confidence"], 6),
            "inference_ms": r["inference_ms"],
            "deciding": m.pk == deciding_meta.pk,
        }
        for m, r in runs
    ]
    result["vote_count"] = top
    if failures:
        logger.warning("Voting skipped models: %s", "; ".join(failures))
    return result, deciding_meta


# ---------------------------------------------------------------- record

def classify_upload(
    upload,
    reference_label="",
    user=None,
    *,
    notes="",
    location_text="",
    latitude=None,
    longitude=None,
    source="web",
):
    """Validate, classify and log one upload. Always returns a saved Classification (failed ones too)."""
    from .models import Classification

    rec = Classification(
        user=user if user is not None and user.is_authenticated else None,
        filename=(getattr(upload, "name", "") or "")[:255],
        size_kb=round(upload.size / 1024) if upload is not None else None,
        reference_label=reference_label if reference_label in LABELS else "",
        notes=(notes or "")[:2000],
        location_text=(location_text or "")[:255],
        latitude=latitude,
        longitude=longitude,
        source=(source or "web")[:10],
    )
    try:
        data, img = read_and_validate(upload)
    except ClassificationError as exc:
        rec.status, rec.error = "failed", str(exc)
        rec.save()
        return rec

    rec.width, rec.height = img.size
    rec.image.save(upload.name, ContentFile(data), save=False)
    metas = models_in_use(sync=True)
    rec.selection_mode = selection_mode()
    meta = metas[0]
    rec.model = meta
    try:
        if len(metas) > 1:
            result, meta = predict_by_vote(metas, img)
            rec.model = meta  # the model whose prediction was used
            rec.votes = result.pop("votes")
            result.pop("vote_count")
            demo = False
        else:
            result, demo = predict(meta, img)
    except ClassificationError as exc:
        rec.status, rec.error = "failed", str(exc)
    except Exception as exc:  # inference crashed: keep the attempt in the log
        rec.status, rec.error = "failed", f"Inference error: {exc}"
    else:
        for key, value in result.items():
            setattr(rec, key, value)
        rec.demo = demo
        # Below the confidence threshold the image is not assigned to any of the
        # five incident categories (scores are still kept for review).
        if rec.low_confidence:
            rec.predicted_label = ""
    rec.save()
    return rec
