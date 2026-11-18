import json
import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.models import normalize_person_name, normalize_username
from classifier.forms import VerificationForm
from classifier.labels import LABEL_NAMES, LABELS
from classifier.locations import SANTA_MARIA_BARANGAY_SET, normalize_barangay
from classifier.models import Classification
from classifier.services import active_model, classify_upload, models_in_use, preload_active_model, selection_mode
from classifier.views import filtered_queryset, parse_filters

from .auth import api_login_optional, api_login_required
from .models import AuthToken
from .serializers import classification_payload, user_payload

User = get_user_model()

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
def index(request):
    """GET /api/ — confirms the API base URL (avoids a confusing 404 in the browser)."""
    return JsonResponse({
        "ok": True,
        "service": "eic-api",
        "health": "/api/health/",
        "hint": "Mobile app API base should end with /api (e.g. https://….devtunnels.ms/api).",
    })


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
    """POST {username|email, password, device_label?} → {token, user}"""
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Send JSON with username/email and password."}, status=400)
    # Prefer username when both are sent; keep email for older mobile builds.
    identifier = (body.get("username") or body.get("email") or "").strip()
    password = body.get("password") or ""
    if not identifier or not password:
        return JsonResponse({"error": "Username/email and password are required."}, status=400)
    if "@" in identifier:
        identifier = identifier.lower()
    user = authenticate(request, username=identifier, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid username/email or password."}, status=401)
    token = AuthToken.objects.create(
        user=user,
        label=(body.get("device_label") or "")[:80],
    )
    return JsonResponse({"token": token.key, "user": user_payload(user)})


def _field_error(fields, key, message):
    fields.setdefault(key, []).append(message)


@csrf_exempt
@require_POST
def register(request):
    """POST resident self-signup for Santa Maria residents → {token, user}.

    Always creates role=resident. Officers/admins must be created by staff.
    """
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Send JSON with your account details."}, status=400)

    fields = {}
    username = normalize_username(body.get("username") or "")
    email = (body.get("email") or "").strip().lower()
    first_name = normalize_person_name(body.get("first_name") or "")
    middle_name = normalize_person_name(body.get("middle_name") or "")
    last_name = normalize_person_name(body.get("last_name") or "")
    phone = (body.get("phone") or "").strip()[:40]
    barangay = normalize_barangay(body.get("barangay") or "")
    password = body.get("password") or ""
    password_confirm = body.get("password_confirm") or body.get("password2") or ""

    if not username:
        _field_error(fields, "username", "Enter a username.")
    elif len(username) < 3:
        _field_error(fields, "username", "Username must be at least 3 characters.")
    elif User.objects.filter(username__iexact=username).exists():
        _field_error(fields, "username", "That username is already taken.")

    if not email:
        _field_error(fields, "email", "Enter your email address.")
    else:
        try:
            validate_email(email)
        except ValidationError:
            _field_error(fields, "email", "Enter a valid email address.")
        else:
            if User.objects.filter(email__iexact=email).exists():
                _field_error(fields, "email", "An account with that email already exists.")

    if not first_name:
        _field_error(fields, "first_name", "Enter your first name.")
    if not last_name:
        _field_error(fields, "last_name", "Enter your last name.")

    if not barangay:
        _field_error(fields, "barangay", "Select your barangay in Santa Maria.")
    elif barangay not in SANTA_MARIA_BARANGAY_SET:
        _field_error(fields, "barangay", "Choose a barangay in Santa Maria, Ilocos Sur.")

    if not password:
        _field_error(fields, "password", "Enter a password.")
    elif password != password_confirm:
        _field_error(fields, "password_confirm", "The two password fields did not match.")
    else:
        try:
            password_validation.validate_password(password)
        except ValidationError as exc:
            for msg in exc.messages:
                _field_error(fields, "password", str(msg))

    if fields:
        first = next(iter(fields.values()))[0]
        return JsonResponse(
            {"error": first, "fields": fields},
            status=400,
        )

    try:
        user = User.objects.create_user(
            email=email,
            password=password,
            username=username,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            phone=phone,
            barangay=barangay,
            role=User.Role.RESIDENT,
        )
    except IntegrityError:
        return JsonResponse(
            {"error": "That username or email is already registered."},
            status=400,
        )

    token = AuthToken.objects.create(
        user=user,
        label=(body.get("device_label") or "mobile")[:80],
    )
    return JsonResponse(
        {"token": token.key, "user": user_payload(user)},
        status=201,
    )


@api_login_required
@require_POST
def logout(request):
    request.api_token.delete()
    return JsonResponse({"ok": True})


@api_login_required
@require_GET
def me(request):
    return JsonResponse({"user": user_payload(request.user)})


@api_login_optional
@require_GET
def meta(request):
    """Public model/label metadata so the mobile app can boot without signing in."""
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
    location_text = normalize_barangay(request.POST.get("location_text") or "")[:255]
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
