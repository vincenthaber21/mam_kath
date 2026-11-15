from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from classifier.labels import LABEL_SHORT, LABELS, label_name

from .forms import ModelUploadForm
from .models import DatasetInfo, DatasetSplit, MLModel


def _models_context(form=None):
    models = list(MLModel.objects.all())
    active = next((m for m in models if m.is_active), None)
    charts = {
        str(m.id): {"name": f"{m.name} v{m.version}", "history": m.history or []}
        for m in models
    }
    return {
        "models": models,
        "chart_default": (active or (models[0] if models else None)),
        "charts": charts,
        "form": form or ModelUploadForm(),
        "nav": "models",
    }


@login_required
def models_page(request):
    return render(request, "registry/models.html", _models_context())


@login_required
@require_POST
def upload_model(request):
    form = ModelUploadForm(request.POST, request.FILES)
    if form.is_valid():
        m = form.save()
        messages.success(request, f"{m.name} v{m.version} uploaded. Press Set active to use it.")
        return redirect("models")
    ctx = _models_context(form)
    ctx["upload_open"] = True
    return render(request, "registry/models.html", ctx, status=400)


@login_required
@require_POST
def activate_model(request, pk):
    m = get_object_or_404(MLModel, pk=pk)
    m.is_active = True
    m.save()
    messages.success(request, f"{m.name} v{m.version} is now the active model.")
    return redirect("models")


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
