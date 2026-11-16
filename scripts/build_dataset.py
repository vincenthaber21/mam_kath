"""Build the 5-class dataset (dataset/train|val|test/<label>/) from the downloaded Kaggle sources in raw_data/.

    python scripts/build_dataset.py            # defaults: raw_data -> dataset, cap 1000 per class, 70/15/15

Cleaning (paper, Data preparation): unreadable images are dropped, exact duplicates (same pixels)
are removed across all sources, large classes are capped so one class does not dominate, and every image
lands in exactly one split. A manifest.csv records the source of every image.
"""
import argparse
import csv
import hashlib
import random
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image

EXT = {".jpg", ".jpeg", ".png"}

# label -> list of (kaggle dataset, folder inside raw_data, filename filter)
SOURCES = {
    "fire": [("phylake1337/fire-dataset", "fire-dataset/fire_dataset/fire_images", None)],
    "crime": [("abdulmananraja/real-life-violence-situations", "real-life-violence-situations/new_violence/violence", None)],
    "medical_emergency": [
        ("simuletic/cctv-incident-dataset-fall-and-lying-down-detection",
         "cctv-incident-dataset-fall-and-lying-down-detection/laying_dataset/images", None),
        ("uttejkumarkandagatla/fall-detection-dataset", "fall-detection-dataset/fall_dataset/images",
         lambda p: p.name.lower().startswith("fall")),  # "fall*" = fallen person, skip "not fallen*"
    ],
    "accident": [
        ("ckay16/accident-detection-from-cctv-footage", f"accident-detection-from-cctv-footage/data/{s}/Accident", None)
        for s in ("train", "val", "test")
    ],
    "disaster": [
        ("aswin1871/cyclonewildfireflood-and-earthquake",
         f"cyclonewildfireflood-and-earthquake/Cyclone_Wildfire_Flood_Earthquake_Database/{c}", None)
        for c in ("Cyclone", "Earthquake", "Flood")  # Wildfire left out: it overlaps with "fire"
    ],
}


def pixel_hash(path):
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        im = im.convert("RGB")
        return hashlib.md5(im.tobytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="raw_data")
    ap.add_argument("--out", default="dataset")
    ap.add_argument("--cap", type=int, default=1000, help="Max images per class (0 = no cap)")
    ap.add_argument("--split", default="0.70,0.15,0.15")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    raw, out = Path(a.raw), Path(a.out)
    fr = [float(x) for x in a.split.split(",")]
    rng = random.Random(a.seed)
    if out.exists():
        shutil.rmtree(out)

    seen, removed, manifest = set(), defaultdict(int), []
    for label, sources in SOURCES.items():
        items = []
        for ref, folder, keep in sources:
            d = raw / folder
            if not d.is_dir():
                raise SystemExit(f"Missing {d} (download {ref} first)")
            files = sorted(p for p in d.rglob("*") if p.suffix.lower() in EXT and (keep is None or keep(p)))
            for p in files:
                try:
                    h = pixel_hash(p)
                except Exception:
                    removed["corrupt"] += 1
                    continue
                if h in seen:
                    removed["duplicate"] += 1
                    continue
                seen.add(h)
                items.append((ref, p))
        rng.shuffle(items)
        if a.cap and len(items) > a.cap:
            removed["over_cap"] += len(items) - a.cap
            items = items[: a.cap]
        n = len(items)
        n_train, n_val = round(n * fr[0]), round(n * fr[1])
        splits = {"train": items[:n_train], "val": items[n_train:n_train + n_val], "test": items[n_train + n_val:]}
        for split, rows in splits.items():
            dst_dir = out / split / label
            dst_dir.mkdir(parents=True, exist_ok=True)
            for i, (ref, p) in enumerate(rows):
                dst = dst_dir / f"{label}_{i:05d}{p.suffix.lower()}"
                shutil.copy2(p, dst)
                manifest.append([dst.relative_to(out).as_posix(), label, split, ref, p.relative_to(raw).as_posix()])
        print(f"{label:18} total {n:5}  train {len(splits['train']):4}  val {len(splits['val']):4}  test {len(splits['test']):4}")

    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "label", "split", "kaggle_dataset", "original_path"])
        w.writerows(manifest)
    print(f"Removed: {removed['corrupt']} corrupt, {removed['duplicate']} duplicate, {removed['over_cap']} over the cap.")
    print(f"Clean images removed (corrupt + duplicate): {removed['corrupt'] + removed['duplicate']}")


if __name__ == "__main__":
    main()
