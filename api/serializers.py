from django.conf import settings
from django.utils import timezone

from classifier.labels import LABEL_NAMES, label_name


def absolute_media_url(request, file_field):
    if not file_field:
        return None
    url = file_field.url
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def user_payload(user):
    return {
        "id": user.pk,
        "email": user.email,
        "name": user.display_name,
    }


def classification_payload(rec, request=None, detail=False):
    data = {
        "id": rec.pk,
        "record_no": rec.record_no,
        "status": rec.status,
        "error": rec.error or "",
        "filename": rec.filename,
        "predicted_label": rec.predicted_label or "",
        "predicted_label_name": label_name(rec.predicted_label) if rec.predicted_label else "",
        "confidence": rec.confidence,
        "low_confidence": rec.low_confidence,
        "inference_ms": rec.inference_ms,
        "selection_mode": rec.selection_mode or "",
        "demo": rec.demo,
        "notes": rec.notes or "",
        "location_text": rec.location_text or "",
        "latitude": rec.latitude,
        "longitude": rec.longitude,
        "source": rec.source or "web",
        "verification": rec.verification or "",
        "actual_label": rec.actual_label or "",
        "reference_label": rec.reference_label or "",
        "image_url": absolute_media_url(request, rec.image),
        "created_at": timezone.localtime(rec.created_at).isoformat() if rec.created_at else None,
        "model": None,
    }
    if rec.model_id:
        data["model"] = {
            "id": rec.model_id,
            "name": rec.model.name,
            "version": rec.model.version,
        }
    if detail:
        data["scores"] = {label: float(rec.scores.get(label, 0)) for label in LABEL_NAMES}
        data["scores_sorted"] = [
            {"label": label, "name": LABEL_NAMES[label], "score": score}
            for label, score in rec.sorted_scores()
        ]
        data["votes"] = rec.votes or []
        data["width"] = rec.width
        data["height"] = rec.height
        data["size_kb"] = rec.size_kb
    return data
