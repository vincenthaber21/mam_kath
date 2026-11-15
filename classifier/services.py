"""Image validation and inference.

The active Keras model is loaded once and cached in memory; it is reloaded
automatically when a different model is activated. TensorFlow is imported
lazily so the website (and its tests) start without it.
"""
import hashlib
import io
import threading
import time

import numpy as np
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

from .labels import LABELS


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

_cache = {"key": None, "model": None}
_lock = threading.Lock()


def _preprocess_fn(name):
    import tensorflow as tf  # noqa: WPS433 (lazy import keeps startup fast)

    return {
        "efficientnet": tf.keras.applications.efficientnet.preprocess_input,
        "mobilenet_v2": tf.keras.applications.mobilenet_v2.preprocess_input,
        "resnet50": tf.keras.applications.resnet50.preprocess_input,
    }[name]


def _load_keras(meta):
    key = (meta.pk, meta.file.name)
    with _lock:
        if _cache["key"] != key:
            try:
                import tensorflow as tf
            except ImportError:
                raise ClassificationError(
                    "TensorFlow is not installed on the server. Run: pip install tensorflow-cpu"
                )
            try:
                _cache["model"] = tf.keras.models.load_model(meta.file.path, compile=False)
            except Exception as exc:  # corrupted or incompatible model file
                raise ClassificationError(f"Could not load model file: {exc}")
            _cache["key"] = key
        return _cache["model"]


def _keras_predict(meta, img):
    model = _load_keras(meta)
    size = meta.input_size or 224
    arr = np.asarray(img.convert("RGB").resize((size, size)), dtype=np.float32)
    x = _preprocess_fn(meta.preprocessing)(np.expand_dims(arr, 0))
    t0 = time.perf_counter()
    probs = model.predict(x, verbose=0)[0]
    ms = (time.perf_counter() - t0) * 1000
    return np.asarray(probs, dtype=np.float64), ms


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


def active_model():
    from registry.models import MLModel

    return MLModel.objects.filter(is_active=True).first()


# ---------------------------------------------------------------- record

def classify_upload(upload, reference_label="", user=None):
    """Validate, classify and log one upload. Always returns a saved Classification (failed ones too)."""
    from .models import Classification

    rec = Classification(
        user=user if user is not None and user.is_authenticated else None,
        filename=(getattr(upload, "name", "") or "")[:255],
        size_kb=round(upload.size / 1024) if upload is not None else None,
        reference_label=reference_label if reference_label in LABELS else "",
    )
    try:
        data, img = read_and_validate(upload)
    except ClassificationError as exc:
        rec.status, rec.error = "failed", str(exc)
        rec.save()
        return rec

    rec.width, rec.height = img.size
    rec.image.save(upload.name, ContentFile(data), save=False)
    meta = active_model()
    rec.model = meta
    try:
        result, demo = predict(meta, img)
    except ClassificationError as exc:
        rec.status, rec.error = "failed", str(exc)
    except Exception as exc:  # inference crashed: keep the attempt in the log
        rec.status, rec.error = "failed", f"Inference error: {exc}"
    else:
        for key, value in result.items():
            setattr(rec, key, value)
        rec.demo = demo
    rec.save()
    return rec
