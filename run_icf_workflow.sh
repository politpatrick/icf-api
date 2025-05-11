#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_icf_workflow.sh (macOS-optimiert, robustere Checks)
# ---------------------------------------------------------------------------

set -euo pipefail

# Standardparameter
XML_FILE="${1:-icf2005syst_claml_20120619.xml}"
OUT_DIR="${2:-./icf_json}"
LANG="${3:-de}"
PY_CMD="${4:-python3}"

# Prüfungen
if ! command -v "$PY_CMD" &>/dev/null; then
  echo "❌ Python-Interpreter '$PY_CMD' nicht gefunden." >&2
  exit 1
fi
if [[ ! -f "$XML_FILE" ]]; then
  echo "❌ XML-Datei '$XML_FILE' nicht gefunden." >&2
  exit 1
fi
if [[ ! -f "icf_to_json.py" ]]; then
  echo "❌ icf_to_json.py nicht im aktuellen Ordner." >&2
  exit 1
fi

# Workflow starten
printf "\n===== ICF-Workflow gestartet =====\n"
printf "XML: %s\nZiel: %s\nSprache: %s\nPython: %s\n\n" \
  "$XML_FILE" "$OUT_DIR" "$LANG" "$PY_CMD"

"$PY_CMD" icf_to_json.py "$XML_FILE" "$OUT_DIR" --clean --lang "$LANG" --flatten --stats

printf "\n===== Workflow abgeschlossen =====\n"
