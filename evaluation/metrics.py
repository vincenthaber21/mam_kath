"""Accuracy, per-class / macro / weighted precision-recall-F1 and confusion matrix (scikit-learn)."""
import statistics

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from classifier.labels import LABELS


def _r(x):
    return round(float(x), 4)


def compute(y_true, y_pred, labels=LABELS):
    if not y_true:
        zero = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        return {
            "accuracy": 0.0,
            "per_class": [{"label": l, **zero, "support": 0} for l in labels],
            "macro": dict(zero),
            "weighted": dict(zero),
            "labels": list(labels),
            "confusion_matrix": [[0] * len(labels) for _ in labels],
        }
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    mp, mr, mf, _ = precision_recall_fscore_support(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    wp, wr, wf, _ = precision_recall_fscore_support(y_true, y_pred, labels=labels, average="weighted", zero_division=0)
    return {
        "accuracy": _r(accuracy_score(y_true, y_pred)),
        "per_class": [
            {"label": l, "precision": _r(p[i]), "recall": _r(r[i]), "f1": _r(f[i]), "support": int(s[i])}
            for i, l in enumerate(labels)
        ],
        "macro": {"precision": _r(mp), "recall": _r(mr), "f1": _r(mf)},
        "weighted": {"precision": _r(wp), "recall": _r(wr), "f1": _r(wf)},
        "labels": list(labels),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def timing(values):
    if not values:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": round(statistics.fmean(values), 1),
        "median": round(statistics.median(values), 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
    }
