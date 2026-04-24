@echo off
setlocal

echo ==========================================
echo SignalDesk Pipeline startet...
echo ==========================================

echo.
echo [1/2] Starte Scraper...
python scraper\run_scrapers.py all
if errorlevel 1 (
    echo.
    echo [ABBRUCH] run_scrapers.py ist fehlgeschlagen.
    exit /b 1
)

echo.
echo [2/2] Starte Dedupe und Push...
python dedupe_and_push.py
if errorlevel 1 (
    echo.
    echo [ABBRUCH] dedupe_and_push.py ist fehlgeschlagen.
    exit /b 1
)

echo.
echo [OK] Pipeline erfolgreich abgeschlossen.
exit /b 0