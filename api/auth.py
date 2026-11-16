from functools import wraps

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import AuthToken


def parse_bearer(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() not in {"bearer", "token"}:
        return None
    return parts[1].strip() or None


def resolve_token(request):
    key = parse_bearer(request)
    if not key:
        return None
    try:
        token = AuthToken.objects.select_related("user").get(key=key)
    except AuthToken.DoesNotExist:
        return None
    if not token.user.is_active:
        return None
    AuthToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
    return token


def api_login_required(view):
    """Require Authorization: Bearer <token>. CSRF is not used for token auth."""

    @wraps(view)
    @csrf_exempt
    def wrapper(request, *args, **kwargs):
        token = resolve_token(request)
        if token is None:
            return JsonResponse({"error": "Authentication required."}, status=401)
        request.api_token = token
        request.user = token.user
        return view(request, *args, **kwargs)

    return wrapper


def api_login_optional(view):
    """Attach Bearer user when present; otherwise leave request.user anonymous."""

    @wraps(view)
    @csrf_exempt
    def wrapper(request, *args, **kwargs):
        token = resolve_token(request)
        if token is not None:
            request.api_token = token
            request.user = token.user
        else:
            request.api_token = None
        return view(request, *args, **kwargs)

    return wrapper
