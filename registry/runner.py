"""Start a multi-architecture training job in a background thread (Models page)."""
import logging
import threading

from django.conf import settings
from django.db import close_old_connections, connection
from django.utils import timezone

from .training import train_candidates

log = logging.getLogger(__name__)


def run(run_id):
    close_old_connections()
    from .models import TrainingRun

    job = TrainingRun.objects.get(pk=run_id)
    try:
        _run(job)
    except Exception as exc:  # never leave a run stuck at "running"
        log.exception("TrainingRun %s failed", run_id)
        TrainingRun.objects.filter(pk=job.pk).update(
            status="failed", error=str(exc), finished_at=timezone.now(),
        )
    finally:
        if not settings.TRAINING_SYNC:
            connection.close()


def _run(job):
    from .models import TrainingRun

    TrainingRun.objects.filter(pk=job.pk).update(
        status="running",
        total=len(job.archs),
        processed=0,
        message=f"Starting {len(job.archs)} model(s)",
        error="",
    )

    def on_progress(**kwargs):
        fields = {
            "processed": kwargs.get("processed", 0),
            "total": kwargs.get("total", len(job.archs)),
            "current_arch": kwargs.get("current_arch", ""),
            "message": kwargs.get("message", ""),
        }
        if "model_ids" in kwargs:
            fields["model_ids"] = kwargs["model_ids"]
        TrainingRun.objects.filter(pk=job.pk).update(**fields)

    trained = train_candidates(
        job.dataset_path,
        job.archs,
        epochs=job.epochs,
        fine_tune_epochs=job.fine_tune_epochs,
        model_version=job.model_version,
        activate=job.activate_best,
        quiet=True,
        on_progress=on_progress,
    )
    TrainingRun.objects.filter(pk=job.pk).update(
        status="done",
        processed=len(job.archs),
        total=len(job.archs),
        message=f"Done — {len(trained)} model(s) registered",
        model_ids=[m.id for m in trained],
        finished_at=timezone.now(),
    )


def start(job):
    if settings.TRAINING_SYNC:
        run(job.pk)
    else:
        threading.Thread(target=run, args=(job.pk,), daemon=True).start()
