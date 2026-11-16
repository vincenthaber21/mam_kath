import os
import sys

from django.apps import AppConfig

# Management commands that must not pay TensorFlow startup cost.
_SKIP_CMDS = {
    "test", "migrate", "makemigrations", "shell", "dbshell", "check",
    "collectstatic", "createsuperuser", "changepassword", "flush",
    "train_models", "seed_demo", "import_dataset_counts", "build_dataset",
}


class ClassifierConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "classifier"
    verbose_name = "Classifications"

    def ready(self):
        cmd = sys.argv[1] if len(sys.argv) > 1 else ""
        if cmd in _SKIP_CMDS:
            return

        # Under runserver autoreload, only warm the child process (RUN_MAIN=true).
        # With --noreload there is a single process and RUN_MAIN is unset — still warm.
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true" and "--noreload" not in sys.argv:
            return

        # Only preload when we are clearly serving HTTP (or an explicit opt-in).
        serving = (
            "runserver" in sys.argv
            or os.environ.get("EIC_WARMUP") == "1"
            or any(name in sys.argv[0] for name in ("gunicorn", "uvicorn", "daphne"))
            or any(arg.endswith(("wsgi.py", "asgi.py")) for arg in sys.argv)
        )
        if not serving:
            return

        from .services import preload_active_model

        preload_active_model()
