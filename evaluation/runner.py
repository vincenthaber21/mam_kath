"""Run a labelled test-set .zip through a model in a background thread."""
import logging
import posixpath
import threading
import zipfile

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import close_old_connections, connection
from django.utils import timezone

from classifier.labels import LABELS
from classifier.services import ClassificationError, open_image, predict

from . import metrics
from .models import Evaluation, Misclassified

log = logging.getLogger(__name__)
IMAGE_EXT = (".jpg", ".jpeg", ".png")
MAX_MISCLASSIFIED = 60
MAX_MEMBERS = 50_000


class TestSetError(Exception):
    pass


def list_images(zf):
    """Return [(member_name, label)] for <label>/<file> entries; tolerates one wrapping folder."""
    names = [i.filename for i in zf.infolist() if not i.is_dir()]
    if len(names) > MAX_MEMBERS:
        raise TestSetError(f"The zip has more than {MAX_MEMBERS} files.")
    names = [n for n in names if "__MACOSX" not in n and not posixpath.basename(n).startswith(".")]
    items = []
    for n in names:
        if not n.lower().endswith(IMAGE_EXT) or ".." in n.split("/"):
            continue
        parts = [p for p in n.split("/") if p]
        label = next((p.lower() for p in parts[:-1] if p.lower() in LABELS), None)
        if label:
            items.append((n, label))
    if not items:
        raise TestSetError(
            "No images found. The zip needs one folder per category: " + ", ".join(f"{l}/" for l in LABELS)
        )
    return sorted(items)


def run(evaluation_id):
    close_old_connections()
    ev = Evaluation.objects.select_related("model").get(pk=evaluation_id)
    try:
        _run(ev)
    except Exception as exc:  # never leave an evaluation stuck at "running"
        log.exception("Evaluation %s failed", evaluation_id)
        Evaluation.objects.filter(pk=ev.pk).update(status="failed", error=str(exc), finished_at=timezone.now())
    finally:
        if not settings.EVALUATION_SYNC:
            connection.close()


def _run(ev):
    meta = ev.model
    with zipfile.ZipFile(ev.test_set.path) as zf:
        items = list_images(zf)
        Evaluation.objects.filter(pk=ev.pk).update(total=len(items))
        y_true, y_pred, times = [], [], []
        failed, demo_used, saved_wrong = 0, False, 0
        for i, (name, actual) in enumerate(items, start=1):
            try:
                data = zf.read(name)
                img = open_image(data)
                result, demo = predict(meta, img)
            except ClassificationError as exc:
                if "No active model" in str(exc) or "no model file" in str(exc) or "TensorFlow" in str(exc):
                    raise
                failed += 1
            except Exception:
                failed += 1
            else:
                demo_used = demo_used or demo
                y_true.append(actual)
                y_pred.append(result["predicted_label"])
                times.append(result["inference_ms"])
                if result["predicted_label"] != actual and saved_wrong < MAX_MISCLASSIFIED:
                    m = Misclassified(
                        evaluation=ev, filename=posixpath.basename(name), actual=actual,
                        predicted=result["predicted_label"], confidence=result["confidence"],
                    )
                    m.image.save(f"{ev.pk}_{i}_{posixpath.basename(name)}", ContentFile(data), save=True)
                    saved_wrong += 1
            if i % 5 == 0 or i == len(items):
                Evaluation.objects.filter(pk=ev.pk).update(processed=i, failed=failed)

    result = metrics.compute(y_true, y_pred)
    timing = metrics.timing(times)
    Evaluation.objects.filter(pk=ev.pk).update(
        status="done", processed=len(items), failed=failed, accuracy=result["accuracy"], metrics=result,
        inference_ms=timing, demo=demo_used, finished_at=timezone.now(),
    )
    if ev.update_model_metrics and meta is not None and not demo_used and y_true:
        meta.test_accuracy = result["accuracy"]
        meta.avg_inference_ms = timing["mean"]
        meta.save(update_fields=["test_accuracy", "avg_inference_ms"])


def start(evaluation):
    if settings.EVALUATION_SYNC:
        run(evaluation.pk)
    else:
        threading.Thread(target=run, args=(evaluation.pk,), daemon=True).start()
