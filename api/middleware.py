"""Minimal CORS for the mobile / Expo client.

Allow origins listed in CORS_ALLOWED_ORIGINS, or any origin when CORS_ALLOW_ALL
is True (default in DEBUG). Native apps do not send an Origin header; browsers
and Expo web do.
"""


class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.http import HttpResponse

        # Always answer preflight for /api/ (Expo web / browsers).
        if request.method == "OPTIONS" and (
            request.path.startswith("/api/")
            or request.headers.get("Access-Control-Request-Method")
        ):
            response = HttpResponse(status=204)
            self._apply(request, response, settings)
            return response

        response = self.get_response(request)
        self._apply(request, response, settings)
        return response

    def _apply(self, request, response, settings):
        origin = request.headers.get("Origin")
        allow_all = getattr(settings, "CORS_ALLOW_ALL", False)
        allowed = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        if allow_all:
            response["Access-Control-Allow-Origin"] = origin or "*"
        elif origin and origin in allowed:
            response["Access-Control-Allow-Origin"] = origin
        elif request.path.startswith("/api/"):
            # Native Expo Go often sends no Origin; still advertise open API CORS.
            response["Access-Control-Allow-Origin"] = "*"
        else:
            return
        response["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, Accept, X-Requested-With, X-EIC-Token, X-Tunnel-Authorization"
        )
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Max-Age"] = "86400"
        if response.get("Access-Control-Allow-Origin") not in (None, "*"):
            response["Vary"] = "Origin"
