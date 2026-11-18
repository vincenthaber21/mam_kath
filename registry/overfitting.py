"""Overfitting check for registered models.

A model overfits when it memorises the training images instead of learning patterns that carry over to
new images. Three signals are checked, each only when the numbers exist:

1. Train vs validation gap — accuracy on the (un-augmented) training images minus validation accuracy.
   Uses ``MLModel.train_accuracy`` when training measured it, otherwise the training curve at the epoch
   with the lowest validation loss (the weights EarlyStopping keeps).
2. Validation vs test gap — validation accuracy was used to pick the epoch and the best model, so a
   model that only looks good on validation shows a drop on the untouched test set.
3. Loss divergence — validation loss climbing back up while training loss keeps falling.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Accuracy gaps (0-1 scale). 0.03 = 3 percentage points.
GAP_WATCH = 0.03
GAP_OVERFIT = 0.06
# Validation loss ending this much above its best value while training loss still falls.
LOSS_RISE_WATCH = 0.10

STATUS_LABELS = {
    "ok": "Good fit",
    "watch": "Watch",
    "overfit": "Overfitting",
    "unknown": "Not enough data",
}


@dataclass
class FitReport:
    status: str = "unknown"
    train_val_gap: float | None = None
    train_val_source: str = ""
    val_test_gap: float | None = None
    loss_rise: float | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def label(self):
        return STATUS_LABELS[self.status]

    @property
    def is_overfit(self):
        return self.status == "overfit"

    @property
    def summary(self):
        return " ".join(self.reasons) if self.reasons else "No overfitting signals found."

    def as_dict(self):
        return {
            "status": self.status,
            "label": self.label,
            "train_val_gap": self.train_val_gap,
            "train_val_source": self.train_val_source,
            "val_test_gap": self.val_test_gap,
            "loss_rise": self.loss_rise,
            "reasons": list(self.reasons),
        }


def _level(gap):
    if gap is None:
        return None
    if gap >= GAP_OVERFIT:
        return "overfit"
    if gap >= GAP_WATCH:
        return "watch"
    return "ok"


def _best_epoch(history):
    """The epoch with the lowest validation loss (what EarlyStopping restores), or None."""
    rows = [r for r in history or [] if isinstance(r, dict) and r.get("val_loss") is not None]
    if not rows:
        return None, rows
    return min(rows, key=lambda r: r["val_loss"]), rows


def assess(train_accuracy=None, val_accuracy=None, test_accuracy=None, history=None) -> FitReport:
    report = FitReport()
    levels = []
    best, rows = _best_epoch(history)

    # 1. train vs validation
    if train_accuracy is not None and val_accuracy is not None:
        report.train_val_gap = round(train_accuracy - val_accuracy, 4)
        report.train_val_source = "training set"
    elif best and best.get("train_acc") is not None and best.get("val_acc") is not None:
        report.train_val_gap = round(best["train_acc"] - best["val_acc"], 4)
        report.train_val_source = f"training curve, epoch {best.get('epoch', '?')}"
    lvl = _level(report.train_val_gap)
    if lvl:
        levels.append(lvl)
        if lvl != "ok":
            report.reasons.append(
                f"Training accuracy is {report.train_val_gap * 100:.1f} points above validation "
                f"({report.train_val_source})."
            )

    # 2. validation vs test
    if val_accuracy is not None and test_accuracy is not None:
        report.val_test_gap = round(val_accuracy - test_accuracy, 4)
        lvl = _level(report.val_test_gap)
        levels.append(lvl)
        if lvl != "ok":
            report.reasons.append(
                f"Test accuracy is {report.val_test_gap * 100:.1f} points below validation, so the "
                "model does worse on images it was never tuned on."
            )

    # 3. loss divergence after the best epoch
    if best and len(rows) >= 3:
        last = rows[-1]
        if last is not best and best["val_loss"] > 0:
            rise = (last["val_loss"] - best["val_loss"]) / best["val_loss"]
            train_fell = (
                last.get("train_loss") is not None
                and best.get("train_loss") is not None
                and last["train_loss"] < best["train_loss"]
            )
            report.loss_rise = round(rise, 4)
            if rise >= LOSS_RISE_WATCH and train_fell:
                levels.append("watch")
                report.reasons.append(
                    f"Validation loss rose {rise * 100:.0f}% after epoch {best.get('epoch', '?')} while "
                    "training loss kept falling."
                )
            else:
                levels.append("ok")

    if not levels:
        report.status = "unknown"
    elif "overfit" in levels:
        report.status = "overfit"
    elif "watch" in levels:
        report.status = "watch"
    else:
        report.status = "ok"
    return report


def assess_model(m) -> FitReport:
    return assess(
        train_accuracy=getattr(m, "train_accuracy", None),
        val_accuracy=m.val_accuracy,
        test_accuracy=m.test_accuracy,
        history=m.history,
    )
