import json
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from classifier.forms import VerificationForm
from classifier.labels import LABEL_NAMES, LABELS
from classifier.models import Classification
from classifier.services import active_model, classify_upload, models_in_use, preload_active_model, selection_mode
from classifier.views import filtered_queryset, parse_filters

from .auth import api_login_optional, api_login_required
from .models import AuthToken
from .serializers import classification_payload, user_payload

logger = logging.getLogger(__name__)
PAGE_SIZE = 20


def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _parse_optional_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@csrf_exempt
@require_GET
def health(request):
    """Unauthenticated ping so the mobile app can verify the tunnel / API is reachable."""
    return JsonResponse({
        "ok": True,
        "service": "eic-api",
        "tunnel_hint": "Use this host in the Expo app API URL.",
    })


@csrf_exempt
@require_POST
def login(request):
    """POST {email, password, device_label?} → {token, user}"""
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Send JSON with email and password."}, status=400)
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return JsonResponse({"error": "Email and password are required."}, status=400)
    user = authenticate(request, username=email, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid email or password."}, status=401)
    token = AuthToken.objects.create(
        user=user,
        label=(body.get("device_label") or "")[:80],
    )
    return JsonResponse({"token": token.key, "user": user_payload(user)})


@api_login_required
@require_POST
def logout(request):
    request.api_token.delete()
    return JsonResponse({"ok": True})


@api_login_required
@require_GET
def me(request):
    return JsonResponse({"user": user_payload(request.user)})


@api_login_required
@require_GET
def meta(request):
    preload_active_model()
    in_use = models_in_use()
    active = active_model(sync=False)
    return JsonResponse({
        "labels": [{"value": l, "name": LABEL_NAMES[l]} for l in LABELS],
        "selection_mode": selection_mode(),
        "low_confidence_threshold": settings.LOW_CONFIDENCE_THRESHOLD,
        "max_image_mb": settings.MAX_IMAGE_MB,
        "active_model": (
            {"id": active.pk, "name": active.name, "version": active.version}
            if active else None
        ),
        "models_in_use": [
            {"id": m.pk, "name": m.name, "version": m.version, "val_accuracy": m.val_accuracy}
            for m in in_use if m is not None
        ],
        "demo_mode": settings.EIC_DEMO_MODE,
    })


@api_login_optional
@require_POST
def classify(request):
    """Multipart: image (required), optional notes, location_text, latitude, longitude, reference_label.

    Auth is optional so the mobile app can report incidents quickly as a guest.
    """
    upload = request.FILES.get("image")
    if upload is None:
        return JsonResponse({"error": "Choose or capture an image first."}, status=400)

    reference = (request.POST.get("reference_label") or "").strip()
    notes = (request.POST.get("notes") or "").strip()[:2000]
    location_text = (request.POST.get("location_text") or "").strip()[:255]
    latitude = _parse_optional_float(request.POST.get("latitude"))
    longitude = _parse_optional_float(request.POST.get("longitude"))

    rec = classify_upload(
        upload,
        reference,
        request.user,
        notes=notes,
        location_text=location_text,
        latitude=latitude,
        longitude=longitude,
        source="mobile",
    )
    # Always 201: failed attempts are still logged (same as the website flow).
    return JsonResponse(classification_payload(rec, request, detail=True), status=201)


@api_login_required
@require_GET
def classification_detail(request, pk):
    rec = get_object_or_404(Classification.objects.select_related("model"), pk=pk)
    return JsonResponse(classification_payload(rec, request, detail=True))


@api_login_required
@require_http_methods(["POST", "PUT", "PATCH"])
def classification_verify(request, pk):
    rec = get_object_or_404(Classification.objects.select_related("model"), pk=pk)
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Send JSON with verification and optional actual_label."}, status=400)
    form = VerificationForm(body, record=rec)
    if not form.is_valid():
        return JsonResponse({"error": "Invalid verification.", "fields": form.errors}, status=400)
    rec.verification = form.cleaned_data["verification"]
    rec.actual_label = form.cleaned_data["actual_label"] or ""
    rec.save(update_fields=["verification", "actual_label"])
    return JsonResponse(classification_payload(rec, request, detail=True))


@api_login_required
@require_GET
def classification_list(request):
    filters = parse_filters(request.GET)
    qs = filtered_queryset(filters)
    # Mobile reporters typically want their own reports first; staff see everything.
    if not request.user.is_staff:
        qs = qs.filter(user=request.user)
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    return JsonResponse({
        "count": page.paginator.count,
        "page": page.number,
        "num_pages": page.paginator.num_pages,
        "results": [classification_payload(rec, request) for rec in page.object_list],
    })
