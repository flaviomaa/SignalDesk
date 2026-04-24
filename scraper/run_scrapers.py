from pathlib import Path
import argparse
import subprocess
import sys
import os
import json
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

SCRAPER_MAP = {
    "bmj": "scraper_bmj.py",
    "bsi-cert": "scraper_bsi_cert.py",
    "bsi-consumer": "scraper_bsi_consumer.py",
    "edpb": "scraper_edpb.py",
    "eurlex": "scraper_eurlex.py",
    "baylda": "scraper_baylda.py",
    "berlin": "scraper_berlin.py",
    "edps": "scraper_edps.py",
    "enisa-news": "scraper_enisa_news.py",
    "enisa-publications": "scraper_enisa_publications.py",
    "hessen": "scraper_hessen.py",
    "aiact": "scraper_aiact.py",
}

GROUPS = {
    "bsi-all": ["bsi-cert", "bsi-consumer"],
    "all": [
        "bmj", "bsi-cert", "bsi-consumer", "edpb", "eurlex", "baylda",
        "berlin", "edps", "enisa-news", "enisa-publications", "hessen", "aiact"
    ],
}

OUTPUT_DIR = PROJECT_ROOT / "output"
AIACT_FILE = PROJECT_ROOT / "aiact_all_articles.json"


def run_script(script_name):
    script_path = BASE_DIR / script_name
    try:
        print(f"\n[START] Starte {script_path.name}...")

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(PROJECT_ROOT)
        )

        if result.returncode == 0:
            print(f"[OK] Erfolgreich: {script_path.name}")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"[FEHLER] {script_path.name}:")
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)

    except Exception as e:
        print(f"[FEHLER] Konnte {script_path.name} nicht starten: {e}")


def resolve_targets(targets):
    resolved = []
    for t in targets:
        if t in SCRAPER_MAP:
            resolved.append(SCRAPER_MAP[t])
        elif t in GROUPS:
            for entry in GROUPS[t]:
                resolved.append(SCRAPER_MAP[entry])
        else:
            print(f"[WARNUNG] Unbekannter Task: {t}")
    return resolved


def write_entry(f, source_name, entry, index):
    f.write("=" * 120 + "\n")
    f.write(f"SOURCE FILE: {source_name}\n")
    f.write(f"ENTRY #: {index}\n")
    f.write("-" * 120 + "\n")
    f.write(f"TITLE: {entry.get('title', 'Kein Titel')}\n")
    f.write(f"LINK: {entry.get('link', entry.get('url', 'Kein Link'))}\n")
    f.write(f"DATE: {entry.get('date', 'Kein Datum')}\n")
    if "source" in entry:
        f.write(f"SOURCE: {entry.get('source')}\n")
    if "section" in entry:
        f.write(f"SECTION: {entry.get('section')}\n")
    f.write("\nCONTENT:\n")
    f.write(entry.get("content", "Kein Inhalt"))
    f.write("\n\n")


def process_json_file(filepath, f):
    try:
        with open(filepath, "r", encoding="utf-8") as infile:
            data = json.load(infile)

        if isinstance(data, list):
            f.write("\n" + "#" * 120 + "\n")
            f.write(f"DATEI: {filepath}\n")
            f.write(f"ANZAHL EINTRAEGE: {len(data)}\n")
            f.write("#" * 120 + "\n\n")

            for i, entry in enumerate(data, 1):
                if isinstance(entry, dict):
                    write_entry(f, filepath, entry, i)
                else:
                    f.write(f"[WARNUNG] Ungueltiger Eintrag in {filepath}: {entry}\n\n")
        else:
            f.write(f"[WARNUNG] Datei {filepath} enthaelt keine Liste.\n\n")

    except Exception as e:
        f.write(f"[FEHLER] Konnte {filepath} nicht lesen: {e}\n\n")


def export_results_to_txt():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = PROJECT_ROOT / f"scraper_results_export_{timestamp}.txt"

    with open(export_file, "w", encoding="utf-8") as f:
        f.write("SCRAPER RESULTS EXPORT\n")
        f.write(f"Erstellt am: {datetime.now()}\n\n")

        if OUTPUT_DIR.is_dir():
            for filename in sorted(os.listdir(OUTPUT_DIR)):
                if filename.endswith(".json"):
                    process_json_file(OUTPUT_DIR / filename, f)
        else:
            f.write(f"[INFO] Ordner '{OUTPUT_DIR}' nicht gefunden.\n\n")

        if AIACT_FILE.exists():
            process_json_file(AIACT_FILE, f)
        else:
            f.write(f"[INFO] Datei '{AIACT_FILE}' nicht gefunden.\n\n")

    print(f"[OK] TXT-Export erstellt: {export_file.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scraper-Buendelstarter")
    parser.add_argument("targets", nargs="+", help="Scraper oder Gruppen, z.B. bmj, bsi-all, all")
    args = parser.parse_args()

    scripts = resolve_targets(args.targets)
    if not scripts:
        print("[ABBRUCH] Keine gueltigen Scraper angegeben.")
        sys.exit(1)

    for script in scripts:
        run_script(script)

    export_results_to_txt()