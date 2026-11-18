# Emergency Incident Classifier — Django website

A complete Django + Python website for the thesis prototype (MDRRMO Santa Maria, Ilocos Sur ·
DMMMSU MLUC College of Information Technology). It classifies one emergency photo into exactly one of
five categories — **fire, crime, medical emergency, accident, disaster** — with a confidence score.
Predictions are supplementary and need human verification. The site does not dispatch or notify agencies.

## Pages

| Page | Address | What it does |
|---|---|---|
| Front page | `/` | Public product overview, three-step workflow, five categories and responsible-use guidance |
| Sign in | `/login/` | Email + password (accounts are made by the administrator) |
| Dashboard | `/dashboard/` | Monitoring overview: totals, response status, category mix, needs-attention list |
| Classify | `/classify/` | Upload or take a photo (JPG/PNG, max 10 MB), optional reference label for testing |
| Result | `/result/<id>/` | Predicted category, confidence, all five class scores, inference time; below 70% confidence is left unassigned (Uncertain) for verification |
| Incidents | `/incidents/` | Every attempt (failed ones too), response status, search, filters, 20 per page, CSV export; officers monitor all reports, residents see their own |
| Incident map | `/incidents/map/` | Google Map of reports that include GPS (same filters as Incidents); needs `GOOGLE_MAPS_API_KEY` |
| Users | `/users/` | Administrators manage officer and resident accounts (role, phone, barangay) |
| Agencies | `/agencies/` | Administrators maintain the notify-agency directory (type, phone, email, coverage) |
| Evaluation | `/evaluation/` | Upload the labelled test set (.zip, one folder per category): accuracy, per-class / macro / weighted precision-recall-F1, confusion matrix, inference time, failed attempts, misclassified examples, CSV and PDF report |
| Models | `/models/` | Compare EfficientNet / MobileNetV2 / ResNet50, training curves, upload a model, choose the active one |
| Dataset | `/dataset/` | Images per category and train / validation / test split |
| Admin | `/admin/` | Django admin for users and all records |
| Mobile API | `/api/…` | JSON API used by the Expo reporter app (login, classify, history, verify) |

## Mobile reporter app

An Expo (React Native) app in `mobile/` lets field users capture an incident photo (camera or gallery),
optionally attach notes/GPS, and submit it into the same Incidents list the website uses
(`source=mobile`). See [`mobile/README.md`](mobile/README.md) for install and LAN setup.

Quick start (with Django already running on `0.0.0.0:8000`):

```bash
cd mobile
npm install
npx expo start
```

On a physical phone set `EXPO_PUBLIC_API_URL=http://YOUR_PC_LAN_IP:8000/api` and add that IP to `ALLOWED_HOSTS`.

## Run it on your computer

You need **Python 3.11** (TensorFlow does not support Python 3.13 yet).

```bash
# 1. Open a terminal in this folder, then create a virtual environment
python -m venv .venv
# Windows:            .venv\Scripts\activate
# macOS / Linux:      source .venv/bin/activate

# 2. Install everything (TensorFlow is large; this can take a few minutes)
pip install -r requirements.txt

# 3. Settings
copy .env.example .env        # Windows   (macOS/Linux: cp .env.example .env)

# 4. Create the database and your account
python manage.py migrate
python manage.py createsuperuser

# 5. Optional: example models and dataset counts so every page has something to show
python manage.py seed_demo

# 6. Start the site
python manage.py runserver
```

Open http://127.0.0.1:8000 to view the front page, then sign in with the email and password from step 4.

### Demo mode

`.env.example` has `EIC_DEMO_MODE=True`. While no trained model **file** is active, predictions are
**simulated** and the site shows a "Demo predictions" badge, so you can try every page before training.
**Set `EIC_DEMO_MODE=False` before collecting thesis results.** Demo evaluations are clearly marked and are
never saved to the model comparison.

### If the page opens without its design

Extract the **whole ZIP**, keeping `templates/` and `static/` in the same folder as
`manage.py`. Start the website with `python manage.py runserver`, then open
http://127.0.0.1:8000 — do not open the HTML templates directly.
The website serves its bundled CSS and JavaScript even with `DEBUG=False`.
For deployment, run `python manage.py collectstatic --noinput` to prepare compressed
assets (the included Docker setup already does this). After replacing an older
copy, refresh with **Ctrl+F5** (macOS: **Cmd+Shift+R**) to clear cached styling.

## Use your trained model

Train in Colab/Jupyter with Keras, save with `model.save("efficientnet_b0.keras")`, then either:

- **Models page → Upload model**: choose the file, preprocessing type, label order and optional validation metrics, then press **Set active**; or
- the command line:

```bash
python manage.py register_model path/to/efficientnet_b0.keras --name "EfficientNet-B0" --version 1.0 \
    --preprocessing efficientnet --val-accuracy 0.894 --val-macro-f1 0.889 --history history.json --activate
```

The label order must match the model's output order. The default is
`["fire","crime","medical_emergency","accident","disaster"]`.
`history.json` is a list of `{"epoch":1,"train_acc":..,"val_acc":..,"train_loss":..,"val_loss":..}`;
you can build it from Keras `History.history`.

The active model is loaded once and kept in memory; it reloads automatically when you activate another one.
Images are converted to RGB, resized to the model's input size (default 224 px) and passed through the matching
`keras.applications` `preprocess_input` (EfficientNet, MobileNetV2 or ResNet50). Inference time is measured with
`time.perf_counter()` around `model.predict`.

## Dataset page

Lay the cleaned dataset out as `dataset/train/<label>/*.jpg`, `dataset/val/<label>/…`, `dataset/test/<label>/…`, then:

```bash
python manage.py import_dataset_counts path/to/dataset --removed 187 --sources "Kaggle Emergency Scene Dataset, Google Open Images"
```

## Evaluation (Objective 3)

Zip the held-out test split with one folder per category (`fire/`, `crime/`, `medical_emergency/`, `accident/`,
`disaster/`; one wrapping folder is fine) and upload it on the Evaluation page. It runs in the background and the
page updates by itself. Unreadable images are counted as failed attempts, separately from the metrics.
Metrics come from scikit-learn (`precision_recall_fscore_support`, `confusion_matrix`, `zero_division=0`).
Use **Export CSV** for the numbers and **Save as PDF** (your browser's print dialog) for the report.

## Tests

```bash
python manage.py test
```

These cover the public front page and protected classifier route, classification with a tiny dummy model, the JPG/PNG and 10 MB checks, failed attempts being logged,
the 70% unassigned/low-confidence rule, verification, history filters and CSV export, the metric computations, and a full
test-set evaluation.

## Settings (.env)

| Name | Meaning |
|---|---|
| `SECRET_KEY` | Long random string (required when deployed) |
| `DEBUG` | `True` on your computer, `False` when deployed |
| `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | Your domain when deployed |
| `DATABASE_URL` | Empty = local SQLite file; or a PostgreSQL URL |
| `LOW_CONFIDENCE_THRESHOLD` | Default `0.70` (below this, no category is assigned) |
| `EIC_DEMO_MODE` | Simulated predictions when no model file is active |
| `GOOGLE_MAPS_API_KEY` | Maps JavaScript API key for `/incidents/map/` (restrict by HTTP referrer) |
| `MEDIA_ROOT` / `SERVE_MEDIA` | Where uploaded photos and models are stored, and whether Django serves them |

## Deploy (Render)

`render.yaml` and `Dockerfile` are included: push this folder to GitHub, create a **Blueprint** on Render, then
open the service's Shell and run `python manage.py createsuperuser`. Uploaded photos and models are kept on the
attached disk (`/data/media`). TensorFlow needs at least ~2 GB RAM, so pick a plan with enough memory.

## Project layout

```
eic_site/      settings and main URLs
accounts/      email-based user and sign-in
classifier/    labels, upload checks, inference service, Classify / Result / Incidents
evaluation/    test-set runner (background thread), sklearn metrics, report
registry/      ML models, dataset counts, management commands (register_model, import_dataset_counts, seed_demo)
templates/     HTML pages
static/        CSS, JavaScript, Chart.js
```
