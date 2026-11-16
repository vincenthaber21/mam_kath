@echo off
REM ==========================================================================
REM  Emergency Incident Classifier - manual training
REM  Double-click this file (or run "train.bat" in a terminal in this folder).
REM  It shows every step: dataset, model, training epochs, evaluation, saving.
REM  Results appear on http://127.0.0.1:8000/models/ when it finishes.
REM ==========================================================================
cd /d "%~dp0"
set TF_CPP_MIN_LOG_LEVEL=2
set TF_ENABLE_ONEDNN_OPTS=0
set PYTHONUNBUFFERED=1

if not exist dataset\train (
  echo The dataset folder is missing. Building it from raw_data\ ...
  python scripts\build_dataset.py || goto :error
)

echo.
echo Which model do you want to train?
echo   1 = EfficientNet-B0   (the paper's main model)
echo   2 = MobileNetV2       (lightweight, fastest)
echo   3 = ResNet50          (largest, slowest)
echo   4 = All three at once and compare  (takes a few hours on a CPU)
echo   5 = Quick demo: MobileNetV2, 2 + 2 epochs  (about 5-10 minutes)
set /p CHOICE=Type 1-5 and press Enter:

set ARGS=
if "%CHOICE%"=="1" set ARGS=--archs efficientnet
if "%CHOICE%"=="2" set ARGS=--archs mobilenet_v2
if "%CHOICE%"=="3" set ARGS=--archs resnet50
if "%CHOICE%"=="4" set ARGS=--all
if "%CHOICE%"=="5" set ARGS=--archs mobilenet_v2 --epochs 2 --fine-tune-epochs 2 --model-version demo --no-activate
if "%ARGS%"=="" (
  echo Unknown choice "%CHOICE%".
  goto :end
)

echo.
echo Running: python manage.py train_models dataset %ARGS%
echo.
python manage.py train_models dataset %ARGS% || goto :error
echo.
echo Done. Open http://127.0.0.1:8000/models/ to see the models.
goto :end

:error
echo.
echo Training stopped with an error (see the messages above).

:end
echo.
pause
