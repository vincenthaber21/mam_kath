import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from classifier.labels import LABEL_SHORT, label_name
from registry.models import MLModel

from . import runner
from .forms import EvaluationForm
from .models import Evaluation


def _report(ev):
    if ev is None or ev.status != "done":
        return None
    m = ev.metrics
    labels = m.get("labels", [])
    matrix = m.get("confusion_matrix", [])
    peak = max([1] + [v for row in matrix for v in row])
    rows = []
    for i, label in enumerate(labels):
        cells = []
        for j, v in enumerate(matrix[i] if i < len(matrix) else []):
            cells.append({"value": v, "diag": i == j, "alpha": round(v / peak * 0.85, 2)})
        rows.append({"label": label, "name": label_name(label), "short": LABEL_SHORT.get(label, label), "cells": cells})
    return {
        "labels": [{"label": l, "short": LABEL_SHORT.get(l, l), "name": label_name(l)} for l in labels],
        "matrix": rows,
        "per_class": m.get("per_class", []),
        "macro": m.get("macro", {}),
        "weighted": m.get("weighted", {}),
        "accuracy": ev.accuracy,
        "classified": sum(sum(r) for r in matrix),
        "misclassified": list(ev.misclassified.all()[:24]),
    }


@login_required
def evaluation_page(request):
    form = EvaluationForm()
    if request.method == "POST":
        form = EvaluationForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["test_set"]
            ev = Evaluation.objects.create(
                model=form.cleaned_data["model"], created_by=request.user, test_set=upload,
                test_set_name=upload.name[:255], update_model_metrics=form.cleaned_data["update_model_metrics"],
            )
            runner.start(ev)
            return redirect(ev.get_absolute_url())

    ev = None
    if request.GET.get("id", "").isdigit():
        ev = get_object_or_404(Evaluation.objects.select_related("model"), pk=int(request.GET["id"]))
    elif request.method != "POST":
        ev = Evaluation.objects.select_related("model").first()

    if ev and ev.status == "done" and request.GET.get("toast") == "1":
        messages.success(request, "Evaluation finished.")
    return render(request, "evaluation/evaluation.html", {
        "form": form,
        "ev": ev,
        "report": _report(ev),
        "has_models": MLModel.objects.exists(),
        "recent": Evaluation.objects.select_related("model")[:8],
        "nav": "evaluation",
    }, status=400 if form.errors else 200)


@login_required
def evaluation_status(request, pk):
    ev = get_object_or_404(Evaluation, pk=pk)
    return JsonResponse({"id": ev.pk, "status": ev.status, "processed": ev.processed, "total": ev.total,
                         "failed": ev.failed, "error": ev.error})


@login_required
def evaluation_csv(request, pk):
    ev = get_object_or_404(Evaluation.objects.select_related("model"), pk=pk, status="done")
    m = ev.metrics
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="evaluation_{ev.pk}.csv"'
    w = csv.writer(response)
    w.writerow(["Evaluation", ev.pk])
    w.writerow(["Model", str(ev.model) if ev.model else ""])
    w.writerow(["Test set", ev.test_set_name])
    w.writerow(["Simulated (demo mode)", "yes" if ev.demo else "no"])
    w.writerow(["Accuracy", f"{ev.accuracy:.4f}"])
    w.writerow(["Images", ev.total])
    w.writerow(["Failed attempts", ev.failed])
    t = ev.inference_ms
    w.writerow(["Inference ms (mean/median/min/max)", t.get("mean"), t.get("median"), t.get("min"), t.get("max")])
    w.writerow([])
    w.writerow(["Class", "Precision", "Recall", "F1", "Support"])
    for c in m["per_class"]:
        w.writerow([label_name(c["label"]), f'{c["precision"]:.4f}', f'{c["recall"]:.4f}', f'{c["f1"]:.4f}', c["support"]])
    supp = sum(c["support"] for c in m["per_class"])
    for name, key in (("Macro avg", "macro"), ("Weighted avg", "weighted")):
        w.writerow([name, f'{m[key]["precision"]:.4f}', f'{m[key]["recall"]:.4f}', f'{m[key]["f1"]:.4f}', supp])
    w.writerow([])
    w.writerow(["Confusion matrix (rows = actual / columns = predicted)", *[label_name(l) for l in m["labels"]]])
    for i, row in enumerate(m["confusion_matrix"]):
        w.writerow([label_name(m["labels"][i]), *row])
    return response
