from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from classifier.labels import LABEL_SHORT, LABELS, label_name
from classifier.services import active_model, preload_models_in_use, trained_models

from . import runner
from .forms import ModelUploadForm, TrainModelsForm
from .overfitting import GAP_OVERFIT, GAP_WATCH
from .models import DatasetInfo, DatasetSplit, MLModel, SelectionSetting, TrainingRun
from .training import ARCHS


def _models_context(form=None, train_form=None, train_run=None):
    active = active_model(sync=True)  # in auto/voting mode this also syncs the Active badge to the best model
    models = list(MLModel.objects.all())
    setting = SelectionSetting.get()
    voters = trained_models()
    charts = {
        str(m.id): {"name": f"{m.name} v{m.version}", "history": m.history or [], "fit": m.fit.as_dict()}
        for m in models
    }
    busy = bool(train_run and train_run.status in ("pending", "running"))
    return {
        "models": models,
        "chart_default": (active or (models[0] if models else None)),
        "charts": charts,
        "form": form or ModelUploadForm(),
        "train_form": train_form or TrainModelsForm(),
        "train_run": train_run,
        "training_busy": busy,
        "arch_names": {k: v[0] for k, v in ARCHS.items()},
        "selection": setting,
        "selection_modes": SelectionSetting.MODES,
        "active": active,
        "voters": voters,
        "voting_ids": {m.pk for m in voters} if setting.mode == "voting" and len(voters) >= 2 else set(),
        "fit_watch_pts": round(GAP_WATCH * 100),
        "fit_overfit_pts": round(GAP_OVERFIT * 100),
        "nav": "models",
    }


def _resolve_train_run(request):
    run_id = request.GET.get("run", "")
    if run_id.isdigit():
        return get_object_or_404(TrainingRun, pk=int(run_id))
    return TrainingRun.objects.filter(status__in=("pending", "running")).first() or TrainingRun.objects.first()


@login_required
def models_page(request):
    train_run = _resolve_train_run(request)
    if train_run and train_run.status == "done" and request.GET.get("toast") == "1":
        n = len(train_run.model_ids or [])
        messages.success(request, f"Training finished — {n} model(s) registered.")
    return render(request, "registry/models.html", _models_context(train_run=train_run))


@login_required
@require_POST
def upload_model(request):
    form = ModelUploadForm(request.POST, request.FILES)
    if form.is_valid():
        m = form.save()
        messages.success(request, f"{m.name} v{m.version} uploaded. Press Set active to use it.")
        return redirect("models")
    ctx = _models_context(form=form, train_run=_resolve_train_run(request))
    ctx["upload_open"] = True
    return render(request, "registry/models.html", ctx, status=400)


@login_required
@require_POST
def activate_model(request, pk):
    m = get_object_or_404(MLModel, pk=pk)
    m.is_active = True
    m.save()
    setting = SelectionSetting.get()
    if setting.mode != "manual":  # choosing a model by hand switches off automatic selection / voting
        setting.mode = "manual"
        setting.save()
    messages.success(request, f"{m.name} v{m.version} is now the active model (manual selection).")
    return redirect("models")


@login_required
@require_POST
def set_selection_mode(request):
    mode = request.POST.get("mode", "")
    if mode not in dict(SelectionSetting.MODES):
        messages.error(request, "Unknown selection mode.")
        return redirect("models")
    setting = SelectionSetting.get()
    setting.mode = mode
    setting.save()
    active = active_model(sync=True)
    preload_models_in_use()  # so the first classification after switching is not a cold start
    if mode == "auto":
        text = f"Automatic selection on: {active} (highest validation accuracy) classifies new images." if active \
            else "Automatic selection on. Train or upload a model to use it."
    elif mode == "voting":
        n = len(trained_models())
        text = (f"Voting on: all {n} trained models classify each image; the majority wins and the most "
                "confident model decides ties.") if n >= 2 else \
            "Voting on, but only one trained model exists, so it is used alone until you add another."
    else:
        text = f"Manual selection on: {active} stays active until you choose another." if active \
            else "Manual selection on. Press Set active on a model."
    messages.success(request, text)
    return redirect("models")


@login_required
@require_POST
def start_training(request):
    runner.fail_stale_runs()
    if TrainingRun.objects.filter(status__in=("pending", "running")).exists():
        messages.error(request, "A training run is already in progress. Wait for it to finish.")
        return redirect("models")

    form = TrainModelsForm(request.POST)
    if not form.is_valid():
        ctx = _models_context(train_form=form, train_run=_resolve_train_run(request))
        ctx["train_open"] = True
        return render(request, "registry/models.html", ctx, status=400)

    job = TrainingRun.objects.create(
        created_by=request.user,
        archs=form.cleaned_data["archs"],
        dataset_path=form.cleaned_data["dataset_path"],
        epochs=form.cleaned_data["epochs"],
        fine_tune_epochs=form.cleaned_data["fine_tune_epochs"],
        model_version=form.cleaned_data["model_version"],
        activate_best=form.cleaned_data["activate_best"],
        total=len(form.cleaned_data["archs"]),
        message="Queued",
    )
    runner.start(job)
    messages.info(
        request,
        f"Training started for {len(job.archs)} model(s). This page updates by itself.",
    )
    return redirect(job.get_absolute_url())


@login_required
def training_status(request, pk):
    job = get_object_or_404(TrainingRun, pk=pk)
    return JsonResponse({
        "id": job.pk,
        "status": job.status,
        "processed": job.processed,
        "total": job.total,
        "current_arch": job.current_arch,
        "message": job.message,
        "error": job.error,
        "progress_pct": job.progress_pct,
    })


def dataset_summary():
    counts = {(s.label, s.split): s.count for s in DatasetSplit.objects.all()}
    rows = []
    for label in LABELS:
        train = counts.get((label, "train"), 0)
        val = counts.get((label, "val"), 0)
        test = counts.get((label, "test"), 0)
        if train or val or test:
            rows.append({"label": label, "name": label_name(label), "short": LABEL_SHORT[label],
                         "train": train, "val": val, "test": test, "total": train + val + test})
    totals = {k: sum(r[k] for r in rows) for k in ("train", "val", "test", "total")}
    for r in rows:
        r["share"] = (r["total"] / totals["total"]) if totals["total"] else None
    return rows, totals


@login_required
def dataset_page(request):
    rows, totals = dataset_summary()
    info = DatasetInfo.get()
    total = totals["total"]
    split_share = {k: (round(totals[k] / total * 100) if total else None) for k in ("train", "val", "test")}
    chart = {"labels": [r["short"] for r in rows], "full": [r["name"] for r in rows], "values": [r["total"] for r in rows]}
    return render(request, "registry/dataset.html", {
        "rows": rows, "totals": totals, "info": info, "split_share": split_share, "chart": chart, "nav": "dataset",
    })
