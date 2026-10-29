#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_icf_workflow.sh (macOS-optimiert, robustere Checks)
# Erzeugt icf_json/ (inkl. icf_flat.json und qualifiers.json) aus der ClaML-XML.
# Aufruf aus beliebigem Ordner: scripts/run_icf_workflow.sh [XML] [ZIEL] [SPRACHE] [PYTHON]
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Standardparameter
XML_FILE="${1:-$ROOT_DIR/source/icf2005syst_claml_20120619.xml}"
OUT_DIR="${2:-$ROOT_DIR/icf_json}"
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

# Workflow starten
printf "\n===== ICF-Workflow gestartet =====\n"
printf "XML: %s\nZiel: %s\nSprache: %s\nPython: %s\n\n" \
  "$XML_FILE" "$OUT_DIR" "$LANG" "$PY_CMD"

"$PY_CMD" "$SCRIPT_DIR/icf_to_json.py" "$XML_FILE" "$OUT_DIR" --clean --lang "$LANG" --flatten --stats > /dev/null

printf "\n===== Workflow abgeschlossen =====\n"
