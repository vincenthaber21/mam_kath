"""Start a multi-architecture training job (Models page).

Sync mode (tests): runs in-process.
Otherwise: spawns ``manage.py train_models --run-id=...`` in a detached process so
training survives Django runserver reloads (daemon threads do not).
"""
import logging
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import close_old_connections, connection
from django.utils import timezone

from .training import train_candidates

log = logging.getLogger(__name__)

# Runs left "running" longer than this are treated as dead (e.g. killed server).
STALE_AFTER = timedelta(hours=6)


def fail_stale_runs():
    """Mark abandoned pending/running jobs as failed so a new train can start."""
    from .models import TrainingRun

    cutoff = timezone.now() - STALE_AFTER
    n = TrainingRun.objects.filter(
        status__in=("pending", "running"),
        created_at__lt=cutoff,
    ).update(
        status="failed",
        error="Training did not finish (process stopped or timed out). Start again.",
        finished_at=timezone.now(),
        message="Abandoned",
    )
    return n


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


def _spawn_train_process(job):
    """Detach a manage.py train_models child that updates this TrainingRun."""
    log_dir = Path(settings.MEDIA_ROOT) / "training_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{job.pk}.log"

    cmd = [
        sys.executable,
        str(Path(settings.BASE_DIR) / "manage.py"),
        "train_models",
        job.dataset_path,
        "--archs",
        ",".join(job.archs),
        "--epochs",
        str(job.epochs),
        "--fine-tune-epochs",
        str(job.fine_tune_epochs),
        "--model-version",
        job.model_version,
        "--run-id",
        str(job.pk),
        "--quiet",
    ]
    if not job.activate_best:
        cmd.append("--no-activate")

    kwargs = {
        "cwd": str(settings.BASE_DIR),
        "stdout": open(log_path, "a", encoding="utf-8"),  # noqa: SIM115 — kept open for child
        "stderr": subprocess.STDOUT,
    }
    if sys.platform == "win32":
        # Survive parent exit / runserver autoreload on Windows.
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        kwargs["close_fds"] = False
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kwargs)
    log.info("TrainingRun %s started as pid %s (log %s)", job.pk, proc.pid, log_path)
    return proc


def start(job):
    fail_stale_runs()
    if settings.TRAINING_SYNC:
        run(job.pk)
    else:
        _spawn_train_process(job)
