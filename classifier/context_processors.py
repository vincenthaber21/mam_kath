from django.conf import settings


def site(request):
    from registry.models import MLModel

    demo = False
    if settings.EIC_DEMO_MODE and getattr(request, "user", None) and request.user.is_authenticated:
        active = MLModel.objects.filter(is_active=True).only("file").first()
        demo = active is None or not active.file
    return {
        "DEMO_PREDICTIONS": demo,
        "LOW_CONFIDENCE_PCT": round(settings.LOW_CONFIDENCE_THRESHOLD * 100),
    }
