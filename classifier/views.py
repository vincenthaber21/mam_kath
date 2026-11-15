import csv
import re
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import VerificationForm
from .labels import LABEL_NAMES, LABELS, label_name
from .models import Classification
from .services import active_model, classify_upload

PAGE_SIZE = 20


def front_page(request):
    """Public introduction to the research prototype and its workflow."""
    return render(request, "frontpage.html")


@login_required
def classify_page(request):
    error = None
    reference = ""
    if request.method == "POST":
        reference = request.POST.get("reference_label", "")
        upload = request.FILES.get("image")
        if upload is None:
            error = "Choose or capture an image first."
        else:
            rec = classify_upload(upload, reference, request.user)
            if rec.failed:
                messages.error(request, f"Classification failed: {rec.error}")
            return redirect("result", pk=rec.pk)
    return render(request, "classifier/classify.html", {
        "active": active_model(),
        "labels": [(l, LABEL_NAMES[l]) for l in LABELS],
        "reference": reference,
        "error": error,
        "nav": "classify",
    }, status=400 if error else 200)


@login_required
def result_page(request, pk):
    rec = get_object_or_404(Classification.objects.select_related("model"), pk=pk)
    initial = {"verification": rec.verification or "correct", "actual_label": rec.actual_label}
    form = VerificationForm(request.POST or None, record=rec, initial=initial)
    if request.method == "POST" and form.is_valid():
        rec.verification = form.cleaned_data["verification"]
        rec.actual_label = form.cleaned_data["actual_label"] or ""
        rec.save(update_fields=["verification", "actual_label"])
        messages.success(request, f"Record {rec.record_no} saved to the log.")
        return redirect("history")
    other_labels = [(l, LABEL_NAMES[l]) for l in LABELS if l != rec.predicted_label]
    return render(request, "classifier/result.html", {
        "rec": rec,
        "form": form,
        "scores": [(label_name(l), v) for l, v in rec.sorted_scores()],
        "other_labels": other_labels,
        "nav": "history",
    })


def parse_filters(params):
    search = (params.get("search") or "").strip()
    predicted = params.get("predicted") if params.get("predicted") in LABELS else ""
    status = params.get("status") if params.get("status") in ("success", "failed") else ""
    day = params.get("date") or ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        day = ""
    return {"search": search, "predicted": predicted, "status": status, "date": day}


def filtered_queryset(filters):
    qs = Classification.objects.select_related("model")
    s = filters["search"]
    if s:
        digits = s.lstrip("#").lstrip("0") or ("0" if s.lstrip("#") else "")
        q = Q(filename__icontains=s)
        if digits.isdigit():
            q |= Q(pk=int(digits))
        qs = qs.filter(q)
    if filters["predicted"]:
        qs = qs.filter(predicted_label=filters["predicted"])
    if filters["status"]:
        qs = qs.filter(status=filters["status"])
    if filters["date"]:
        try:
            day = date.fromisoformat(filters["date"])
            qs = qs.filter(created_at__date=day)
        except ValueError:
            pass
    return qs


@login_required
def history_page(request):
    filters = parse_filters(request.GET)
    page = Paginator(filtered_queryset(filters), PAGE_SIZE).get_page(request.GET.get("page"))
    query = "&".join(f"{k}={v}" for k, v in filters.items() if v)
    return render(request, "classifier/history.html", {
        "page": page,
        "filters": filters,
        "query": query,
        "labels": [(l, LABEL_NAMES[l]) for l in LABELS],
        "nav": "history",
    })


@login_required
def history_export(request):
    filters = parse_filters(request.GET)
    stamp = timezone.localdate().isoformat()
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="classification_log_{stamp}.csv"'
    w = csv.writer(response)
    w.writerow([
        "id", "created_at", "filename", "width", "height", "size_kb", "model", "predicted_label", "confidence",
        *[f"score_{l}" for l in LABELS], "low_confidence", "inference_ms", "reference_label", "match",
        "verification", "actual_label", "status", "error", "demo",
    ])
    for c in filtered_queryset(filters).iterator():
        w.writerow([
            c.pk, timezone.localtime(c.created_at).isoformat(), c.filename, c.width, c.height, c.size_kb,
            str(c.model) if c.model else "", c.predicted_label,
            "" if c.confidence is None else f"{c.confidence:.4f}",
            *[f"{float(c.scores.get(l, 0)):.4f}" if c.scores else "" for l in LABELS],
            c.low_confidence, c.inference_ms, c.reference_label,
            ("yes" if c.is_match else "no") if c.has_match else "", c.verification, c.actual_label,
            c.status, c.error, c.demo,
        ])
    return response
