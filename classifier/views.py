import csv
import re
from datetime import date
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import IncidentResponseForm, NotifyAgencyForm, VerificationForm
from .labels import LABEL_NAMES, LABELS, label_name
from .locations import SANTA_MARIA_BARANGAYS, normalize_barangay
from .models import Classification, IncidentResponse, NotifyAgency
from .services import active_model, classify_upload, models_in_use, preload_active_model, selection_mode

PAGE_SIZE = 20
# Santa Maria, Ilocos Sur — default map center when no pin has coordinates.
MAP_DEFAULT_CENTER = {"lat": 17.35712, "lng": 120.49634}
# Municipal outline (medres NAMRIA / PSGC 102926000) so the LGU land is easy to see.
MAP_SANTA_MARIA_BOUNDARY = [
    {"lat": 17.394986, "lng": 120.557548},
    {"lat": 17.395562, "lng": 120.532398},
    {"lat": 17.390840, "lng": 120.519530},
    {"lat": 17.394898, "lng": 120.503376},
    {"lat": 17.392626, "lng": 120.480685},
    {"lat": 17.392824, "lng": 120.458801},
    {"lat": 17.374968, "lng": 120.449029},
    {"lat": 17.361262, "lng": 120.454569},
    {"lat": 17.348017, "lng": 120.445478},
    {"lat": 17.343702, "lng": 120.462631},
    {"lat": 17.334319, "lng": 120.462529},
    {"lat": 17.328327, "lng": 120.476232},
    {"lat": 17.317699, "lng": 120.482106},
    {"lat": 17.326649, "lng": 120.485259},
    {"lat": 17.354308, "lng": 120.484122},
    {"lat": 17.346220, "lng": 120.496189},
    {"lat": 17.344091, "lng": 120.512007},
    {"lat": 17.343605, "lng": 120.538611},
    {"lat": 17.356986, "lng": 120.537814},
    {"lat": 17.371764, "lng": 120.542809},
    {"lat": 17.394986, "lng": 120.557548},
]
MAP_MARKER_COLORS = {
    "fire": "#b91c1c",
    "crime": "#1e3a5f",
    "medical_emergency": "#0f766e",
    "accident": "#c2410c",
    "disaster": "#854d0e",
}


def manager_required(view):
    """Only administrators (or Django staff) may manage notify agencies."""

    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.can_manage_users:
            messages.error(request, "Only administrators can manage notify agencies.")
            return redirect("history")
        return view(request, *args, **kwargs)

    return _wrapped


def front_page(request):
    """Public introduction to the research prototype and its workflow."""
    preview = (
        Classification.objects
        .filter(status="success", demo=False, low_confidence=False)
        .exclude(predicted_label="")
        .select_related("model")
        .order_by("-created_at", "-id")
        .first()
    )
    preview_scores = []
    if preview:
        preview_scores = [
            (label_name(label), score) for label, score in preview.sorted_scores()[:3]
        ]
    return render(request, "frontpage.html", {
        "preview": preview,
        "preview_scores": preview_scores,
        "model_ready": active_model(sync=False) is not None,
    })


def _parse_optional_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@login_required
def classify_page(request):
    error = None
    reference = ""
    notes = ""
    # Prefill from the signed-in user's barangay when set.
    location_text = normalize_barangay(getattr(request.user, "barangay", "") or "")
    latitude = None
    longitude = None
    if request.method == "POST":
        reference = request.POST.get("reference_label", "")
        notes = (request.POST.get("notes") or "").strip()[:2000]
        location_text = normalize_barangay(request.POST.get("location_text") or "")[:255]
        latitude = _parse_optional_float(request.POST.get("latitude"))
        longitude = _parse_optional_float(request.POST.get("longitude"))
        upload = request.FILES.get("image")
        if upload is None:
            error = "Choose or capture an image first."
        else:
            rec = classify_upload(
                upload,
                reference,
                request.user,
                notes=notes,
                location_text=location_text,
                latitude=latitude,
                longitude=longitude,
                source="web",
            )
            if rec.failed:
                messages.error(request, f"Classification failed: {rec.error}")
            return redirect("result", pk=rec.pk)
    # Kick off (or continue) background load so the next POST is not a cold start.
    preload_active_model()
    in_use = models_in_use()
    return render(request, "classifier/classify.html", {
        "active": active_model(sync=True),
        "selection_mode": selection_mode(),
        "voting": in_use if len(in_use) > 1 else [],
        "labels": [(l, LABEL_NAMES[l]) for l in LABELS],
        "barangays": SANTA_MARIA_BARANGAYS,
        "reference": reference,
        "notes": notes,
        "location_text": location_text,
        "latitude": "" if latitude is None else latitude,
        "longitude": "" if longitude is None else longitude,
        "error": error,
        "nav": "classify",
    }, status=400 if error else 200)


def _can_view_incident(user, rec):
    if user.can_monitor_incidents:
        return True
    return rec.user_id == user.id


@login_required
def result_page(request, pk):
    rec = get_object_or_404(
        Classification.objects.select_related("model", "user", "assigned_officer"),
        pk=pk,
    )
    if not _can_view_incident(request.user, rec):
        messages.error(request, "You can only open incidents you reported.")
        return redirect("history")
    default_verification = rec.verification or ("unclear" if not rec.predicted_label and not rec.failed else "correct")
    initial = {"verification": default_verification, "actual_label": rec.actual_label}
    form = VerificationForm(request.POST or None, record=rec, initial=initial)
    if request.method == "POST" and form.is_valid():
        rec.verification = form.cleaned_data["verification"]
        rec.actual_label = form.cleaned_data["actual_label"] or ""
        rec.save(update_fields=["verification", "actual_label"])
        messages.success(request, f"Record {rec.record_no} saved to Incidents.")
        return redirect("history")
    other_labels = [(l, LABEL_NAMES[l]) for l in LABELS if l != rec.predicted_label]
    response_form = IncidentResponseForm(user=request.user)
    responses = rec.responses.select_related("author").all()
    return render(request, "classifier/result.html", {
        "rec": rec,
        "form": form,
        "response_form": response_form,
        "responses": responses,
        "scores": [(label_name(l), v) for l, v in rec.sorted_scores()],
        "other_labels": other_labels,
        "nav": "history",
    })


def _safe_redirect_after_response(request, pk):
    """Prefer an in-app next URL (e.g. incidents list); otherwise the result page."""
    nxt = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect("result", pk=pk)


@login_required
def incident_respond(request, pk):
    rec = get_object_or_404(Classification.objects.select_related("user"), pk=pk)
    if not _can_view_incident(request.user, rec):
        messages.error(request, "You can only respond to incidents you reported.")
        return redirect("history")
    if not rec.predicted_label:
        messages.error(request, "Uncertain predictions have no incident response until a category is assigned.")
        return _safe_redirect_after_response(request, pk)
    if request.method != "POST":
        return redirect("result", pk=pk)
    form = IncidentResponseForm(request.POST, user=request.user)
    if not form.is_valid():
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
        return _safe_redirect_after_response(request, pk)

    action = form.cleaned_data["action"]
    message = form.cleaned_data["message"].strip()
    if not message:
        message = IncidentResponse.DEFAULT_MESSAGES.get(action, "Status updated.")
    IncidentResponse.objects.create(
        incident=rec,
        author=request.user,
        action=action,
        message=message,
    )
    update_fields = []
    new_status = IncidentResponse.ACTION_TO_STATUS.get(action)
    if new_status and request.user.can_monitor_incidents:
        rec.response_status = new_status
        update_fields.append("response_status")
        if action in (
            IncidentResponse.Action.ACKNOWLEDGE,
            IncidentResponse.Action.RESPONDING,
        ):
            rec.assigned_officer = request.user
            update_fields.append("assigned_officer")
        elif action in (
            IncidentResponse.Action.CANCEL,
            IncidentResponse.Action.REOPEN,
        ):
            rec.assigned_officer = None
            update_fields.append("assigned_officer")
    if update_fields:
        rec.save(update_fields=update_fields)
    if action == IncidentResponse.Action.RESPONDING:
        messages.success(request, f"{rec.record_no} is now Responding.")
    elif action == IncidentResponse.Action.CANCEL:
        messages.success(request, f"{rec.record_no} is Pending again.")
    else:
        messages.success(request, f"Response posted on {rec.record_no}.")
    return _safe_redirect_after_response(request, pk)


def parse_filters(params):
    search = (params.get("search") or "").strip()
    predicted = params.get("predicted") if params.get("predicted") in LABELS else ""
    status = params.get("status") if params.get("status") in ("success", "failed") else ""
    response_status = params.get("response_status") or ""
    valid_response = {c[0] for c in Classification.RESPONSE_STATUS}
    if response_status not in valid_response:
        response_status = ""
    day = params.get("date") or ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        day = ""
    return {
        "search": search,
        "predicted": predicted,
        "status": status,
        "response_status": response_status,
        "date": day,
    }


def filtered_queryset(filters, user=None):
    qs = Classification.objects.select_related("model", "user", "assigned_officer")
    if user is not None and not user.can_monitor_incidents:
        qs = qs.filter(user=user)
    s = filters["search"]
    if s:
        digits = s.lstrip("#").lstrip("0") or ("0" if s.lstrip("#") else "")
        q = Q(filename__icontains=s) | Q(location_text__icontains=s) | Q(notes__icontains=s)
        if digits.isdigit():
            q |= Q(pk=int(digits))
        qs = qs.filter(q)
    if filters["predicted"]:
        qs = qs.filter(predicted_label=filters["predicted"])
    if filters["status"]:
        qs = qs.filter(status=filters["status"])
    if filters.get("response_status"):
        qs = qs.filter(response_status=filters["response_status"])
    if filters["date"]:
        try:
            day = date.fromisoformat(filters["date"])
            qs = qs.filter(created_at__date=day)
        except ValueError:
            pass
    return qs


def _incident_base_queryset(user):
    qs = Classification.objects.select_related("user", "assigned_officer", "model")
    if not user.can_monitor_incidents:
        qs = qs.filter(user=user)
    return qs


@login_required
def dashboard_page(request):
    """Simple monitoring overview of incident volume and response status."""
    qs = _incident_base_queryset(request.user)
    today = timezone.localdate()
    status_counts = {
        row["response_status"]: row["n"]
        for row in qs.values("response_status").annotate(n=Count("id"))
    }
    pending = status_counts.get("open", 0)
    acknowledged = status_counts.get("acknowledged", 0)
    responding = status_counts.get("responding", 0)
    resolved = status_counts.get("resolved", 0)
    closed = status_counts.get("closed", 0)
    completed = resolved + closed
    total = qs.count()
    today_count = qs.filter(created_at__date=today).count()
    with_gps = qs.exclude(latitude__isnull=True).exclude(longitude__isnull=True).count()
    with_barangay = qs.exclude(location_text="").count()
    uncertain = qs.filter(Q(predicted_label="") | Q(low_confidence=True), status="success").count()

    label_counts = {
        row["predicted_label"]: row["n"]
        for row in qs.exclude(predicted_label="").values("predicted_label").annotate(n=Count("id"))
    }
    max_label = max(label_counts.values(), default=0) or 1
    categories = [
        {
            "key": key,
            "name": LABEL_NAMES[key],
            "count": label_counts.get(key, 0),
            "pct": round(100 * label_counts.get(key, 0) / max_label),
        }
        for key in LABELS
    ]
    response_rows = [
        {
            "key": key,
            "name": name,
            "count": status_counts.get(key, 0),
            "pct": round(100 * status_counts.get(key, 0) / total) if total else 0,
        }
        for key, name in Classification.RESPONSE_STATUS
    ]

    barangay_counts = {
        row["location_text"]: row["n"]
        for row in qs.exclude(location_text="").values("location_text").annotate(n=Count("id"))
    }
    max_barangay = max(barangay_counts.values(), default=0) or 1
    # Prefer official Santa Maria order; append any free-text / legacy locations after.
    barangay_rows = []
    for name in SANTA_MARIA_BARANGAYS:
        count = barangay_counts.pop(name, 0)
        if count:
            barangay_rows.append({
                "name": name,
                "count": count,
                "pct": round(100 * count / max_barangay),
            })
    for name, count in sorted(barangay_counts.items(), key=lambda item: (-item[1], item[0])):
        barangay_rows.append({
            "name": name,
            "count": count,
            "pct": round(100 * count / max_barangay),
        })
    barangay_rows.sort(key=lambda row: (-row["count"], row["name"]))
    barangay_rows = barangay_rows[:10]
    if barangay_rows:
        top_max = barangay_rows[0]["count"] or 1
        for row in barangay_rows:
            row["pct"] = round(100 * row["count"] / top_max)

    attention = list(
        qs.exclude(predicted_label="")
        .filter(response_status__in=["open", "acknowledged", "responding"])
        .order_by("-created_at", "-id")[:8]
    )
    recent = list(qs.order_by("-created_at", "-id")[:8])

    return render(request, "classifier/dashboard.html", {
        "nav": "dashboard",
        "today": today,
        "counts": {
            "total": total,
            "pending": pending,
            "acknowledged": acknowledged,
            "responding": responding,
            "completed": completed,
            "today": today_count,
            "with_gps": with_gps,
            "with_barangay": with_barangay,
            "uncertain": uncertain,
        },
        "categories": categories,
        "response_rows": response_rows,
        "barangay_rows": barangay_rows,
        "attention": attention,
        "recent": recent,
        "can_monitor": request.user.can_monitor_incidents,
    })


@login_required
def history_page(request):
    filters = parse_filters(request.GET)
    page = Paginator(filtered_queryset(filters, user=request.user), PAGE_SIZE).get_page(request.GET.get("page"))
    query = "&".join(f"{k}={v}" for k, v in filters.items() if v)
    return render(request, "classifier/history.html", {
        "page": page,
        "filters": filters,
        "query": query,
        "labels": [(l, LABEL_NAMES[l]) for l in LABELS],
        "response_statuses": Classification.RESPONSE_STATUS,
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
        "verification", "actual_label", "status", "error", "demo", "selection_mode", "votes",
        "source", "notes", "location_text", "latitude", "longitude",
        "response_status", "assigned_officer", "reporter",
    ])
    for c in filtered_queryset(filters, user=request.user).iterator():
        w.writerow([
            c.pk, timezone.localtime(c.created_at).isoformat(), c.filename, c.width, c.height, c.size_kb,
            str(c.model) if c.model else "", c.predicted_label,
            "" if c.confidence is None else f"{c.confidence:.4f}",
            *[f"{float(c.scores.get(l, 0)):.4f}" if c.scores else "" for l in LABELS],
            c.low_confidence, c.inference_ms, c.reference_label,
            ("yes" if c.is_match else "no") if c.has_match else "", c.verification, c.actual_label,
            c.status, c.error, c.demo, c.selection_mode,
            "; ".join(f"{v['model']}={v['label']} ({v['confidence']:.3f})" for v in (c.votes or [])),
            c.source, c.notes, c.location_text, c.latitude, c.longitude,
            c.response_status,
            c.assigned_officer.email if c.assigned_officer_id else "",
            c.user.email if c.user_id else "",
        ])
    return response


@login_required
def incident_map_page(request):
    """Google Map of incidents that include GPS coordinates."""
    filters = parse_filters(request.GET)
    qs = filtered_queryset(filters, user=request.user)
    mapped = list(
        qs.exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
        .order_by("-created_at", "-id")[:500]
    )
    unmapped_count = qs.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True)).count()
    markers = []
    for c in mapped:
        when = timezone.localtime(c.created_at).strftime("%b %d, %Y · %I:%M %p")
        when = when.replace(" 0", " ")
        markers.append({
            "id": c.pk,
            "record": c.record_no,
            "lat": c.latitude,
            "lng": c.longitude,
            "label": c.predicted_label or "",
            "label_name": label_name(c.predicted_label) if c.predicted_label else "Uncertain",
            "color": MAP_MARKER_COLORS.get(c.predicted_label, "#64748b"),
            "status": c.response_status,
            "status_label": c.response_status_label,
            "location": c.location_text or "",
            "url": reverse("result", args=[c.pk]),
            "when": when,
        })

    agency_markers = [
        {
            "id": a.pk,
            "name": a.name,
            "lat": a.latitude,
            "lng": a.longitude,
            "type": a.agency_type,
            "type_label": a.agency_type_label,
            "phone": a.phone,
            "barangay": a.barangay,
            "address": a.address,
        }
        for a in NotifyAgency.objects.filter(
            is_active=True, latitude__isnull=False, longitude__isnull=False
        )
    ]

    query = "&".join(f"{k}={v}" for k, v in filters.items() if v)
    return render(request, "classifier/map.html", {
        "agency_markers": agency_markers,
        "filters": filters,
        "query": query,
        "labels": [(l, LABEL_NAMES[l]) for l in LABELS],
        "response_statuses": Classification.RESPONSE_STATUS,
        "markers": markers,
        "unmapped_count": unmapped_count,
        "mapped_count": len(markers),
        "map_center": MAP_DEFAULT_CENTER,
        "map_boundary": MAP_SANTA_MARIA_BOUNDARY,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        "nav": "map",
    })


def _agencies_queryset(search, agency_type, active_only=None):
    qs = NotifyAgency.objects.all()
    if agency_type:
        qs = qs.filter(agency_type=agency_type)
    if active_only is True:
        qs = qs.filter(is_active=True)
    elif active_only is False:
        qs = qs.filter(is_active=False)
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(contact_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(barangay__icontains=search)
            | Q(address__icontains=search)
            | Q(notes__icontains=search)
        )
    return qs


@manager_required
def agency_list(request):
    agency_type = request.GET.get("agency_type") or ""
    if agency_type not in {c.value for c in NotifyAgency.AgencyType}:
        agency_type = ""
    status = request.GET.get("status") or ""
    if status not in ("active", "inactive"):
        status = ""
    search = (request.GET.get("search") or "").strip()
    create_form = NotifyAgencyForm()
    create_open = request.GET.get("new") == "1"

    if request.method == "POST" and request.POST.get("intent") == "create":
        create_form = NotifyAgencyForm(request.POST)
        if create_form.is_valid():
            agency = create_form.save()
            messages.success(request, f"Added notify agency “{agency.name}”.")
            return redirect("agency_list")
        create_open = True

    active_only = None
    if status == "active":
        active_only = True
    elif status == "inactive":
        active_only = False

    page = Paginator(
        _agencies_queryset(search, agency_type, active_only=active_only),
        PAGE_SIZE,
    ).get_page(request.GET.get("page"))

    query_parts = []
    if search:
        query_parts.append(f"search={search}")
    if agency_type:
        query_parts.append(f"agency_type={agency_type}")
    if status:
        query_parts.append(f"status={status}")

    return render(request, "classifier/agencies.html", {
        "page": page,
        "search": search,
        "agency_type": agency_type,
        "status": status,
        "agency_types": NotifyAgency.AgencyType.choices,
        "query": "&".join(query_parts),
        "nav": "agencies",
        "create_form": create_form,
        "create_open": create_open,
        "map_center": MAP_DEFAULT_CENTER,
        "map_boundary": MAP_SANTA_MARIA_BOUNDARY,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        "counts": {
            "all": NotifyAgency.objects.count(),
            "active": NotifyAgency.objects.filter(is_active=True).count(),
            "inactive": NotifyAgency.objects.filter(is_active=False).count(),
        },
    })


@manager_required
def agency_create(request):
    """Old /agencies/new/ address — open the dialog on the Agencies page instead."""
    return redirect("/agencies/?new=1")


@manager_required
def agency_edit(request, pk):
    agency = get_object_or_404(NotifyAgency, pk=pk)
    form = NotifyAgencyForm(request.POST or None, instance=agency)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated “{agency.name}”.")
        return redirect("agency_list")
    return render(request, "classifier/agency_form.html", {
        "form": form,
        "agency": agency,
        "title": f"Edit {agency.name}",
        "subtitle": "Update contact details, station location, or deactivate this notify agency.",
        "nav": "agencies",
        "map_center": MAP_DEFAULT_CENTER,
        "map_boundary": MAP_SANTA_MARIA_BOUNDARY,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    })
