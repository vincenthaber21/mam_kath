"""Shared transfer-learning training used by manage.py train_models and the Models page."""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
from django.core.files import File

from classifier.labels import LABELS
from registry.models import MLModel

ARCHS = {
    "efficientnet": ("EfficientNet-B0", "EfficientNetB0", "efficientnet"),
    "mobilenet_v2": ("MobileNetV2", "MobileNetV2", "mobilenet_v2"),
    "resnet50": ("ResNet50", "ResNet50", "resnet50"),
}

ALL_ARCHS = tuple(ARCHS.keys())


def train_candidates(
    path,
    archs,
    *,
    epochs=10,
    fine_tune_epochs=10,
    fine_tune_layers=20,
    batch_size=32,
    input_size=224,
    model_version="1.0",
    out="trained_models",
    activate=True,
    quiet=False,
    write=None,
    on_progress=None,
):
    """Train one or more architectures and register them. Returns the list of MLModel rows."""
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError("TensorFlow is not installed. Run: pip install tensorflow-cpu") from exc
    from sklearn.metrics import classification_report, confusion_matrix, f1_score

    say = write or (lambda *_a, **_k: None)
    progress = on_progress or (lambda **_k: None)

    root = Path(path)
    for split in ("train", "val"):
        if not (root / split).is_dir():
            raise FileNotFoundError(f"Missing folder: {root / split}")

    keys = [a.strip() for a in archs if str(a).strip()]
    bad = [a for a in keys if a not in ARCHS]
    if bad:
        raise ValueError(f"Unknown architecture(s): {', '.join(bad)}")
    if not keys:
        raise ValueError("Select at least one architecture.")

    size, bs = input_size, batch_size
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    fit_verbose = 2 if quiet else 1

    def load(split, shuffle):
        if not (root / split).is_dir():
            return None
        return tf.keras.utils.image_dataset_from_directory(
            root / split, labels="inferred", label_mode="int", class_names=LABELS,
            image_size=(size, size), batch_size=bs, shuffle=shuffle, seed=42,
        )

    say(f"\nSTEP 1  Load the dataset")
    say(f"  Folder: {root.resolve()}")
    say(f"  {'class':18} {'train':>6} {'val':>6} {'test':>6}")
    for lb in LABELS:
        n = [
            sum(1 for p in (root / s / lb).glob("*") if p.is_file()) if (root / s / lb).is_dir() else 0
            for s in ("train", "val", "test")
        ]
        say(f"  {lb:18} {n[0]:6} {n[1]:6} {n[2]:6}")
    say(f"  Every image is resized to {size}x{size} px; batches of {bs}.")

    raw = {s: load(s, s == "train") for s in ("train", "val", "test")}
    counts = np.array(
        [sum(1 for p in (root / "train" / lb).glob("*") if p.is_file()) for lb in LABELS], float
    )
    class_weight = {i: float(counts.sum() / (len(LABELS) * c)) for i, c in enumerate(counts) if c}
    say(
        "  Class weights (smaller classes count more): "
        + ", ".join(f"{LABELS[i]} {w:.2f}" for i, w in class_weight.items())
    )
    say("  Augmentation on TRAINING images only: random flip, rotation, zoom, contrast.")
    augment = tf.keras.Sequential([
        tf.keras.layers.RandomFlip("horizontal"),
        tf.keras.layers.RandomRotation(0.05),
        tf.keras.layers.RandomZoom(0.1),
        tf.keras.layers.RandomContrast(0.1),
    ])

    trained = []
    for n_arch, key in enumerate(keys, 1):
        display, app_name, pre = ARCHS[key]
        progress(
            processed=n_arch - 1,
            total=len(keys),
            current_arch=key,
            message=f"Training {display} ({n_arch}/{len(keys)})",
        )
        say(f"\n{'=' * 60}\nMODEL {n_arch}/{len(keys)}: {display}\n{'=' * 60}")
        t_model = time.perf_counter()
        preprocess = getattr(tf.keras.applications, pre).preprocess_input

        train = raw["train"].map(
            lambda x, y: (preprocess(augment(x, training=True)), y)
        ).prefetch(tf.data.AUTOTUNE)
        val = raw["val"].map(lambda x, y: (preprocess(x), y)).cache().prefetch(tf.data.AUTOTUNE)
        test = (
            raw["test"].map(lambda x, y: (preprocess(x), y)).prefetch(tf.data.AUTOTUNE)
            if raw["test"] else None
        )

        base = getattr(tf.keras.applications, app_name)(
            include_top=False, weights="imagenet", input_shape=(size, size, 3)
        )
        base.trainable = False
        inputs = tf.keras.Input((size, size, 3))
        x = base(inputs, training=False)
        x = tf.keras.layers.GlobalAveragePooling2D()(x)
        x = tf.keras.layers.Dropout(0.3)(x)
        outputs = tf.keras.layers.Dense(len(LABELS), activation="softmax")(x)
        model = tf.keras.Model(inputs, outputs, name=key)

        def n_params(trainable):
            ws = model.trainable_weights if trainable else model.non_trainable_weights
            return sum(int(np.prod(w.shape)) for w in ws)

        say("\nSTEP 2  Build the transfer-learning model")
        say(f"  Backbone: {display} pre-trained on ImageNet ({len(base.layers)} layers) -> FROZEN")
        say(f"  New head: GlobalAveragePooling -> Dropout 0.3 -> Dense(5, softmax) for {', '.join(LABELS)}")
        say(f"  Trainable parameters: {n_params(True):,}   frozen: {n_params(False):,}")

        def fit(lr, n_epochs, initial_epoch=0, phase=""):
            model.compile(
                optimizer=tf.keras.optimizers.Adam(lr),
                loss="sparse_categorical_crossentropy",
                metrics=["accuracy"],
            )

            class ProgressCallback(tf.keras.callbacks.Callback):
                def on_epoch_begin(self, epoch, logs=None):
                    progress(
                        processed=n_arch - 1,
                        total=len(keys),
                        current_arch=key,
                        message=f"{display}: {phase} epoch {epoch + 1}",
                    )

            return model.fit(
                train,
                validation_data=val,
                epochs=initial_epoch + n_epochs,
                initial_epoch=initial_epoch,
                verbose=fit_verbose,
                class_weight=class_weight,
                callbacks=[
                    tf.keras.callbacks.EarlyStopping(
                        monitor="val_loss", patience=4, restore_best_weights=True
                    ),
                    ProgressCallback(),
                ],
            )

        hist = []
        say(f"\nSTEP 3  Phase 1: train only the new head ({epochs} epochs max, learning rate 0.001)")
        say("  accuracy/loss = training images, val_accuracy/val_loss = validation images.")
        say("  Stops early if val_loss does not improve for 4 epochs.")
        h1 = fit(1e-3, epochs, phase="phase 1")
        hist.append(h1.history)
        if fine_tune_epochs > 0:
            base.trainable = True
            for layer in base.layers[:-fine_tune_layers]:
                layer.trainable = False
            for layer in base.layers:
                if isinstance(layer, tf.keras.layers.BatchNormalization):
                    layer.trainable = False
            say(
                f"\nSTEP 4  Phase 2: fine-tune the top {fine_tune_layers} backbone layers "
                f"({fine_tune_epochs} epochs max, learning rate 0.00001)"
            )
            say(f"  Trainable parameters now: {n_params(True):,}")
            h2 = fit(1e-5, fine_tune_epochs, initial_epoch=len(h1.history["loss"]), phase="phase 2")
            hist.append(h2.history)

        history, epoch = [], 0
        for h in hist:
            for i in range(len(h["loss"])):
                epoch += 1
                history.append({
                    "epoch": epoch,
                    "train_acc": round(float(h["accuracy"][i]), 4),
                    "val_acc": round(float(h["val_accuracy"][i]), 4),
                    "train_loss": round(float(h["loss"][i]), 4),
                    "val_loss": round(float(h["val_loss"][i]), 4),
                })

        def scores(ds, name):
            y_true = np.concatenate([y.numpy() for _, y in ds])
            y_pred = np.argmax(model.predict(ds, verbose=0), axis=1)
            acc = float(np.mean(y_true == y_pred))
            f1 = float(f1_score(
                y_true, y_pred, labels=list(range(len(LABELS))), average="macro", zero_division=0
            ))
            say(f"\n  {name} set: accuracy {acc:.3f}, macro F1 {f1:.3f}")
            say(classification_report(
                y_true, y_pred, labels=list(range(len(LABELS))), target_names=LABELS,
                digits=3, zero_division=0,
            ))
            cm = confusion_matrix(y_true, y_pred, labels=list(range(len(LABELS))))
            say("  Confusion matrix (rows = true, columns = predicted):")
            say("  " + " " * 18 + "".join(f"{lb[:8]:>9}" for lb in LABELS))
            for lb, row in zip(LABELS, cm):
                say(f"  {lb:18}" + "".join(f"{v:9}" for v in row))
            return acc, f1

        say("\nSTEP 5  Evaluate")
        progress(
            processed=n_arch - 1,
            total=len(keys),
            current_arch=key,
            message=f"{display}: evaluating",
        )
        val_acc, val_f1 = scores(val, "Validation")
        test_acc = scores(test, "Held-out TEST")[0] if test is not None else None

        sample = next(iter(val))[0][:1]
        model(sample, training=False)
        times = []
        for _ in range(20):
            t0 = time.perf_counter()
            model(sample, training=False)
            times.append((time.perf_counter() - t0) * 1000)

        say("\nSTEP 6  Save and register on the Models page")
        path_out = out_dir / f"{key}_v{model_version}.keras"
        model.save(path_out)
        say(f"  Saved {path_out}  (training took {(time.perf_counter() - t_model) / 60:.1f} min)")
        m = MLModel(
            name=display,
            version=model_version,
            preprocessing=key,
            input_size=size,
            labels_json=LABELS,
            val_accuracy=round(val_acc, 4),
            val_macro_f1=round(val_f1, 4),
            test_accuracy=round(test_acc, 4) if test_acc is not None else None,
            size_mb=round(path_out.stat().st_size / 1024 / 1024, 1),
            avg_inference_ms=round(float(np.mean(times)), 1),
            history=history,
            notes=(
                f"ImageNet weights; head {epochs} ep, fine-tuned top {fine_tune_layers} layers "
                f"{fine_tune_epochs} ep; trained with manage.py train_models."
            ),
        )
        with path_out.open("rb") as fh:
            m.file.save(path_out.name, File(fh), save=False)
        if activate and not MLModel.objects.filter(is_active=True).exists():
            m.is_active = True
        m.save()
        trained.append(m)
        test_txt = f"{test_acc:.3f}" if test_acc is not None else "n/a"
        say(
            f"{display}: val acc {val_acc:.3f}, val macro F1 {val_f1:.3f}, test acc {test_txt}, "
            f"{m.size_mb} MB, {m.avg_inference_ms} ms -> registered (id {m.id})"
        )
        progress(
            processed=n_arch,
            total=len(keys),
            current_arch=key,
            message=f"Finished {display}",
            model_ids=[x.id for x in trained],
        )
        tf.keras.backend.clear_session()

    if trained and activate:
        best = max(trained, key=lambda m: m.val_macro_f1 or 0)
        best.is_active = True
        best.save()
        say(f"\nActive model: {best} (best validation macro F1).")

    return trained
